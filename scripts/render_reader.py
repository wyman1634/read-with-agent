#!/usr/bin/env python3
"""Render a book's Markdown notes as one offline, accessible reading page.

Uses only Python's standard library. Raw HTML is always displayed as text.
The caller must omit spoilers until the reader has explicitly allowed them.
"""

import argparse
import base64
import html
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


FILES = ("map.md", "distillation.md", "route.md", "progress.md")
HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
LIST_ITEM = re.compile(r"^\s*(?:([-+*])|(\d+)[.)])\s+(.+)$")


def safe_url(value):
    """Allow HTTP(S), page fragments and relative paths; reject active schemes."""
    value = value.strip()
    decoded = unquote(value)
    if not value or any(ord(c) < 33 for c in decoded):
        return None
    if "\\" in decoded or decoded.startswith(("/", "//")):
        return None
    try:
        parsed = urlsplit(value)
        scheme = parsed.scheme.lower()
        if scheme in ("http", "https"):
            return value if parsed.hostname and parsed.username is None else None
        if scheme or ":" in decoded.split("/", 1)[0]:
            return None
        return value if not parsed.netloc else None
    except ValueError:
        return None


def inline(text, links=True):
    """Parse inline constructs while escaping every unrecognized character."""
    parts = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text) and text[i + 1] in r"\`*_{}[]()#+-.!|>":
            parts.append(html.escape(text[i + 1]))
            i += 2
            continue
        if text[i] == "`":
            run = len(text[i:]) - len(text[i:].lstrip("`"))
            marker = "`" * run
            end = text.find(marker, i + run)
            if end != -1:
                parts.append("<code>" + html.escape(text[i + run:end]) + "</code>")
                i = end + run
                continue
        if text.startswith("**", i):
            end = text.find("**", i + 2)
            if end != -1:
                parts.append("<strong>" + inline(text[i + 2:end], links) + "</strong>")
                i = end + 2
                continue
        if links and text[i] == "[":
            match = re.match(r"\[([^\]\n]+)\]\(([^\s()]+)\)", text[i:])
            if match:
                label = inline(match.group(1), links=False)
                url = safe_url(match.group(2))
                if url:
                    parts.append('<a href="' + html.escape(url, quote=True) + '">' + label + "</a>")
                else:
                    parts.append(label)
                i += match.end()
                continue
        parts.append(html.escape(text[i]))
        i += 1
    return "".join(parts)


def plain(text):
    return re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text).replace("**", "").replace("`", "")


def slug(text):
    value = re.sub(r"[^\w\-]+", "-", plain(text).lower(), flags=re.UNICODE).strip("-")
    return value or "section"


class Anchors:
    def __init__(self):
        self.used = set()

    def make(self, text, prefix=""):
        base = prefix + slug(text)
        value = base
        n = 2
        while value in self.used:
            value = base + "-" + str(n)
            n += 1
        self.used.add(value)
        return value


def table_cells(line):
    """Split table pipes except escaped pipes and pipes inside inline code."""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    cells, current = [], []
    marker = ""
    i = 0
    while i < len(line):
        if line[i] == "\\" and i + 1 < len(line):
            current.extend(line[i:i + 2])
            i += 2
            continue
        if line[i] == "`":
            run = len(line[i:]) - len(line[i:].lstrip("`"))
            ticks = "`" * run
            if not marker:
                marker = ticks
            elif marker == ticks:
                marker = ""
            current.append(ticks)
            i += run
            continue
        if line[i] == "|" and not marker:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(line[i])
        i += 1
    cells.append("".join(current).strip())
    return cells


