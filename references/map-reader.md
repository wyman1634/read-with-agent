# 地图式阅读页：可选数据格式

地图式页面是 `render_reader.py` 的可选模式，适用于已经准备好结构化地图与讲解记录的工作区。它不会自动读取整本书、判断完成状态或生成知识点；先按 `technical.md` 核对来源、章节及历史，再由 Agent 准备和维护数据。未完成的蒸馏、缺图与不确定性如实说明。普通 Markdown 工作区无需这些文件，继续使用默认渲染器。

最小可运行例子在 [examples/map-first](../examples/map-first/)。

## 准备与生成

1. 准备 `distillation.md`：每段要放进地图的历史讲解使用 `## 已介绍：标题` 等包含中文冒号的二级标题；标题冒号后的文字需与记录的 `title` 一致。正文可按普通规则链接本地文字或图片。
2. 在工作区创建 `study-map-data.json`，按下文提供章节、知识点、历史和计数。记录“已带读”必须有实际讲解依据；部分讲过标“进行中”，读者明确暂缓时标“经确认暂缓”，不把讲解等同读者掌握。
3. 创建 `reader-navigation.txt`，内容为 `map-first`，再运行 `python3 <技能目录>/scripts/render_reader.py <本书工作区>`。打开生成的 `reader.html`；读取和点击不会写回进度。继续带读后同步更新数据、记录和下一入口再重新生成。

## JSON 字段

- `title`、`description`：书名和简短介绍。`current` 包含 `point_id`、`label`、`chapter`，指向实际下一入口。
- `topics[] → chapters[] → modules[] → points[]`：按原书顺序排列。章节 `id` 为整数，模块有 `id`、`title`；知识点 `id` 使用数字和点组成的唯一编号，如 `1.1.2`，并提供 `title`、`status` 和 `history_ids`。
- 每个知识点的 `status` 为 `待带读`、`进行中`、`已带读` 或 `经确认暂缓`；`counted` 默认为 `true`，可对小结设为 `false`。`goal`、`items`、`related` 可用于讲解目标、细项和其他知识点的 ID。`source` 是工作区内相对路径；启用 `point_source_previews: true` 后可以在页面内展开支持的文字或图片。
- `history[]` 每项有唯一 `id`、`title` 和可选 `display_status`、`reader_link`；每条记录必须且只能出现在一个知识点的 `history_ids`。例如另一个关联章节可用 `related` 指向核心讲解，避免重复计数。历史段落、章节进度和读者理解应保持各自口径。
- `counts.by_status` 必须和所有 `counted` 知识点一致，至少包含已带读、进行中、待带读；存在暂缓时还需提供 `经确认暂缓`。小结不计入进度。渲染器会拒绝编号重复、历史缺失或重复归属、当前位置不存在及计数不一致的数据。
- 可选 `progress_mode: "history-led"` 以历史讲解段数和章节状态分别展示进度；`map_note` 解释统计口径。不要把历史段数包装成去重后的知识点数。

历史来源默认是 `distillation.md`。若用 `history_file` 指向工作区内派生的历史副本，可同时保存 `history_source_sha256`（原始 `distillation.md` 的 SHA-256）和 `history_snapshot_sha256`（副本 SHA-256）；相应文件变动后渲染器会要求先核对并同步。指纹只检测变化，不证明历史归属或内容语义正确。完成核对后更新两个指纹，保留原始记录。

输入是自包含的本地工作区；正式发布示例前删除个人路径、阅读记录和受版权保护的原文。页面和数据的浏览器交互仍需实际验证；自动化结构测试无法证明整书已蒸馏或读者已理解。
