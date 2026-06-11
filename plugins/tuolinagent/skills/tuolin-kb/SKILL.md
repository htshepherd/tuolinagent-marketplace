---
name: tuolin-kb
description: Manage Tianjin Tuolin's local enterprise knowledge base. Use when the user asks in Chinese to build, update, inspect, query, review, or write back Tuolin product knowledge packs from local raw materials.
---

# Tuolin KB

Use this skill for Tuolin local knowledge-base work.

## Default Behavior

普通员工默认使用中文自然语言。只保留三个显式命令：

```text
/tuolin-kb build
/tuolin-kb update
/tuolin-kb status
```

Natural-language routing:

- “整理一下拓霖知识库”：默认推荐一个最有业务价值的下一步，说明为什么、做完能得到什么，并等待确认；不要默认输出完整七分区状态报表。
- “整理[产品名称]资料”、“整理[公司/标准/市场]资料”：展示目标构建分区计划并等待确认；确认后只构建该分区。
- “从头构建拓霖知识库”、“从零构建拓霖知识库”、“重新构建拓霖知识库”、“全量重建拓霖知识库”：先拆成明确的构建分区队列并等待确认；不得直接无边界扫描 raw。
- “更新一下知识库”：先展示构建分区状态和需要更新的分区；等待用户选择目标分区或确认分区队列。
- “查看四个产品的知识包状态”、“查看知识库状态”：执行 status，返回构建分区和产品状态。
- 产品问答：先读 `graphify-out/tuolin-agent-packs/manifest.json`，再读对应产品知识包。
- “有哪些内容需要我复核”：读取对应 `evidence_pack`。
- “继续看资料”、“继续看剩下的资料”、“继续看图片报告和视频”：推荐目标构建分区，说明这一步会继续查看图片、报告或视频画面，并等待确认；确认后只处理该分区任务。
- “整理成可用资料”、“把已识别内容整理进资料”：推荐目标构建分区，说明整理后哪些资料会变得可用、哪些内容需要确认，并等待确认；确认后只合并该分区结果。
- “准备Codex抽取任务”：高级/调试表达，生成 `graphify-out/tuolin-agent-packs/extraction/tasks.json`；普通用户不要使用这个术语。

Build/update before execution must show a short partition-scoped plan and wait for user confirmation.

Every user-facing recommendation that needs confirmation must include one copyable natural-language reply. Use wording like:

```text
你可以直接回复：确认，继续看标准资料。
```

or:

```text
你可以直接回复：确认，先把石英纤维隔热带整理成可用资料。
```

When there is nothing left to organize, switch to using existing materials and include one copyable question example:

```text
你可以直接问：石英纤维隔热带适合哪些客户场景？
```

### Partition-Scoped Build Meaning

“整理一下拓霖知识库”不是直接执行全库构建，也不是状态报表。它在本项目中只有一个含义：

1. 读取当前知识库状态。
2. 按业务价值推荐一个下一步。
3. 说明为什么推荐、做完能得到什么。
4. 固定说明不会修改核心资料，也不会对外发布内容。
5. 等待用户确认。

Only when the user asks “查看知识库状态” should you show the full seven-partition status list and counts.

Do not ask the user to choose between multiple build types when they say “从头构建”. Treat “从头构建” or “全量重建” as a request to propose a partition queue, then wait for confirmation.

Even when the user says “全量重建”, do not run an unbounded full raw scan. Split it into these build partitions:

- 陶瓷纤维隔热带
- 石英纤维隔热带
- 玄武岩纤维隔热带
- 高硅氧纤维隔热带
- 公司
- 标准
- 市场

Product build partitions must include the concrete product name. Missing product raw directories remain `not_built` and must not generate core-only fallback packs.

Do not suggest “重新设计知识库体系” during a build request. Redesigning the schema, directory layout, product fields, or review workflow is a PRD/design task, not a build task.