def table_separator(line):
    cells = table_cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def markdown(source, anchors=None, prefix=""):
    """A deliberately small Markdown subset, not a full CommonMark parser."""
    anchors = anchors or Anchors()
    lines = source.splitlines()
    result = []
    i = 0

    def starts_block(pos):
        line = lines[pos]
        return (not line.strip() or HEADING.match(line) or FENCE.match(line)
                or LIST_ITEM.match(line) or line.lstrip().startswith(">")
                or (pos + 1 < len(lines) and "|" in line and table_separator(lines[pos + 1])))

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        fence = FENCE.match(line)
        if fence:
            delimiter = fence.group(1)
            language = fence.group(2).strip()
            code = []
            i += 1
            closing = re.compile(r"^ {0,3}" + re.escape(delimiter[0]) + "{" + str(len(delimiter)) + r",}\s*$")
            while i < len(lines) and not closing.match(lines[i]):
                code.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            label = '<div class="code-label">' + html.escape(language) + "</div>" if language else ""
            result.append(label + "<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
            continue
        heading = HEADING.match(line)
        if heading:
            level = max(2, len(heading.group(1)))
            title = heading.group(2)
            identifier = anchors.make(title, prefix)
            result.append(f'<h{level} id="{html.escape(identifier, quote=True)}">{inline(title)}</h{level}>')
            i += 1
            continue
        if i + 1 < len(lines) and "|" in line and table_separator(lines[i + 1]):
            header = table_cells(line)
            alignment = table_cells(lines[i + 1])
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip() and "|" in lines[i]:
                cells = table_cells(lines[i])
                cells = (cells + [""] * len(header))[:len(header)]
                rows.append(cells)
                i += 1

            def cells_html(cells, tag):
                values = []
                for col, cell in enumerate(cells):
                    align = alignment[col] if col < len(alignment) else ""
                    style = "center" if align.startswith(":") and align.endswith(":") else "right" if align.endswith(":") else "left"
                    values.append(f'<{tag} class="align-{style}">{inline(cell)}</{tag}>')
                return "".join(values)

            result.append('<div class="table-scroll"><table><thead><tr>' + cells_html(header, "th")
                          + "</tr></thead><tbody>" + "".join("<tr>" + cells_html(row, "td") + "</tr>" for row in rows)
                          + "</tbody></table></div>")
            continue
        if line.lstrip().startswith(">"):
            quotes = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                quotes.append(re.sub(r"^\s*> ?", "", lines[i], count=1))
                i += 1
            result.append("<blockquote>" + markdown("\n".join(quotes), anchors, prefix) + "</blockquote>")
            continue
        item = LIST_ITEM.match(line)
        if item:
            ordered = bool(item.group(2))
            tag = "ol" if ordered else "ul"
            start = ' start="' + item.group(2) + '"' if ordered and item.group(2) != "1" else ""
            items = []
            while i < len(lines):
                item = LIST_ITEM.match(lines[i])
                if not item or bool(item.group(2)) != ordered:
                    break
                content = [item.group(3)]
                i += 1
                while i < len(lines) and lines[i].startswith(("  ", "\t")) and not starts_block(i):
                    content.append(lines[i].strip())
                    i += 1
                items.append("<li>" + inline(" ".join(content)) + "</li>")
            result.append(f"<{tag}{start}>" + "".join(items) + f"</{tag}>")
            continue
        paragraph = [line.strip()]
        i += 1
        while i < len(lines) and not starts_block(i):
            paragraph.append(lines[i].strip())
            i += 1
        result.append("<p>" + inline(" ".join(paragraph)) + "</p>")
    return "\n".join(result)


def chapters(source):
    """Split on H2 outside code fences; H1 is the fallback chapter delimiter."""
    lines = source.splitlines()
    headings = []
    active = None
    for i, line in enumerate(lines):
        fence = FENCE.match(line)
        if active:
            if re.fullmatch(r" {0,3}" + re.escape(active[0]) + "{" + str(len(active)) + r",}\s*", line):
                active = None
            continue
        if fence:
            active = fence.group(1)
            continue
        heading = HEADING.match(line)
        if heading:
            headings.append((i, len(heading.group(1)), heading.group(2)))
    level = 2 if any(h[1] == 2 for h in headings) else 1
    boundaries = [h for h in headings if h[1] == level]
    if not boundaries:
        return [("深度内容", source)] if source.strip() else []
    result = []
    intro = "\n".join(lines[:boundaries[0][0]]).strip()
    # A document title alone is not a separate chapter.
    if intro and not (HEADING.fullmatch(intro) and "\n" not in intro):
        result.append(("阅读提示", intro))
    for index, (position, _, title) in enumerate(boundaries):
        end = boundaries[index + 1][0] if index + 1 < len(boundaries) else len(lines)
        result.append((title, "\n".join(lines[position + 1:end])))
    return result


class SourcePreviews:
    """Embed explicitly linked local sources so previews also work offline."""

    TEXT = {".txt", ".md", ".json"}
    IMAGES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}

    def __init__(self, workspace, anchors):
        self.workspace = workspace.resolve()
        self.anchors = anchors
        self.templates = {}

    def replace(self, fragment):
        def preview(match):
            url, label = html.unescape(match.group(1)), match.group(2)
            parsed = urlsplit(url)
            path = Path(unquote(parsed.path))
            if parsed.scheme or not parsed.path or path.suffix.lower() not in self.TEXT | self.IMAGES.keys():
                return match.group(0)
            path = (self.workspace / path).resolve()
            if not path.is_relative_to(self.workspace) or not path.is_file():
                return '<span class="source-unavailable">' + label + '（原文不可用）</span>'
            if path not in self.templates:
                if path.stat().st_size > 2_000_000:
                    return '<span class="source-unavailable">' + label + '（请准备较短选段）</span>'
                suffix = path.suffix.lower()
                if suffix in self.IMAGES:
                    data = base64.b64encode(path.read_bytes()).decode("ascii")
                    content = f'<img alt="原文图片" src="data:{self.IMAGES[suffix]};base64,{data}">'
                else:
                    text = path.read_text(encoding="utf-8-sig")
                    if suffix == ".json":
                        content = '<pre><code>' + html.escape(text) + '</code></pre>'
                    else:
                        blocks = []
                        for block in re.split(r"\n\s*\n", text.strip()):
                            location = re.match(r"^(\[[^\n]+\])\n", block)
                            caption = ""
                            if location:
                                caption = '<small class="source-location">' + html.escape(location.group(1)) + '</small>'
                                block = block[location.end():]
                            blocks.append('<div class="source-block">' + caption + '<p>' + html.escape(block) + '</p></div>')
                        content = "\n".join(blocks)
                identifier = self.anchors.make("source", "template-")
                self.templates[path] = (identifier, content)
            identifier = self.templates[path][0]
            panel = self.anchors.make("source", "panel-")
            return (f'<button type="button" class="source-toggle" data-template="{identifier}" '
                    f'data-panel="{panel}" aria-expanded="false">{label}</button>')

        return re.sub(r'<a href="([^"]+)">(.*?)</a>', preview, fragment, flags=re.DOTALL)

    def render_templates(self):
        return "\n".join(f'<template id="{identifier}"><div class="source-content">{content}</div></template>'
                         for identifier, content in self.templates.values())


