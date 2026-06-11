# Agent知识包 Schema

Agent知识包输出位置：

```text
graphify-out/tuolin-agent-packs/
├── manifest.json
├── products/
├── competitors/
├── content/
├── video/
├── evidence/
└── readable/
```

Codex抽取适配层：

```text
graphify-out/tuolin-agent-packs/extraction/
├── tasks.json
└── results/
    └── <task_id>.json
```

`tasks.json` 由脚本生成，Codex负责执行理解任务。`results/` 由Codex写入结构化抽取结果，随后通过 `apply_extraction_results.py` 合并进知识包。

`manifest.json` 必须包含 `build_partitions`，每个构建分区至少包含：

- `name`
- `type`
- `status`
- `status_label`
- `raw_path`
- `pending_extraction_count`
- `pending_result_count`
- `review_claim_count`

构建分区状态只允许：`not_built`、`ready`、`needs_update`、`pending_extraction`、`review_required`。

`tasks.json` 中每个任务必须包含 `partition_name`。`results/<task_id>.json` 必须包含匹配的 `partition_name` 和 `applied`；未合并结果为 `applied: false`，合并成功后改为 `applied: true`。

五类知识包：

- `product_pack`：产品事实、规格、卖点、场景、禁用场景、客服话术、产品变体。
- `competitor_pack`：竞品、差异点、证据、推断项。
- `content_pack`：对外内容生成素材和约束，不存固定成稿。
- `video_pack`：视频素材、视觉描述、分镜素材、即梦 prompt 片段，不存最终完整即梦 prompt。
- `evidence_pack`：证据来源、置信度、复核状态、冲突项。

知识包是编译产物，不人工直接编辑。
