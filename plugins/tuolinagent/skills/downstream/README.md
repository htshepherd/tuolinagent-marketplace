# 下游Agent占位模块

首版只实现知识库基础设施。下游 YouTube、LinkedIn、开发信、跟进信、视频脚本 Agent 暂不实现完整业务生成。

未来下游 Agent 必须优先消费：

```text
graphify-out/tuolin-agent-packs/
```

边界规则：

- 不直接消费完整 Graphify `graph.json`。
- 不默认读取真实 `raw/`。
- 不直接修改 Agent 知识包或 `graphify-out/graph.json`。
- 内容生成可以使用待复核素材作为草稿输入，但必须保留复核标记。
- 首版占位模块不输出最终可发布内容，只描述未来接入边界。