def render_workspace(workspace, output=None):
    workspace = Path(workspace)
    sources = {}
    for filename in FILES:
        path = workspace / filename
        if path.is_file():
            sources[filename] = path.read_text(encoding="utf-8-sig")
    if not sources:
        raise ValueError("未找到阅读材料：请先准备 map.md、distillation.md、route.md 或 progress.md。")
    anchors = Anchors()
    anchors.used.update(("overview", "depth", "route", "progress", "session-guide", "session-heading",
                         "prompt-start", "prompt-continue", "prompt-resume", "copy-status"))
    title = "我的读书页"
    for line in sources.get("map.md", "").splitlines():
        heading = HEADING.match(line)
        if heading:
            title = plain(heading.group(2))
            break

    def body(filename, prefix):
        if filename not in sources or not sources[filename].strip():
            return '<p class="empty">尚未准备。后续阅读时补充。</p>'
        return markdown(sources[filename], anchors, prefix)

    nav = []
    depth = []
    for name, content in chapters(sources.get("distillation.md", "")):
        identifier = anchors.make(name, "chapter-")
        escaped_id = html.escape(identifier, quote=True)
        depth.append(f'<details class="chapter search-unit" id="{escaped_id}"><summary>{inline(name, links=False)}</summary>'
                     + '<div class="chapter-body">' + markdown(content, anchors, identifier + "-") + "</div></details>")
        nav.append(f'<a class="chapter-link" href="#{escaped_id}">{html.escape(plain(name))}</a>')
    if not depth:
        depth.append('<p class="empty search-unit">尚未准备。后续阅读时补充。</p>')
    values = {
        "TITLE": html.escape(title),
        "MAP": body("map.md", "map-"),
        "DEPTH": "\n".join(depth),
        "CHAPTER_NAV": "\n".join(nav),
        "ROUTE": body("route.md", "route-"),
        "PROGRESS": body("progress.md", "progress-"),
        "START_PROMPT": html.escape(f"$read-with-agent 请开始带读这个工作区：{workspace.resolve()}\n"
                                  "从记录的当前单元开始，一次一小段：先解释重点并展示关键原文，再等我讨论或实践。"),
        "CONTINUE_PROMPT": html.escape(f"$read-with-agent 继续带读这个工作区：{workspace.resolve()}\n"
                                     "读取已有进度，接上当前讨论或下一步。"),
        "RESUME_PROMPT": html.escape(f"$read-with-agent 继续带读这个工作区：{workspace.resolve()}\n"
                                   "先读取 map.md、route.md、progress.md，再按需读取当前部分的蒸馏和原文。"
                                   "采用最新记录，保留未答问题与真实理解状态，一次继续一小段。"),
    }
    previews = SourcePreviews(workspace, anchors)
    for key in ("MAP", "DEPTH", "ROUTE", "PROGRESS"):
        values[key] = previews.replace(values[key])
    values["SOURCE_TEMPLATES"] = previews.render_templates()
    template = Path(__file__).resolve().parent.parent / "assets" / "reader-template.html"
    page = re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: values[m.group(1)], template.read_text(encoding="utf-8"))
    output = Path(output) if output else workspace / "reader.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description="将阅读笔记生成离线 HTML 读书页（仅标准库）。")
    parser.add_argument("workspace", type=Path, help="包含阅读笔记的目录")
    parser.add_argument("--output", type=Path, help="输出 HTML 路径；默认阅读目录中的 reader.html")
    args = parser.parse_args(argv)
    try:
        output = render_workspace(args.workspace, args.output)
    except (OSError, UnicodeError, ValueError) as exc:
        print("生成失败：" + str(exc), file=sys.stderr)
        return 1
    print("已生成：" + str(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
