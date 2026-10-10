# read-with-agent · 读书搭子

先建立书籍全貌，再读关键原文，并与 Agent 一起深入理解。适用于技术、实用、哲学思想、小说和混合类型。支持全文、节选或仅书名；资料不足时交付明确范围的导读。

默认以 HTML 展示，Markdown 保存内容与跨会话进度。技术书依据实际练习，思想书依据论证，文学依据文本讨论；没有统一考试或自动“已掌握”百分比。

## 安装与使用

需要支持文件型 Skills 的 Agent。HTML 渲染器需要 Python 3，仅使用标准库。

将本目录复制到 Codex 的 `~/.codex/skills/read-with-agent`，重新开始会话后使用：

```text
用 $read-with-agent 带我读这本书。我想理解作者的思路，
再用于分析实际问题。这是原文／文件／书名。
```

继续时提供原阅读工作区路径并说“继续”。其他 Agent 可按自己的 Skill 安装约定使用；首版验证环境为 Codex，未验证其他产品兼容性。不同类型的验证范围与首轮观察见 `evals/results.md`。

## 内容与边界

- 入口：[SKILL.md](SKILL.md)，类型指导按需加载。
- 来源、蒸馏、原文路线、讨论记录保存在本书工作区，默认不写回技能目录。
- `python3 scripts/extract_epub.py <原书.epub> <本书工作区>/source` 按阅读顺序准备 EPUB 文本和定位，图片与公式缺口单列。
- `python3 scripts/render_reader.py <本书工作区>` 从四份 Markdown 生成离线页面。
- 工作区内的 TXT、Markdown、JSON 和常见原图链接会变成点击展开的原文框，正文随 HTML 内嵌，离线可用。仅嵌入明确链接的材料；每项上限 2 MB，超出时准备较短选段。HTML 含所选原文，发布前检查授权与隐私。
- 渲染器支持常用 Markdown 子集；暂不支持图片、脚注、数学公式或嵌套列表。公式可保留为代码文本，复杂内容需 Agent 选择其他展示方式。
- 网页是阅读界面；会话与 Markdown 记录构成续读依据。网页点击不证明学习完成。
- 技能帮助建立理解路径，真实学习效果需要读者试用反馈。

## 验证

```bash
python3 -m unittest discover -s tests -v
```

真实测试请求见 [evals/evals.json](evals/evals.json)。有／无 Skill 的对照以实际产物和行为判断，不能据此证明整书掌握或长期学习收益。

## 参考与许可

本项目指令与渲染代码重新编写。方法参考：

- [Deep Reader](https://github.com/tronghieu/agent-skills/tree/main/skills/deep-reader)：分轮阅读与章节定位。
- [Deep Book Guide](https://github.com/pengpeng810/deep-book-guide-skill)：导读与原文路线。
- [DeepRead](https://github.com/alirezarezvani/claude-skills/tree/main/research/deepread)：理解断点与迁移检查。

采用 MIT 许可，见 [LICENSE](LICENSE)。请仅公开适合分享的示例；原始书籍与个人学习记录保留本地。
