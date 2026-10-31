"""Render a map-first, single-page reader from an explicitly prepared workspace."""
import html
import hashlib
import json
import re
from pathlib import Path


def render(workspace, output, engine):
    workspace = Path(workspace)
    data_file = workspace / 'study-map-data.json'
    notes_file = workspace / 'distillation.md'
    if not data_file.is_file() or not notes_file.is_file():
        raise ValueError('地图阅读页需要 study-map-data.json 和 distillation.md。')
    data = json.loads(data_file.read_text(encoding='utf-8'))
    if data.get('history_file'):
        expected = data.get('history_source_sha256')
        if expected and hashlib.sha256(notes_file.read_bytes()).hexdigest() != expected:
            raise ValueError('原始带读记录已变化；请同步地图历史及状态后更新来源指纹。')
        candidate = (workspace / data['history_file']).resolve()
        if not candidate.is_relative_to(workspace.resolve()) or not candidate.is_file():
            raise ValueError('地图历史记录文件不存在或位于工作区之外。')
        expected_snapshot = data.get('history_snapshot_sha256')
        if expected_snapshot and hashlib.sha256(candidate.read_bytes()).hexdigest() != expected_snapshot:
            raise ValueError('地图历史副本已变化；请核对原始记录和归属后更新副本指纹。')
        notes_file = candidate
    anchors = engine['Anchors']()
    previews = engine['SourcePreviews'](workspace, anchors)
    sections = {}
    for heading, text in engine['chapters'](notes_file.read_text(encoding='utf-8-sig')):
        if '：' in heading:
            sections[engine['plain'](heading.split('：', 1)[1]).strip()] = text
    records = {x['id']: x for x in data.get('history', [])}
    if len(records) != len(data.get('history', [])):
        raise ValueError('历史讲解编号重复。')
    all_points = [point for topic in data['topics'] for chapter in topic['chapters']
                  for module in chapter['modules'] for point in module['points']]
    point_ids = {x['id'] for x in all_points}
    if len(point_ids) != len(all_points):
        raise ValueError('地图知识点编号重复。')
    assigned = [h for point in all_points for h in point.get('history_ids', [])]
    if len(assigned) != len(records) or set(assigned) != set(records):
        raise ValueError('历史讲解必须且只能归属一个知识点。')
    current = data.get('current', {})
    if current.get('point_id') not in point_ids:
        raise ValueError('当前阅读位置未映射到知识点。')
    esc = lambda v: html.escape(str(v), quote=True)
    lecture_templates = []
    for rec in records.values():
        body = sections.get(engine['plain'](rec['title']).strip())
        if body is None:
            raise ValueError(f'找不到历史讲解正文：{rec["title"]}')
        fragment = engine['markdown'](body, anchors, f'lecture-{rec["id"]}-')
        fragment = previews.replace(fragment)
        lecture_templates.append(f'<template id="lecture-{esc(rec["id"])}"><div class="lecture-content">{fragment}</div></template>')
    out = []
    for topic in data['topics']:
        for chapter in topic['chapters']:
            point_count = sum(p.get('counted', True) for m in chapter['modules'] for p in m['points'])
            out.append(f'<details class="map-chapter" id="map-chapter-{esc(chapter["id"])}"><summary><span class="chapter-index">{int(chapter["id"]):02d}</span><span class="chapter-title">{esc(chapter["title"])}</span><span class="chapter-count">{point_count} 项</span></summary><div class="chapter-items">')
            for module in chapter['modules']:
                out.append(f'<details class="map-module"><summary><span>{esc(module["id"])} {esc(module["title"])}</span></summary><div class="module-items">')
                if module.get('intro') and any(p['id'] != module['id'] for p in module['points']):
                    out.append(f'<p class="point-intro">原书模块引入（摘句）：{esc(module["intro"])}</p>')
                for point in module['points']:
                    point_id = point['id']
                    if not re.fullmatch(r'\d+(?:\.\d+)+', point_id):
                        raise ValueError(f'无效知识点编号：{point_id}')
                    is_counted = point.get('counted', True)
                    status = point['status'] if is_counted else ''
                    titles = [records[x]['title'] for x in point.get('history_ids', [])]
                    has_lectures = any(records[x].get('display_status', '已带读') == '已带读' for x in point.get('history_ids', []))
                    search = ' '.join([chapter['title'], module['title'], point_id,
                                       point['title'], point.get('goal', ''), *titles])
                    state_class = {'已带读':'done', '进行中':'partial', '待带读':'pending', '经确认暂缓':'deferred'}.get(status, '')
                    badge = f'<span class="status {state_class}">{esc(status)}</span>' if status else f'<span class="status summary-status">{esc(point.get("uncounted_label", "本章小结"))}</span>'
                    out.append(f'<details class="map-point" id="point-{esc(point_id)}" data-search="{esc(search.lower())}" data-status="{esc(status)}" data-has-history="{str(has_lectures).lower()}"><summary><span class="point-title">{esc(point_id)} {esc(point["title"])}</span>{badge}</summary><div class="point-content">')
                    if point.get('status_reason'):
                        out.append(f'<p class="point-intro">状态说明：{esc(point["status_reason"])}</p>')
                    if point.get('goal'):
                        out.append(f'<p class="point-intro">{esc(point["goal"])}</p>')
                    if point.get('items'):
                        out.append('<ul class="point-items">' + ''.join(f'<li>{esc(item)}</li>' for item in point['items']) + '</ul>')
                    if data.get('point_source_previews') and point.get('source'):
                        label = point.get('source_label', '展开原书目录定位' if point['source'].endswith('/toc.txt') else '展开原书章节文本')
                        source_link = f'[{label}]({point["source"]})'
                        out.append(previews.replace(engine['markdown'](source_link, anchors, f'source-{point_id}-')))
                    ids = point.get('history_ids', [])
                    if ids:
                        history_label = data.get('history_group_label', '已讲过')
                        out.append(f'<details class="history"><summary>{esc(history_label)} {len(ids)} 段</summary><div class="history-items">')
                        for hid in ids:
                            rec = records[hid]
                            legacy = rec.get('reader_link', '').partition('#')[2]
                            if not legacy: legacy = f'lecture-record-{hid}'
                            record_status = rec.get('display_status', '已带读')
                            record_class = 'done' if record_status == '已带读' else 'pending'
                            out.append(f'<details class="lecture" id="{esc(legacy)}" data-lecture="lecture-{esc(hid)}"><summary>{esc(rec["title"])} <span class="status {record_class}">{esc(record_status)}</span></summary><div class="lecture-body"></div></details>')
                        out.append('</div></details>')
                    if point.get('related'):
                        links = ' '.join(f'<a data-jump href="#point-{esc(v)}">{esc(v)}</a>' for v in point['related'] if v in point_ids)
                        if links: out.append(f'<p class="related">关联知识点：{links}</p>')
                    out.append(f'<p class="source-reference">原书第 {int(chapter["id"])} 章 · {esc(point_id)}</p></div></details>')
                out.append('</div></details>')
            out.append('</div></details>')
    statuses = ['已带读', '进行中', '待带读']
    if ('经确认暂缓' in data.get('counts', {}).get('by_status', {}) or
            any(x.get('counted', True) and x['status'] == '经确认暂缓' for x in all_points)):
        statuses.append('经确认暂缓')
    status_counts = {s: sum(x.get('counted', True) and x['status'] == s for x in all_points)
                     for s in statuses}
    if any(x.get('counted', True) and x['status'] not in statuses for x in all_points):
        raise ValueError('地图包含不支持的带读状态。')
    if status_counts != data.get('counts', {}).get('by_status'):
        raise ValueError('进度计数与知识点状态不一致。')
    location = str(workspace.resolve())
    if data.get('progress_mode') == 'history-led':
        taught = sum(x.get('display_status') == '已带读' for x in records.values())
        progress_values = (f'<div><strong>{taught}</strong><span>已带读（段）</span></div>'
                           f'<div><strong>{status_counts["进行中"]}</strong><span>进行中（节）</span></div>'
                           f'<div><strong>{status_counts["待带读"]}</strong><span>待带读（节）</span></div>')
    else:
        progress_values = (f'<div><strong>{len(records)}</strong><span>{esc(data.get("history_label", "已讲解（段）"))}</span></div>'
                           f'<div><strong>{status_counts["已带读"]}</strong><span>已完成（节）</span></div>'
                           f'<div><strong>{status_counts["进行中"]}</strong><span>进行中（节）</span></div>'
                           f'<div><strong>{status_counts["待带读"]}</strong><span>待带读（节）</span></div>')
    if status_counts.get('经确认暂缓', 0):
        progress_values += f'<div><strong>{status_counts["经确认暂缓"]}</strong><span>暂缓（节）</span></div>'
    prompts = {
        'start': f'$read-with-agent 请从这本书的带读地图开始：{location}\n先读取当前进度和地图，一次继续一小段。',
        'continue': '继续',
        'resume': f'$read-with-agent 继续带读这个工作区：{location}\n请读取公共偏好、本书偏好、进度和带读地图，保留未答问题与真实理解状态。',
    }
    template = (Path(__file__).resolve().parent.parent / 'assets' / 'map-reader-template.html').read_text(encoding='utf-8')
    values = {
        'TITLE': esc(data.get('title', '读书笔记').replace('全书带读地图', '').strip()),
        'INTRO': esc(data.get('description', '沿着原书的结构，循序渐进地阅读和理解。')),
        'CURRENT_CHAPTER': esc(current.get('chapter', '当前阅读')),
        'CURRENT_LABEL': esc(current.get('label', '查看当前位置')),
        'CURRENT_POINT': esc(current['point_id']),
        'DONE': str(status_counts['已带读']), 'DOING': str(status_counts['进行中']),
        'TODO': str(status_counts['待带读']), 'TOTAL': str(sum(status_counts.values())), 'HISTORY': str(len(records)),
        'HISTORY_LABEL': esc(data.get('history_label', '已讲解（段）')),
        'PROGRESS_VALUES': progress_values,
        'MAP_NOTE': esc(data.get('map_note', f'{sum(status_counts.values())} 个章节条目按节统计；历史按记录段落统计，两者不能相加。部分章节仍需细分并核对。')),
        'TREE': '\n'.join(out), 'LECTURE_TEMPLATES': '\n'.join(lecture_templates),
        'SOURCE_TEMPLATES': previews.render_templates(),
        'START_PROMPT': esc(prompts['start']), 'CONTINUE_PROMPT': esc(prompts['continue']),
        'RESUME_PROMPT': esc(prompts['resume']),
    }
    page = re.sub(r'\{\{([A-Z_]+)\}\}', lambda m: values[m.group(1)], template)
    output = Path(output) if output else workspace / 'reader.html'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding='utf-8')
    return output