Do not delete, move, or clear `graphify-out/` just because the user says “从头构建”. Only discuss deletion/cleanup if the user explicitly says “清空输出”、“删除graphify-out”、“干净重建”, or similar. For deletion/cleanup, show the exact cleanup plan and wait for explicit confirmation.

Expected response when the user says “整理一下拓霖知识库”:

```text
我看了当前资料状态。石英纤维隔热带最适合先整理，因为它已有基础资料，整理后最快能用于回答客户问题、写产品介绍和整理销售话术。

公司、标准、市场也有资料可继续整理；陶瓷、玄武岩、高硅氧还需要先补齐产品素材。

我建议下一步：先把石英纤维隔热带整理成可用资料。

整理后，你会得到：
- 一批可以用于回答客户问题、写产品介绍和整理销售话术的石英纤维隔热带信息
- 需要你判断的内容会单独列出来，不会混进确定答案

这一步不会修改核心资料，也不会对外发布内容。

你可以直接回复：确认，先把石英纤维隔热带整理成可用资料。

请确认是否开始整理。
```

Expected response when the user says “整理石英纤维隔热带资料”:

```text
我会只处理石英纤维隔热带资料。

如果已有识别出的内容，我会先把它整理成可用资料；如果还没有可整理内容，我会继续看这个产品剩下的图片、报告或视频画面。

整理后，你会看到：
- 哪些信息已经可以用于回答客户问题、写产品介绍和整理销售话术
- 哪些内容还需要你确认
- 下一步建议做什么

这一步不会修改核心资料，也不会对外发布内容。

你可以直接回复：确认，开始整理石英纤维隔热带资料。

请确认是否开始。
```

Expected response after build finishes:

```text
基础知识库已构建完成。下一步建议先把已识别出的内容整理成可用资料；如果没有已识别内容，我会建议继续看剩下的资料。
```

Do not continue with material analysis automatically after build or update. Build/update only scan raw materials, compile packs, index video frames, and generate the material analysis task list.

Continuing to inspect source material must be explicitly triggered by natural language:

- If the user says “继续看资料” without a build partition, recommend one build partition by business value, not by raw task count alone.
- Explain that Codex will continue looking at pictures, reports, or video frames for that partition.
- If no build partition has pending extraction tasks, say there is no new material to look at and switch to using existing materials.
- If the selected build partition status is `needs_update`, stop and ask the user to update that partition first.

Organizing recognized content into usable materials must also be explicitly triggered by natural language:

- If the user says “整理成可用资料” without a build partition, recommend one build partition by business value.
- Explain what will become usable and what will still need human confirmation.
- If no build partition has unapplied results, say there is no recognized content waiting to be organized and suggest continuing to look at remaining materials or using existing materials.
- When applying results, pass the confirmed partition to `python3 scripts/tuolin_kb/apply_extraction_results.py --partition <构建分区名称>`.
- Successful application marks result files as `applied: true` and refreshes `manifest.json`.

Only stop for user confirmation when:

- writing to `raw/00_知识库核心资料/`;
- deleting, moving, or clearing files;
- publishing external content;
- changing configuration, schema, or product scope;
- a claim is blocked by review policy and needs human judgment.

Do not tell ordinary users to say “请处理待抽取任务”. That is an internal implementation detail.

Never expose internal field names to ordinary users. Use these labels in user-facing text:

- `tasks.json` -> “素材分析清单”
- `extraction/results` -> “素材分析结果”
- `evidence_pack` -> “复核清单”
- `video_pack` -> “视频素材信息”
- `product_pack` -> “产品资料”
- `manifest.json` -> “产品状态清单”
- `inferred` -> “待确认”
- `uncertain` -> “不确定”
- `pending` -> “待处理”
- `confirmed` -> “已确认”
- `review_required` -> “需要人工确认”
- `claim` -> “内容”
- `raw/00_知识库核心资料/` -> “核心资料”
- `core_patch` -> “修改预览”

