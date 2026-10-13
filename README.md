# read-with-agent · 读书搭子

先建立书籍全貌，蒸馏重要内容，再挑选关键原文，与 Agent 一起深入阅读。适用于技术、实用、哲学思想、小说和混合类型；支持全文、节选或仅书名，按实际来源范围交付导读。

默认以离线 HTML 展示，Markdown 保存内容与跨会话进度，也可选择只在聊天带读。一次推进一个阅读单元，遇到误解就针对断点补充。技术书看实际应用，思想书看论证，文学看文本讨论；读者说“懂了”和已有证据理解分别记录。

## 安装与开始

需要支持文件型 Skills 的 Agent；附带脚本需要 Python 3.9 或更新版本，仅使用标准库。当前验证环境为 Codex，其他产品兼容性尚未验证。

技能入口为 [SKILL.md](SKILL.md)，类型指导、续读和图形规则按需加载。

首次安装可直接克隆到 Codex 的技能目录：

```bash
git clone https://github.com/wyman1634/read-with-agent.git \
  ~/.codex/skills/read-with-agent
```

也可以下载后将本目录复制到该路径。重新开始会话后使用：

```text
用 $read-with-agent 带我读这本书。我想理解作者的思路，
再用于分析实际问题。这是原文／文件／书名。
```

页面提供可复制的开始、继续、新会话续读指令。同一对话可以直接说“继续”“下一节”“没懂”或“换个例子”；新对话使用带工作区路径的续读指令。换机器时复制整个书籍工作区并使用新路径。

## 先看一个完整示例

[列表赋值与浅复制](examples/list-copy/map.md) 是项目自编的三节短教材，按本项目 MIT 许可分享。它展示完整流程：材料范围与地图 → 蒸馏与原文路线 → 一次带读 → 误解修正 → 保存状态 → 新会话续读。

- [原文：浅复制](examples/list-copy/source/02-shallow-copy.txt) 与 [蒸馏、简图](examples/list-copy/distillation.md)：核对原文和补充解释的关系。
- [带读对话](examples/list-copy/history/unit-2.md)：明确标为模拟，包含“复制了列表，为什么修改还会影响原列表”的断点与修正。
- [当前进度](examples/list-copy/progress.md)：停在模拟读者自述理解，尚未回答下一道预测题；续读应从这里接上。

在项目根目录运行下面的命令，复制到独立临时工作区并生成页面：

```bash
demo_workspace="$(mktemp -d "${TMPDIR:-/tmp}/read-with-agent-demo.XXXXXX")"
cp -R examples/list-copy/. "$demo_workspace/"
python3 scripts/render_reader.py "$demo_workspace"
```

用浏览器打开输出的 `reader.html`，展开“2. 浅复制”，查看简图和原文；复制“新对话接着读”指令到新会话。预期接着解释／讨论完整预测例子，保留待验证状态。模拟对话用于展示工作方式，不是读者效果评测；示例生成的 HTML 含当前机器路径，不纳入发布文件。

## 材料支持与缺口

| 材料 | 当前方式 | 缺口处理 |
| --- | --- | --- |
| Markdown／TXT | 直接读取并保留章节、段落定位 | 长材料分批读；标明实际已读与已分析范围 |
| EPUB | `scripts/extract_epub.py` 按阅读顺序提取正文与定位 | 图片、图片公式等缺口单列，相关单元回查原书 |
| 有文本层的 PDF | 使用宿主已有 PDF 工具或 `pdftotext -layout` | 回查代码、表格、公式及页码；本项目不附带 PDF 提取器 |
| 扫描 PDF | 依赖宿主 OCR 或按页查看原图 | OCR 不可用时，先读可查看的部分或请求对应选段；不声称已分析全文 |
| 仅书名／目录 | 核实版本、查找可用目录与试读，形成暂定地图和路线 | 缺少正文处保留待核对，作者具体论证需要原文支持 |

EPUB 提取命令如下，非空输出目录默认拒绝覆盖：

```bash
python3 scripts/extract_epub.py <原书.epub> <本书工作区>/source
```

## 工作区与页面

阅读数据保存在独立工作区，技能目录只存可复用资源：

```text
<本书工作区>/
  source/          原文与提取文本
  map.md           身份、范围与结构地图
  distillation.md  已核对内容的蒸馏
  route.md         关键原文与阅读路线
  progress.md      当前状态、证据和下一步
  preferences.md  可选，当前读者的差异化偏好
  history/         按需回查的讨论记录
  visuals/         可选，独立图形与演示
  reader.html      可重新生成的界面
```

```bash
python3 scripts/render_reader.py <本书工作区>
```

渲染器读取地图、蒸馏、路线、进度及存在的偏好文件。续读先读简短进度和偏好，再按指针加载当前原文；历史按需回查。网页点击不会写回理解状态，Markdown 与真实讨论是续读依据。

## 图形与离线交付

技术带读默认文字＋简洁架构图；单个字段用例子就能讲清时直接推进，状态变化确需操作时才加少量交互。具体选择、成本与交付规则见 [references/visuals.md](references/visuals.md)。

当前读书页直接显示代码块中的等宽文本简图。工作区内明确链接的 TXT、Markdown、JSON、PNG／JPG／JPEG／WebP 会成为点击展开的内容，内嵌后可离线查看，每个文件上限 2 MB。Agent 示意图使用 `[Agent 示意图：主题](visuals/topic/diagram.png)` 这样的普通链接，区分原书图与补充图。

Mermaid 会显示为代码，SVG 不内嵌；普通 Markdown 图片语法、脚注、数学排版与嵌套列表尚未支持。独立交互 HTML 通过链接打开，分享时要带上演示文件；只有内嵌的内容随单个读书页保存。续读始终需要原工作区，不能只带 HTML。

## 验证与边界

```bash
python3 -m unittest discover -s tests -v
```

测试覆盖提取、渲染、离线来源与续读入口。真实测试请求见 [evals/evals.json](evals/evals.json)，已执行的范围与观察见 [evals/results.md](evals/results.md)。示例可复现交付流程；这些检查不能证明整书掌握或长期学习收益，仍需要真实读者反馈。

HTML 含明确选入的原文和记录。公开分享前检查对应材料的授权与隐私；私人原书和个人记录留在本地。

## 参考与许可

本项目指令与渲染代码重新编写。方法参考：

- [Deep Reader](https://github.com/tronghieu/agent-skills/tree/main/skills/deep-reader)：分轮阅读与章节定位。
- [Deep Book Guide](https://github.com/pengpeng810/deep-book-guide-skill)：导读与原文路线。
- [DeepRead](https://github.com/alirezarezvani/claude-skills/tree/main/research/deepread)：理解断点与迁移检查。

采用 MIT 许可，见 [LICENSE](LICENSE)。
