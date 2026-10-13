import importlib.util
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


if __name__ == '__main__':
    unittest.main()