Do not narrate internal retrieval mechanics to ordinary users. Avoid phrases like:

- “我按 tuolin-kb 问答规则查...”
- “我按问答优先级先看 manifest 和知识包...”
- “我读取 evidence_pack 里的待复核 claim...”
- “我查 video_pack...”
- “只回答 confirmed 内容...”
- “我按 tuolin-kb 的复核回写流程...”
- “先定位第1条对应的待复核 claim...”
- “写入 raw/00_知识库核心资料/...”
- “最后更新复核状态并校验...”

Use outcome-oriented user language instead:

- “我会先用已整理好的产品资料回答。”
- “这部分属于刚分析出的素材信息，还需要你确认。”
- “我只列出需要你判断的内容。”
- “我不会直接翻原始文件，除非你明确要求。”
- “这条信息已确认，可以作为内部问答依据。”
- “这条信息还待确认，暂时不能当作确定事实。”

For write-back requests, never say that content will be written immediately. The safe user-facing wording is:

- “我会先生成一份修改预览，给你确认。”
- “你确认后，我再把这条内容加入核心资料。”
- “现在不会直接改核心资料。”

Current implementation note: core knowledge write-back is implemented as a HITL flow. If the user asks to write back, first generate a modification preview with `core_patch.py --preview`; only write after explicit human confirmation with the confirmation token. Do not claim the write happened during preview.

## Scripts

Run from repository root:

```bash
python3 scripts/validate_project.py
python3 scripts/tuolin_kb/build.py
python3 scripts/tuolin_kb/update.py
python3 scripts/tuolin_kb/recommend_next_step.py
python3 scripts/tuolin_kb/status.py
python3 scripts/tuolin_kb/prepare_extraction_tasks.py
python3 scripts/tuolin_kb/extract_video_keyframes.py
python3 scripts/tuolin_kb/apply_extraction_results.py
python3 scripts/tuolin_kb/review_claims.py
python3 scripts/tuolin_kb/core_patch.py --preview --claim-index 1
python3 scripts/tuolin_kb/query.py "石英纤维隔热带适合室内排烟管吗？"
```

## Codex Extraction Adapter

Python脚本不直接调用Codex模型。脚本只负责生成素材分析清单：

```text
graphify-out/tuolin-agent-packs/extraction/tasks.json
```

Codex只在用户明确要求分析某个构建分区素材并确认后，读取该分区清单中的 `source_path`、`prompt` 和 `result_schema`，理解图片、报告、视频关键帧后，把结构化结果写入：

```text
graphify-out/tuolin-agent-packs/extraction/results/<task_id>.json
```

再运行：

```bash
python3 scripts/tuolin_kb/apply_extraction_results.py --partition <构建分区名称>
```

抽取结果会更新对应 `video_pack` 或全库知识域包。raw层资料默认准确；只有资料冲突、文件无法解析、Codex明确无法判断或用户要求复核时，才写入复核清单。

公司介绍、标准、市场、竞品、潜在客户、检测报告默认作为已确认知识沉淀。PDF正文必须先由MinerU转换为raw原目录同名Markdown；Codex读取Markdown正文，PDF原件保留为证据附件。缺少同名Markdown且MinerU不可用时，不要让Codex根据PDF文件名编造具体事实。

## Query Policy

Query priority:

1. `graphify-out/tuolin-agent-packs/manifest.json`
2. Product-level Agent knowledge packs
3. Graphify `query/explain/path`
4. Ask the user to supplement core knowledge or raw materials

Do not read `raw/` by default unless the user explicitly asks.

Internal Q&A only uses `confirmed` claims. `inferred`, `uncertain`, and `pending` claims become review prompts.

Content generation may use review-pending material only as draft input and must preserve review marks.

## References

- `references/agent-pack-schema.md`
- `references/review-policy.md`
- `references/raw-layout.md`
