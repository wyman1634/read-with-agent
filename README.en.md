# read-with-agent · A reading companion

[简体中文](README.md) | **English**

Build a map of a book, distill its important ideas, then return to key passages for deeper reading with an AI agent. Works with technical, practical, philosophical, literary, and mixed books. Use a full text, an excerpt, or just a title; the guide stays within the material actually available.

By default, an offline HTML page presents the guide, while Markdown files preserve content and progress across conversations. You can also read entirely in chat. Work through one unit at a time and repair specific misunderstandings as they arise. Technical reading focuses on application, philosophical reading on arguments, and literary reading on textual evidence. “I understand” is recorded separately from demonstrated understanding.

## Install and start

Requires an agent that supports file-based Skills. The bundled scripts require Python 3.9 or later and use only the standard library. Codex is the currently validated environment; compatibility with other products has not been verified.

[SKILL.md](SKILL.md) is the entry point. Guidance for book types, resuming, and visuals is loaded when needed. The skill instructions, bundled sample, and current HTML interface labels are in Chinese; ask the agent to explain in your preferred language.

For a first installation, clone into Codex's skill directory:

```bash
git clone https://github.com/wyman1634/read-with-agent.git \
  ~/.codex/skills/read-with-agent
```

Alternatively, download the project and copy its directory to that location. Start a new conversation and ask:

```text
Use $read-with-agent to guide me through this book. I want to understand
the author's reasoning and apply it to real problems.
Here is the text, file, or title.
```

The page offers copyable prompts to start, continue, or resume in a new conversation. In the same conversation, say “continue,” “next section,” “I don't understand,” or “try another example.” In a new conversation, use the resume prompt containing the reading workspace path. When switching machines, copy the entire workspace and use its new path.

## Explore a complete example

[List assignment and shallow copying](examples/list-copy/map.md) is a project-authored, three-section mini-text released under this project's MIT license. It demonstrates the workflow: source scope and book map → distilled ideas and passage route → a reading unit → misunderstanding and repair → saved state → resuming in a new conversation.

- [Original passage on shallow copying](examples/list-copy/source/02-shallow-copy.txt) and [distilled notes with a simple diagram](examples/list-copy/distillation.md): compare the source with supplementary explanation.
- [Guided reading dialogue](examples/list-copy/history/unit-2.md): explicitly simulated, showing why modifying a copied list can still affect the original.
- [Current progress](examples/list-copy/progress.md): stops at the simulated reader's self-reported understanding, with a prediction task unanswered. This is where the next conversation should resume.

From the project root, copy the example into a separate temporary workspace and generate its page:

```bash
demo_workspace="$(mktemp -d "${TMPDIR:-/tmp}/read-with-agent-demo.XXXXXX")"
cp -R examples/list-copy/. "$demo_workspace/"
python3 scripts/render_reader.py "$demo_workspace"
```

Open the resulting `reader.html` in a browser. Expand **“2. 浅复制” (Shallow copying)** to view the diagram and original passage. Copy the prompt under **“新对话接着读” (Resume in a new conversation)** into a new conversation. The agent should continue with the complete prediction example, keeping understanding unverified until there is evidence. The simulated dialogue demonstrates the workflow, not learning effectiveness. Generated example HTML contains the local machine's path and is excluded from the published files.

## Materials and gaps

| Material | Current approach | Handling gaps |
| --- | --- | --- |
| Markdown / TXT | Read directly, preserving section and paragraph locations | Read long texts in batches; distinguish available, read, and analyzed scope |
| EPUB | `scripts/extract_epub.py` extracts text and locations in reading order | List missing images and image-based formulas; revisit the original when relevant |
| PDF with a text layer | Use the host's PDF tools or `pdftotext -layout` | Check code, tables, formulas, and page numbers against the original; no PDF extractor is bundled |
| Scanned PDF | Use the host's OCR or inspect page images | If OCR is unavailable, read accessible pages or request the relevant excerpt; do not claim full-text analysis |
| Title / table of contents only | Verify the edition, find available contents and samples, and build a provisional map and route | Leave unavailable sections unverified; claims about the author's arguments require source passages |

Extract an EPUB with the following command. A nonempty output directory is rejected by default:

```bash
python3 scripts/extract_epub.py <book.epub> <reading-workspace>/source
```

## Workspace and reading page

Reading data lives in a separate workspace. The installed skill directory contains reusable resources:

```text
<reading-workspace>/
  source/          Original passages and extracted text
  map.md           Book identity, scope, and structural map
  distillation.md  Distilled ideas grounded in checked material
  route.md         Key passages and reading route
  progress.md      Current state, evidence, and next step
  preferences.md  Optional reader-specific preferences
  history/         Discussion records consulted as needed
  visuals/         Optional diagrams and independent demos
  reader.html      Regenerable reading interface
```

```bash
python3 scripts/render_reader.py <reading-workspace>
```

The renderer reads the map, distilled notes, route, progress, and preferences if present. To resume, the agent first reads the short progress summary and preferences, then follows pointers to the relevant passages. History is consulted as needed. Page clicks do not update understanding status; Markdown records and actual discussion support continuity.

## Visuals and offline delivery

Technical reading defaults to text and simple architecture diagrams. When an example already explains a single field, continue reading. Add a small amount of interaction only when manipulating state helps explain a change. Selection, cost, and delivery rules are in [references/visuals.md](references/visuals.md).

The current reading page directly displays monospace text diagrams in code blocks. Explicit links to TXT, Markdown, JSON, PNG / JPG / JPEG / WebP files inside the workspace become expandable, embedded content available offline. Each embedded file is limited to 2 MB. Link an agent-created diagram with a regular Markdown link, such as `[Agent diagram: topic](visuals/topic/diagram.png)`, to distinguish it from a figure in the original text.

Mermaid is displayed as code; SVG is not embedded. Markdown image syntax, footnotes, mathematical typesetting, and nested lists are not yet supported. Independent interactive HTML opens through a link, so include its files when sharing. Only embedded content travels with a standalone reading page. Resuming still requires the original workspace, not just the HTML file.

## Validation and limits

```bash
python3 -m unittest discover -s tests -v
```

Tests cover extraction, rendering, offline source content, and resume prompts. Evaluation prompts are in [evals/evals.json](evals/evals.json); executed cases and observations are in [evals/results.md](evals/results.md). The example makes the delivery workflow reproducible. These checks do not establish whole-book mastery or long-term learning benefits; feedback from real readers is still needed.

HTML includes the passages and records explicitly selected for display. Check permissions and privacy before publishing them. Keep private books and personal reading records local.

## References and license

This project's instructions and rendering code were written anew. Methodological references:

- [Deep Reader](https://github.com/tronghieu/agent-skills/tree/main/skills/deep-reader): reading in stages and locating chapters.
- [Deep Book Guide](https://github.com/pengpeng810/deep-book-guide-skill): book orientation and passage routes.
- [DeepRead](https://github.com/alirezarezvani/claude-skills/tree/main/research/deepread): identifying understanding gaps and checking transfer.

Released under the MIT license. See [LICENSE](LICENSE).
