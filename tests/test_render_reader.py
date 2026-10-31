import importlib.util
import hashlib
import json
import re
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("render_reader", ROOT / "scripts" / "render_reader.py")
reader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reader)


class Inspector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.hrefs = []
        self.tags = []
        self.details_classes = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        attrs = dict(attrs)
        if tag == 'details':
            self.details_classes.append(attrs.get('class', '').split())
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if "href" in attrs:
            self.hrefs.append(attrs["href"])


class MarkdownTests(unittest.TestCase):
    def test_raw_html_never_becomes_markup(self):
        rendered = reader.markdown('<script>alert(1)</script>\n<img src=x onerror="boom">')
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("<script", rendered)
        self.assertNotIn("<img", rendered)
        self.assertIn("&quot;boom&quot;", rendered)

    def test_code_preserves_dollars_backticks_and_tags(self):
        rendered = reader.markdown('```python\nx = "$HOME <tag> `value`"\n## not a heading\n```')
        self.assertIn('$HOME &lt;tag&gt; `value`', rendered)
        self.assertIn("## not a heading", rendered)
        self.assertNotIn("<h2", rendered)
        self.assertIn("<pre><code>", rendered)

    def test_code_blocks_cannot_inject_html(self):
        rendered = reader.markdown('```</div><script>alert(1)</script>\n</code><img src=x>\n```')
        self.assertNotIn("<script", rendered)
        self.assertNotIn("<img", rendered)
        self.assertIn("&lt;/code&gt;", rendered)

    def test_inline_and_safe_links(self):
        rendered = reader.markdown('**重点** `a < b` [网址](https://example.com/?x=1&y=2) [段落](#地图) [笔记](./notes.md)')
        self.assertIn("<strong>重点</strong>", rendered)
        self.assertIn("<code>a &lt; b</code>", rendered)
        self.assertIn('href="https://example.com/?x=1&amp;y=2"', rendered)
        self.assertIn('href="#地图"', rendered)
        self.assertIn('href="./notes.md"', rendered)

    def test_unsafe_links_are_plain_labels(self):
        dangerous = ('javascript:alert', 'data:text/html,boom', 'file:///etc/passwd',
                     '//evil.test/thing', '\\evil.test', '/absolute/path',
                     'java%73cript:evil', 'javascript%3Aevil', 'https://user:pass@example.com',
                     'https://:pass@example.com', 'https://example.com/%0aattack')
        for url in dangerous:
            with self.subTest(url=url):
                self.assertIsNone(reader.safe_url(url))
                self.assertNotIn("href=", reader.markdown('[阅读](' + url + ')'))
        for url in ('https://example.com', 'http://example.com', '#heading', '../notes.md', 'notes/one.md'):
            with self.subTest(url=url):
                self.assertEqual(reader.safe_url(url), url)

    def test_quote_attribute_in_url_is_escaped(self):
        rendered = reader.markdown('[x](https://example.com/"onmouseover="alert)')
        inspector = Inspector()
        inspector.feed(rendered)
        self.assertEqual(inspector.hrefs, ['https://example.com/"onmouseover="alert'])
        self.assertIn('&quot;', rendered)

    def test_tables_handle_inline_code_and_escaped_pipes(self):
        rendered = reader.markdown('| 名称 | 内容 |\n| :--- | ---: |\n| `a|b` | 一个\\|两个 |')
        self.assertIn("<table>", rendered)
        self.assertIn('<td class="align-left"><code>a|b</code></td>', rendered)
        self.assertIn('<td class="align-right">一个|两个</td>', rendered)
        self.assertEqual(rendered.count("<td "), 2)

    def test_lists_quotes_and_duplicate_headings(self):
        rendered = reader.markdown('## 同名\n- 第一\n- 第二\n\n## 同名\n3. 第三\n4. 第四\n\n> 引用\n> **作者**')
        self.assertIn('id="同名"', rendered)
        self.assertIn('id="同名-2"', rendered)
        self.assertIn('<ol start="3">', rendered)
        self.assertIn('<blockquote>', rendered)
        self.assertEqual(rendered.count("<li>"), 4)

    def test_chapter_boundaries_ignore_code_headings(self):
        chapters = reader.chapters('# 蒸馏\n\n## 第一章\n```md\n## 假章节\n```\n\n## 第二章\n正文')
        self.assertEqual([name for name, _ in chapters], ['第一章', '第二章'])
        self.assertIn('## 假章节', chapters[0][1])


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, filename, source):
        (self.workspace / filename).write_text(source, encoding="utf-8")

    def test_no_source_files_fails(self):
        with self.assertRaises(ValueError):
            reader.render_workspace(self.workspace)
        self.assertFalse((self.workspace / "reader.html").exists())

    def test_missing_files_show_pending(self):
        self.write('map.md', '# 我的书\n材料范围：仅第一章。其余未提供。')
        output = reader.render_workspace(self.workspace)
        page = output.read_text(encoding="utf-8")
        self.assertEqual(output, self.workspace / 'reader.html')
        self.assertEqual(page.count('尚未准备。后续阅读时补充。'), 3)
        self.assertIn('仅第一章。其余未提供。', page)
        inspector = Inspector()
        inspector.feed(page)
        self.assertFalse(any(href.startswith(str(self.workspace)) for href in inspector.hrefs))
        self.assertIn('<html lang="zh-CN">', page)

    def test_navigation_is_unique_and_stable(self):
        self.write('map.md', '# 测试书\n## 第一章\n范围：全文已提供。')
        self.write('distillation.md', '# 蒸馏\n## 第一章\n内容\n### 要点\n更多\n## 第一章\n第二部分')
        self.write('route.md', '## 第一章\n1. 回读')
        self.write('progress.md', '## 第一章\n待讨论')
        output = reader.render_workspace(self.workspace)
        first = output.read_text(encoding='utf-8')
        second = reader.render_workspace(self.workspace).read_text(encoding='utf-8')
        self.assertEqual(first, second)
        inspector = Inspector()
        inspector.feed(first)
        self.assertEqual(len(inspector.ids), len(set(inspector.ids)))
        for href in inspector.hrefs:
            if href.startswith('#'):
                self.assertIn(href[1:], inspector.ids)
        self.assertEqual(sum('chapter' in classes for classes in inspector.details_classes), 2)
        self.assertIn('href="#chapter-第一章-2"', first)
        self.assertIn('beforeprint', first)
        self.assertIn('afterprint', first)

    def test_template_tokens_in_book_text_cannot_replace_content(self):
        self.write('map.md', '# {{TITLE}} <script>oops</script>\n{{DEPTH}}')
        self.write('distillation.md', '## 第一章\n独立内容')
        page = reader.render_workspace(self.workspace).read_text(encoding='utf-8')
        self.assertIn('{{TITLE}} &lt;script&gt;oops&lt;/script&gt;', page)
        self.assertIn('<p>{{DEPTH}}</p>', page)
        self.assertEqual(page.count('<script>'), 1)

    def test_offline_page_and_custom_output(self):
        self.write('progress.md', '下一步：阅读第一章。')
        output = reader.render_workspace(self.workspace, self.workspace / 'nested' / 'index.html')
        page = output.read_text(encoding='utf-8')
        self.assertNotRegex(page, r'<(?:script|link|iframe|img)\b[^>]*(?:src|href)=')
        self.assertNotIn('fetch(', page)
        self.assertNotIn('XMLHttpRequest', page)
        self.assertIn('下一步：阅读第一章。', page)

    def test_optional_study_map_is_embedded_without_separate_navigation(self):
        self.write('map.md', '# 测试书')
        self.write('distillation.md', '## 事务\n已经带读的事务内容。')
        self.write('study-map-embed.txt', '<!doctype html><html><head></head><body><h1>知识地图</h1><script>window.test = "ok"</script></body></html>')
        page = reader.render_workspace(self.workspace).read_text(encoding='utf-8')
        self.assertIn('href="#study-plan"', page)
        self.assertIn('id="study-plan"', page)
        self.assertIn('title="全书带读地图"', page)
        self.assertIn('sandbox="allow-scripts allow-top-navigation-by-user-activation"', page)
        self.assertIn('&lt;h1&gt;知识地图&lt;/h1&gt;', page)
        self.assertIn('&lt;base target=&quot;_top&quot;&gt;', page)
        self.assertNotIn('src="study-map.html"', page)
        self.assertIn('已经带读的事务内容。', page)
        self.assertEqual(page.count('<script>'), 1)
        self.assertIn('reader-study-map-height', page)
        self.assertIn('event.source !== studyMapFrame.contentWindow', page)
        self.assertIn('ResizeObserver', page)

    def test_compact_navigation_keeps_current_and_all_reading_content(self):
        self.write('map.md', '# 测试书')
        self.write('distillation.md', '## 当前单元：备份\n现在的内容\n## 已介绍：索引\n索引内容\n## 已介绍：锁\n锁内容')
        self.write('study-map-embed.txt', '<html><head></head><body>地图</body></html>')
        self.write('reader-navigation.txt', 'compact\n')
        page = reader.render_workspace(self.workspace).read_text(encoding='utf-8')
        nav = re.search(r'<nav class="toc">(.*?)</nav>', page, re.S).group(1)
        self.assertEqual(len(re.findall(r'<a\s', nav)), 4)
        for label in ('带读地图', '当前阅读', '已讲内容', '阅读进度'):
            self.assertIn(label, nav)
        self.assertIn('href="#chapter-当前单元-备份"', nav)
        self.assertNotIn('class="chapter-link"', nav)
        self.assertIn('id="chapter-已介绍-索引"', page)
        self.assertIn('索引内容', page)
        self.assertIn('锁内容', page)

    def test_optional_theme_is_local_and_cannot_close_style(self):
        self.write('map.md', '# 测试书')
        self.write('reader-theme.css', ':root { --paper: #10151b; }')
        page = reader.render_workspace(self.workspace).read_text(encoding='utf-8')
        self.assertIn(':root { --paper: #10151b; }', page)
        self.write('reader-theme.css', '</style><script>bad()</script>')
        with self.assertRaises(ValueError):
            reader.render_workspace(self.workspace)
        self.write('reader-theme.css', '@import "https://example.com/x.css";')
        with self.assertRaises(ValueError):
            reader.render_workspace(self.workspace)

    def test_map_first_keeps_history_under_its_point_and_counts_once(self):
        self.write('reader-navigation.txt', 'map-first')
        self.write('original.txt', '真实原文片段')
        self.write('distillation.md', '## 已介绍：事务提交\n真实讲解。\n\n[展开原文](original.txt)')
        point = {'id':'1.1.1','title':'事务','status':'进行中','counted':True,
                 'goal':'事务的作用','items':[],'related':[],'history_ids':['h1']}
        summary = {'id':'1.2','title':'小结','status':'待带读','counted':False,
                   'goal':'回顾','items':[],'related':[],'history_ids':[]}
        data = {'title':'测试书','description':'一本测试书。',
                'current':{'point_id':'1.1.1','label':'事务提交','chapter':'第1章'},
                'topics':[{'chapters':[{'id':1,'title':'基础','modules':[{'id':'1.1','title':'事务','points':[point,summary]}]}]}],
                'history':[{'id':'h1','title':'事务提交','reader_link':'reader.html#old-transaction'}],
                'counts':{'by_status':{'已带读':0,'进行中':1,'待带读':0}}}
        self.write('study-map-data.json', json.dumps(data, ensure_ascii=False))
        page = reader.render_workspace(self.workspace).read_text(encoding='utf-8')
        self.assertNotIn('<iframe', page)
        self.assertNotIn('class="sidebar"', page)
        self.assertIn('href="#point-1.1.1"', page)
        self.assertIn('已讲过 1 段', page)
        self.assertIn('1 个章节条目按节统计', page)
        self.assertIn('已讲解（段）', page)
        self.assertIn('data-has-history="true"', page)
        self.assertIn('id="old-transaction"', page)
        self.assertIn('真实讲解。', page)
        self.assertIn('真实原文片段', page)
        self.assertIn('id="prompt-resume"', page)
        point['status'] = '经确认暂缓'
        data['counts']['by_status'] = {'已带读':0,'进行中':0,'待带读':0,'经确认暂缓':1}
        self.write('study-map-data.json', json.dumps(data, ensure_ascii=False))
        page = reader.render_workspace(self.workspace).read_text(encoding='utf-8')
        self.assertIn('class="status deferred">经确认暂缓', page)
        self.assertIn('<strong>1</strong><span>暂缓（节）</span>', page)
        self.assertIn('<option value="经确认暂缓">', page)
        data['progress_mode'] = 'history-led'
        self.write('study-map-data.json', json.dumps(data, ensure_ascii=False))
        page = reader.render_workspace(self.workspace).read_text(encoding='utf-8')
        self.assertIn('<strong>1</strong><span>暂缓（节）</span>', page)

    def test_map_first_rejects_unassigned_history(self):
        self.write('reader-navigation.txt', 'map-first')
        self.write('distillation.md', '## 已介绍：事务提交\n内容')
        data = {'topics':[], 'history':[{'id':'h1','title':'事务提交'}],
                'current':{'point_id':'1.1.1'}}
        self.write('study-map-data.json', json.dumps(data, ensure_ascii=False))
        with self.assertRaisesRegex(ValueError, '历史讲解'):
            reader.render_workspace(self.workspace)

    def test_map_first_renders_derived_history_and_original_source(self):
        self.write('reader-navigation.txt', 'map-first')
        self.write('distillation.md', '原有笔记仍保留。')
        self.write('map-history.md', '## 已介绍：01 字典用 ** 展开\n原有讲解。')
        (self.workspace / 'source').mkdir()
        self.write('source/chapter.txt', '可回查的原书内容')
        point = {'id':'1.1','title':'字典','status':'进行中','counted':True,
                 'source':'source/chapter.txt','history_ids':['h1']}
        data = {'history_file':'map-history.md', 'history_label':'历史记录（段）',
                'point_source_previews':True,
                'current':{'point_id':'1.1','label':'字典','chapter':'第1章'},
                'topics':[{'chapters':[{'id':1,'title':'基础','modules':[{'id':'1.1','title':'字典','points':[point]}]}]}],
                'history':[{'id':'h1','title':'01 字典用 ** 展开','display_status':'历史记录'}],
                'counts':{'by_status':{'已带读':0,'进行中':1,'待带读':0}}}
        self.write('study-map-data.json', json.dumps(data, ensure_ascii=False))
        page = reader.render_workspace(self.workspace).read_text(encoding='utf-8')
        self.assertIn('原有讲解。', page)
        self.assertIn('可回查的原书内容', page)
        self.assertIn('历史记录（段）', page)
        self.assertIn('data-has-history="false"', page)
        data['progress_mode'] = 'history-led'
        data['history'][0]['display_status'] = '已带读'
        self.write('study-map-data.json', json.dumps(data, ensure_ascii=False))
        page = reader.render_workspace(self.workspace).read_text(encoding='utf-8')
        self.assertIn('<strong>1</strong><span>已带读（段）</span>', page)
        self.assertIn('data-has-history="true"', page)
        self.assertIn('<span class="status done">已带读</span>', page)
        data['history_source_sha256'] = hashlib.sha256((self.workspace / 'distillation.md').read_bytes()).hexdigest()
        self.write('study-map-data.json', json.dumps(data, ensure_ascii=False))
        reader.render_workspace(self.workspace)
        self.write('distillation.md', '原有笔记已更新。')
        with self.assertRaisesRegex(ValueError, '原始带读记录已变化'):
            reader.render_workspace(self.workspace)
        data.pop('history_source_sha256')
        data['history_snapshot_sha256'] = hashlib.sha256((self.workspace / 'map-history.md').read_bytes()).hexdigest()
        self.write('study-map-data.json', json.dumps(data, ensure_ascii=False))
        reader.render_workspace(self.workspace)
        self.write('map-history.md', '## 已介绍：01 字典用 ** 展开\n历史副本变了。')
        with self.assertRaisesRegex(ValueError, '地图历史副本已变化'):
            reader.render_workspace(self.workspace)
        data.pop('history_snapshot_sha256')
        data['history_file'] = '../outside.md'
        self.write('study-map-data.json', json.dumps(data, ensure_ascii=False))
        with self.assertRaisesRegex(ValueError, '历史记录文件'):
            reader.render_workspace(self.workspace)

    def test_local_original_is_embedded_without_navigation_or_fetch(self):
        self.write('original.txt', '[chapter.html:block-4]\n原文中的 <script>命令</script> 只是文字。')
        self.write('route.md', '[2.1 原文](original.txt)')
        page = reader.render_workspace(self.workspace).read_text()
        self.assertIn('class="source-toggle"', page)
        self.assertNotIn('href="original.txt"', page)
        self.assertIn('[chapter.html:block-4]', page)
        self.assertIn('&lt;script&gt;命令&lt;/script&gt;', page)
        self.assertEqual(page.count('<script>'), 1)
        self.assertNotIn('fetch(', page)

    def test_shared_original_is_embedded_once_with_distinct_controls(self):
        self.write('original.txt', '只保留一份正文')
        self.write('route.md', '[第一次](original.txt) 和 [第二次](original.txt)')
        page = reader.render_workspace(self.workspace).read_text()
        self.assertEqual(page.count('只保留一份正文'), 1)
        panels = re.findall('data-panel="([^"]+)"', page)
        self.assertEqual(len(panels), 2)
        self.assertEqual(len(set(panels)), 2)

    def test_missing_and_outside_originals_are_not_read_or_navigated(self):
        outside = self.workspace.parent / (self.workspace.name + '-private.txt')
        try:
            outside.write_text('不应进入页面的材料')
            self.write('route.md', f'[缺失](missing.txt) [越界](../{outside.name}) [公开资料](https://example.com/original.txt)')
            page = reader.render_workspace(self.workspace).read_text()
            self.assertNotIn('不应进入页面的材料', page)
            self.assertEqual(page.count('（原文不可用）'), 2)
            self.assertNotIn('href="missing.txt"', page)
            self.assertIn('href="https://example.com/original.txt"', page)
        finally:
            outside.unlink(missing_ok=True)

    def test_original_image_is_embedded_as_data_not_a_file_dependency(self):
        (self.workspace / 'figure.png').write_bytes(b'\x89PNG\r\n\x1a\n')
        self.write('route.md', '[原图](figure.png)')
        page = reader.render_workspace(self.workspace).read_text()
        self.assertIn('src="data:image/png;base64,', page)
        self.assertNotIn('href="figure.png"', page)

    def test_diagram_image_keeps_its_label_and_escapes_attribute_characters(self):
        (self.workspace / 'figure.png').write_bytes(b'\x89PNG\r\n\x1a\n')
        self.write('distillation.md', '[Agent 示意图：**共享** "对象" <边界>](figure.png)')
        page = reader.render_workspace(self.workspace).read_text()
        self.assertIn('alt="Agent 示意图：共享 &quot;对象&quot; &lt;边界&gt;"', page)
        self.assertNotIn('alt="原文图片"', page)

    def test_unreferenced_material_is_not_embedded(self):
        self.write('later.txt', '未经选择的后续剧情')
        self.write('first.txt', '第一章材料')
        self.write('route.md', '[第一章](first.txt)')
        page = reader.render_workspace(self.workspace).read_text()
        self.assertIn('第一章材料', page)
        self.assertNotIn('未经选择的后续剧情', page)

    def test_resume_prompt_preserves_actual_path_with_html_characters(self):
        workspace = self.workspace / '阅读 <one> & two'
        workspace.mkdir()
        (workspace / 'map.md').write_text('# 我的书')
        page = reader.render_workspace(workspace).read_text()

        class Prompts(HTMLParser):
            def __init__(self):
                super().__init__()
                self.active = None
                self.values = {}

            def handle_starttag(self, tag, attrs):
                identifier = dict(attrs).get('id', '')
                if tag == 'code' and identifier.startswith('prompt-'):
                    self.active = identifier
                    self.values[identifier] = ''

            def handle_data(self, value):
                if self.active:
                    self.values[self.active] += value

            def handle_endtag(self, tag):
                if tag == 'code':
                    self.active = None

        prompts = Prompts()
        prompts.feed(page)
        self.assertEqual(set(prompts.values), {'prompt-start', 'prompt-continue', 'prompt-resume'})
        for value in prompts.values.values():
            self.assertTrue(value.startswith('$read-with-agent '))
            self.assertIn(str(workspace.resolve()), value)

    def test_generating_handoff_does_not_change_learning_record(self):
        self.write('progress.md', '2.1 已介绍；没有回答；下一步继续解释。')
        before = (self.workspace / 'progress.md').read_bytes()
        reader.render_workspace(self.workspace)
        self.assertEqual((self.workspace / 'progress.md').read_bytes(), before)

    def test_preferences_and_selected_history_are_available_offline(self):
        self.write('progress.md', '# 当前进度\n下一步：探针。\n[回查历史](history/unit-6.md)')
        self.write('preferences.md', '# 偏好\n昂贵演示先选择。<script>alert(1)</script>')
        (self.workspace / 'history').mkdir()
        self.write('history/unit-6.md', '实际反馈：懂了；仅为自述理解。')
        self.write('history/unit-1.md', '未选择的早期记录')
        before = {p: p.read_bytes() for p in self.workspace.rglob('*.md')}
        page = reader.render_workspace(self.workspace).read_text()
        self.assertIn('<summary>当前阅读偏好</summary>', page)
        self.assertIn('昂贵演示先选择。&lt;script&gt;', page)
        self.assertIn('实际反馈：懂了；仅为自述理解。', page)
        self.assertNotIn('未选择的早期记录', page)
        self.assertEqual(before, {p: p.read_bytes() for p in self.workspace.rglob('*.md')})

    def test_shared_preferences_apply_without_a_book_preferences_file(self):
        self.write('preferences.md', '# 公共偏好\n复杂关系先图后文。<script>unsafe</script>')
        book = self.workspace / 'book'
        book.mkdir()
        (book / 'progress.md').write_text('当前未答；下次接回。', encoding='utf-8')
        before = {p: p.read_bytes() for p in self.workspace.rglob('*.md')}
        page = reader.render_workspace(book).read_text(encoding='utf-8')
        self.assertIn('<summary>公共阅读偏好</summary>', page)
        self.assertIn('复杂关系先图后文。&lt;script&gt;', page)
        self.assertNotIn('<summary>当前阅读偏好</summary>', page)
        self.assertIn('当前未答；下次接回。', page)
        self.assertEqual(before, {p: p.read_bytes() for p in self.workspace.rglob('*.md')})

    def test_nearest_shared_preferences_and_book_exceptions_are_kept_separate(self):
        self.write('preferences.md', '# 外层偏好\n不应加载的外层记录。')
        collection = self.workspace / 'reading'
        book = collection / 'python'
        book.mkdir(parents=True)
        (collection / 'preferences.md').write_text('# 偏好\n中文，默认图解。', encoding='utf-8')
        (book / 'preferences.md').write_text(
            '# 偏好\n[公共偏好](../preferences.md)\n本书只用文字，答错先巩固。', encoding='utf-8')
        (book / 'progress.md').write_text('第一章；未验证。', encoding='utf-8')
        before = {p: p.read_bytes() for p in self.workspace.rglob('*.md')}
        page = reader.render_workspace(book).read_text(encoding='utf-8')
        self.assertIn('中文，默认图解。', page)
        self.assertIn('本书只用文字，答错先巩固。', page)
        self.assertNotIn('不应加载的外层记录。', page)
        self.assertIn('href="#shared-preferences"', page)
        self.assertNotIn('（原文不可用）', page)
        inspector = Inspector()
        inspector.feed(page)
        self.assertEqual(len(inspector.ids), len(set(inspector.ids)))
        for href in inspector.hrefs:
            if href.startswith('#'):
                self.assertIn(href[1:], inspector.ids)
        self.assertEqual(before, {p: p.read_bytes() for p in self.workspace.rglob('*.md')})

    def test_shared_preferences_are_found_for_a_nested_legacy_book(self):
        self.write('preferences.md', '# 公共偏好\n沿用简图。')
        book = self.workspace / 'outputs' / 'reading' / 'book'
        book.mkdir(parents=True)
        (book / 'map.md').write_text('# 旧书', encoding='utf-8')
        (book / 'preferences.md').write_text('[公共偏好](../../../preferences.md)', encoding='utf-8')
        page = reader.render_workspace(book).read_text(encoding='utf-8')
        self.assertIn('沿用简图。', page)
        self.assertIn('href="#shared-preferences"', page)
        self.assertIn(str(book.resolve()), page)


if __name__ == '__main__':
    unittest.main()
