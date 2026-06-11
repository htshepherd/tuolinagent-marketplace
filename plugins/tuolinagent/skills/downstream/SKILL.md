---
name: downstream
description: Placeholder boundaries for future Tuolin downstream business agents. Use only to explain how YouTube, LinkedIn, outreach, follow-up, and video-script agents should consume Agent knowledge packs without reading raw files directly.
---

# Downstream Agent Boundaries

首版不实现下游业务生成，只保留接入边界。

未来下游 Agent 必须优先读取：

```text
graphify-out/tuolin-agent-packs/
```

规则：

- 不默认读取真实 `raw/`。
- 不直接消费完整 Graphify `graph.json`。
- 内容生成可以使用待复核素材，但必须保留复核标记。
- 内部问答仍只能使用 `confirmed` 内容。
