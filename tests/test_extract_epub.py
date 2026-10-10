import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "extract_epub.py"
SPEC = importlib.util.spec_from_file_location("extract_epub", SCRIPT)
EPUB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EPUB)


class ExtractEpubTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root / "book.epub"
        self.output = self.root / "prepared"

    def make_epub(self, first=None, href="Text/a.xhtml", metadata=None):
        metadata = metadata or '<dc:creator opf:role="aut">作者</dc:creator><dc:creator opf:role="bkp">制作者</dc:creator><dc:creator opf:role="aut">第二作者</dc:creator>'
        package = f'''<package xmlns="http://www.idpf.org/2007/opf" xmlns:opf="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/">
        <metadata><dc:title>测试书</dc:title>{metadata}</metadata>
        <manifest><item id="a" href="{href}" media-type="application/xhtml+xml"/><item id="b" href="Text/b.xhtml" media-type="application/xhtml+xml"/></manifest>
        <spine><itemref idref="b"/><itemref idref="a" linear="no"/></spine></package>'''
        with zipfile.ZipFile(self.input, "w") as archive:
            archive.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="OPS/package.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
            archive.writestr("OPS/package.opf", package)
            archive.writestr("OPS/Text/a.xhtml", first or '<html xmlns="http://www.w3.org/1999/xhtml"><body><h1>甲</h1><p>第一章正文</p></body></html>')
            archive.writestr("OPS/Text/b.xhtml", '<html><body><p>第二章正文</p></body></html>')

    def test_subdirectory_spine_order_metadata_and_source(self):
        self.make_epub()
        manifest = EPUB.prepare_epub(self.input, self.output)
        self.assertIn("第二章正文", (self.output / "0001.txt").read_text())
        self.assertIn("第一章正文", (self.output / "0002.txt").read_text())
        self.assertEqual([item["source"] for item in manifest["spine"]], ["OPS/Text/b.xhtml", "OPS/Text/a.xhtml"])
        self.assertEqual(manifest["spine"][1]["linear"], "no")
        creators = [item for item in manifest["metadata"] if item["name"] == "creator"]
        self.assertEqual([item["value"] for item in creators], ["作者", "制作者", "第二作者"])
        self.assertEqual(creators[1]["attributes"]["{http://www.idpf.org/2007/opf}role"], "bkp")
        self.assertEqual(manifest["source"]["sha256"], hashlib.sha256(self.input.read_bytes()).hexdigest())
        self.assertEqual(manifest["source"]["path"], str(self.input.resolve()))
        self.assertIn("未检测到", manifest["image_note"])
        self.assertEqual(json.loads((self.output / "manifest.json").read_text()), manifest)

    def test_ids_block_numbers_skipped_text_and_image_gaps(self):
        self.make_epub(first='''<!DOCTYPE html SYSTEM "https://invalid.example/unread.dtd"><html><head><title>不读取标题</title><script>危险头部</script></head><body><p id="p1">有用正文<script>危险脚本</script><style>危险样式</style>尾部<span id="inline">行内正文</span><img src="../Images/formula.png" alt="公式"/></p><p>后续正文</p><math><mi>x</mi></math></body></html>''')
        manifest = EPUB.prepare_epub(self.input, self.output)
        text = (self.output / "0002.txt").read_text()
        for forbidden in ("不读取标题", "危险头部", "危险脚本", "危险样式"):
            self.assertNotIn(forbidden, text)
        self.assertIn("尾部", text)
        self.assertIn('[source_id="p1"]', text)
        self.assertIn('[source_id="inline"]', text)
        self.assertIn("[block:0001]", text)
        self.assertIn("图片或图形未提取", text)
        self.assertIn("MathML 公式未提取", text)
        entry = manifest["spine"][1]
        self.assertEqual(entry["source_ids"], [{"id": "p1", "block": 1}, {"id": "inline", "block": 1}])
        self.assertEqual(entry["images"][0]["references"], ["../Images/formula.png"])
        self.assertEqual(entry["images"][0]["status"], "not_extracted")
        self.assertIn("非纸书页码", manifest["location_note"])

    def test_rejects_nonempty_output_without_changes(self):
        self.make_epub()
        self.output.mkdir()
        retained = self.output / "keep.txt"
        retained.write_text("keep")
        result = subprocess.run([sys.executable, str(SCRIPT), str(self.input), str(self.output)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不会覆盖", result.stderr)
        self.assertEqual(retained.read_text(), "keep")
        self.assertEqual(list(self.output.iterdir()), [retained])

    def test_damaged_zip_reports_clear_nonzero(self):
        self.input.write_bytes(b"not an epub")
        result = subprocess.run([sys.executable, str(SCRIPT), str(self.input), str(self.output)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EPUB 提取失败", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(self.output.exists())

    def test_invalid_xml_leaves_no_output(self):
        self.make_epub(first="<html><body>")
        with self.assertRaisesRegex(EPUB.EpubError, "XML 无法解析"):
            EPUB.prepare_epub(self.input, self.output)
        self.assertFalse(self.output.exists())

    def test_rejects_root_escape_external_paths_and_entities(self):
        for href in ("../../outside.xhtml", "%2E%2E/%2E%2E/outside.xhtml", "https://example.com/a.xhtml", "http://[", "/etc/passwd"):
            with self.subTest(href=href):
                self.make_epub(href=href)
                with self.assertRaises(EPUB.EpubError):
                    EPUB.prepare_epub(self.input, self.output)
                self.assertFalse(self.output.exists())
        self.make_epub(first='<!DOCTYPE html [<!ENTITY secret SYSTEM "file:///etc/passwd">]><html><body>&secret;</body></html>')
        with self.assertRaisesRegex(EPUB.EpubError, "实体声明"):
            EPUB.prepare_epub(self.input, self.output)


if __name__ == "__main__":
    unittest.main()
