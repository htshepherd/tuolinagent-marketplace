from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import ProjectConfig, load_project_config


CN_TZ = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class LocalGraphOutput:
    graph_path: Path
    html_path: Path
    report_path: Path
    node_count: int
    edge_count: int
    review_count: int


def write_local_graph_outputs(root: Path | str = ".", config: ProjectConfig | None = None) -> LocalGraphOutput:
    root_path = Path(root).resolve()
    cfg = config or load_project_config(root_path)
    output_dir = root_path / cfg.output_dir
    packs_dir = root_path / cfg.packs_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    graph = build_local_graph(root_path, cfg)
    graph_path = output_dir / "graph.json"
    html_path = output_dir / "graph.html"
    report_path = output_dir / "GRAPH_REPORT.md"

    graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(render_html(graph, packs_dir), encoding="utf-8")
    report_path.write_text(render_report(graph), encoding="utf-8")
    write_wiki_outputs(output_dir / "wiki", graph, packs_dir)

    return LocalGraphOutput(
        graph_path=graph_path,
        html_path=html_path,
        report_path=report_path,
        node_count=len(graph["nodes"]),
        edge_count=len(graph["edges"]),
        review_count=sum(1 for node in graph["nodes"] if node.get("type") == "review_item"),
    )


def build_local_graph(root: Path, config: ProjectConfig) -> dict[str, Any]:
    packs_dir = root / config.packs_dir
    manifest_path = packs_dir / "manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {"products": []}

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    edge_keys: set[tuple[str, str, str]] = set()

    def add_node(node_id: str, label: str, node_type: str, **payload: Any) -> None:
        if node_id in node_ids:
            return
        node_ids.add(node_id)
        nodes.append({"id": node_id, "label": label, "type": node_type, **payload})

    def add_edge(source: str, target: str, relation: str, **payload: Any) -> None:
        key = (source, target, relation)
        if source not in node_ids or target not in node_ids or key in edge_keys:
            return
        edge_keys.add(key)
        edges.append({"source": source, "target": target, "relation": relation, **payload})

    add_node(
        "kb:tuolin",
        "拓霖本地知识库",
        "knowledge_base",
        status="available",
        status_label="可用",
    )

    for item in manifest.get("products", []):
        if item.get("status") == "not_built":
            continue
        product = item["name"]
        product_id = product_node_id(product)
        add_node(
            product_id,
            product,
            "product",
            status=item.get("status", ""),
            status_label=item.get("status_label", ""),
            asset_status=item.get("asset_status", ""),
            asset_status_label=item.get("asset_status_label", ""),
            variants=item.get("variants", []),
        )
        add_edge("kb:tuolin", product_id, "包含产品", confidence="confirmed", status_label="已确认")

        product_pack = read_pack(packs_dir, "products", product)
        add_product_facts(add_node, add_edge, product_id, product_pack)
        add_video_assets(add_node, add_edge, product_id, read_pack(packs_dir, "video", product))
        add_review_claims(add_node, add_edge, product_id, read_pack(packs_dir, "evidence", product))

    add_domain_packs(add_node, add_edge, packs_dir)

    return {
        "schema_version": "1.0",
        "generated_by": "tuolinagent",
        "generated_at": datetime.now(CN_TZ).isoformat(timespec="seconds"),
        "compiler": "tuolin-local-business-graph",
        "graph_type": "agent_pack_projection",
        "llm_api_required": False,
        "source": config.packs_dir,
        "trust_policy": {
            "raw_materials_default_confidence": "confirmed",
            "review_required_when": ["资料冲突", "文件无法解析", "Codex明确无法判断", "用户明确要求复核"],
        },
        "nodes": nodes,
        "edges": edges,
    }


def add_product_facts(add_node: Any, add_edge: Any, product_id: str, pack: dict[str, Any]) -> None:
    facts = pack.get("facts", {})
    for field in ["品牌", "材料", "市场名称", "颜色", "现货规格", "单重", "极限耐温", "长期使用温度", "隔热效果", "核心定位"]:
        value = facts.get(field)
        if not value:
            continue
        node_id = fact_node_id(product_id, field, str(value))
        add_node(node_id, f"{field}: {value}", "product_fact", status="confirmed", status_label="已确认")
        add_edge(product_id, node_id, field, confidence="confirmed", status_label="已确认")

    for field in ["核心卖点", "适用场景", "禁用场景", "产品变体"]:
        for value in facts.get(field, []) or []:
            node_id = fact_node_id(product_id, field, str(value))
            add_node(node_id, str(value), field_to_node_type(field), status="confirmed", status_label="已确认")
            add_edge(product_id, node_id, field, confidence="confirmed", status_label="已确认")

    for field, node_type in [("检测报告路径", "report_asset"), ("图片文件路径", "image_asset"), ("视频文件路径", "video_asset")]:
        for path in facts.get(field, []) or []:
            node_id = asset_node_id(path)
            status = "confirmed"
            status_label = "已确认"
            add_node(node_id, Path(path).name, node_type, source_path=path, status=status, status_label=status_label)
            add_edge(product_id, node_id, field.removesuffix("路径"), confidence="confirmed", status_label="已确认")


def add_video_assets(add_node: Any, add_edge: Any, product_id: str, pack: dict[str, Any]) -> None:
    for video in pack.get("videos", []):
        video_path = video.get("source_path", "")
        if not video_path:
            continue
        video_id = asset_node_id(video_path)
        add_node(video_id, Path(video_path).name, "video_asset", source_path=video_path, status="available", status_label="可用素材")
        add_edge(product_id, video_id, "视频素材", confidence="confirmed", status_label="已确认")
        for keyframe in video.get("keyframes", []):
            frame_path = keyframe.get("frame_path", "")
            if not frame_path:
                continue
            frame_id = asset_node_id(frame_path)
            review_required = bool(keyframe.get("review_required", True))
            add_node(
                frame_id,
                keyframe.get("detected_scene") or Path(frame_path).name,
                "video_keyframe",
                source_path=frame_path,
                description=keyframe.get("visual_description", ""),
                status="review_required" if review_required else "confirmed",
                status_label="需要人工确认" if review_required else "已确认",
            )
            add_edge(video_id, frame_id, "关键帧", confidence=keyframe.get("confidence", "inferred"), status_label="需要人工确认")


def add_review_claims(add_node: Any, add_edge: Any, product_id: str, pack: dict[str, Any]) -> None:
    for claim in pack.get("review_required_claims", []):
        task_id = claim.get("task_id") or str(abs(hash(claim.get("claim", ""))))
        node_id = f"review:{task_id}"
        add_node(
            node_id,
            summarize(claim.get("claim", "")),
            "review_item",
            status="review_required",
            status_label="需要人工确认",
            source_path=claim.get("source_path", ""),
            source_type=claim.get("source_type", ""),
            description=claim.get("claim", ""),
        )
        add_edge(product_id, node_id, "待确认内容", confidence=claim.get("confidence", "inferred"), status_label="需要人工确认")


def add_domain_packs(add_node: Any, add_edge: Any, packs_dir: Path) -> None:
    company = read_json(packs_dir / "company" / "company.json") if (packs_dir / "company" / "company.json").exists() else {}
    standards = read_json(packs_dir / "standards" / "standards.json") if (packs_dir / "standards" / "standards.json").exists() else {}
    market = read_json(packs_dir / "market" / "market.json") if (packs_dir / "market" / "market.json").exists() else {}

    if company:
        company_id = "domain:company"
        add_node(company_id, "公司", "company", status="confirmed", status_label="已确认")
        add_edge("kb:tuolin", company_id, "包含知识域", confidence="confirmed", status_label="已确认")
        for asset in company.get("assets", []):
            add_domain_asset(add_node, add_edge, company_id, asset, "公司资料")
        add_domain_review_items(add_node, add_edge, company_id, company)

    if standards:
        standards_id = "domain:standards"
        add_node(standards_id, "标准", "standards", status="confirmed", status_label="已确认")
        add_edge("kb:tuolin", standards_id, "包含知识域", confidence="confirmed", status_label="已确认")
        for standard in standards.get("standards", []):
            node_id = asset_node_id(standard.get("source_path", ""))
            add_node(
                node_id,
                standard.get("standard_name") or standard.get("title", ""),
                "standard",
                source_path=standard.get("source_path", ""),
                category=standard.get("category", ""),
                summary=standard.get("summary", ""),
                status="confirmed",
                status_label="已确认",
            )
            add_edge(standards_id, node_id, "标准文件", confidence="confirmed", status_label="已确认")
        add_domain_review_items(add_node, add_edge, standards_id, standards)

    if market:
        market_id = "domain:market"
        add_node(market_id, "市场", "market", status="confirmed", status_label="已确认")
        add_edge("kb:tuolin", market_id, "包含知识域", confidence="confirmed", status_label="已确认")
        for asset in market.get("market_overview", []):
            add_domain_asset(add_node, add_edge, market_id, asset, "市场现状")
        for competitor in market.get("competitors", []):
            competitor_id = f"competitor:{competitor.get('name', '')}"
            add_node(competitor_id, competitor.get("name", ""), "competitor", status="confirmed", status_label="已确认")
            add_edge(market_id, competitor_id, "竞争对手", confidence="confirmed", status_label="已确认")
            for asset in competitor.get("assets", []):
                add_domain_asset(add_node, add_edge, competitor_id, asset, "竞品资料")
        for prospect in market.get("prospects", []):
            prospect_id = f"prospect:{prospect.get('name', '')}"
            add_node(prospect_id, prospect.get("name", ""), "prospect", status="confirmed", status_label="已确认")
            add_edge(market_id, prospect_id, "潜在客户", confidence="confirmed", status_label="已确认")
            for asset in prospect.get("assets", []):
                add_domain_asset(add_node, add_edge, prospect_id, asset, "潜客资料")
        add_domain_review_items(add_node, add_edge, market_id, market)


def add_domain_asset(add_node: Any, add_edge: Any, parent_id: str, asset: dict[str, Any], relation: str) -> None:
    path = asset.get("source_path", "")
    if not path:
        return
    node_id = asset_node_id(path)
    add_node(
        node_id,
        asset.get("title") or Path(path).name,
        asset.get("source_type", "domain_asset"),
        source_path=path,
        category=asset.get("category", ""),
        file_type=asset.get("file_type", ""),
        summary=asset.get("summary", ""),
        status="confirmed",
        status_label="已确认",
    )
    add_edge(parent_id, node_id, relation, confidence="confirmed", status_label="已确认")


def add_domain_review_items(add_node: Any, add_edge: Any, parent_id: str, pack: dict[str, Any]) -> None:
    for item in pack.get("review_required_items", []):
        task_id = item.get("task_id") or str(abs(hash(item.get("claim", ""))))
        node_id = f"review:{pack.get('domain', 'domain')}:{task_id}"
        add_node(
            node_id,
            summarize(item.get("claim", "")),
            "review_item",
            status="review_required",
            status_label="需要人工确认",
            source_path=item.get("source_path", ""),
            source_type=item.get("source_type", ""),
            description=item.get("claim", ""),
        )
        add_edge(parent_id, node_id, "待确认内容", confidence=item.get("confidence", "uncertain"), status_label="需要人工确认")


def render_html(graph: dict[str, Any], packs_dir: Path) -> str:
    products = [node for node in graph["nodes"] if node["type"] == "product"]
    company_nodes = [node for node in graph["nodes"] if node["type"] == "company_asset"]
    standard_nodes = [node for node in graph["nodes"] if node["type"] == "standard"]
    competitor_nodes = [node for node in graph["nodes"] if node["type"] == "competitor"]
    prospect_nodes = [node for node in graph["nodes"] if node["type"] == "prospect"]
    review_nodes = [node for node in graph["nodes"] if node["type"] == "review_item"]
    report_nodes = [node for node in graph["nodes"] if node["type"] == "report_asset"]
    video_frames = [node for node in graph["nodes"] if node["type"] == "video_keyframe"]

    product_cards = "\n".join(render_product_card(product, graph) for product in products)
    company_items = "\n".join(render_domain_item(node) for node in company_nodes) or "<li>暂无公司资料。</li>"
    standard_items = "\n".join(render_domain_item(node) for node in standard_nodes) or "<li>暂无标准资料。</li>"
    market_items = "\n".join(render_domain_item(node) for node in [*competitor_nodes, *prospect_nodes]) or "<li>暂无市场资料。</li>"
    review_items = "\n".join(render_review_item(node) for node in review_nodes[:30]) or "<li>当前没有需要人工确认的内容。</li>"
    frame_items = "\n".join(render_frame_item(node) for node in video_frames[:24]) or "<li>暂无视频关键帧。</li>"
    graph_json = json.dumps(graph, ensure_ascii=False).replace("</", "<\\/")
    packs_path = escape(packs_dir.relative_to(packs_dir.parents[1]).as_posix())
    html_text = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>拓霖本地知识库图谱</title>
  <style>
    :root {
      --ink: #1e252b;
      --muted: #65717c;
      --paper: #f4f6f3;
      --panel: #ffffff;
      --line: #d9ded7;
      --steel: #31576f;
      --oxide: #b8502e;
      --moss: #5b7a42;
      --amber: #a86f10;
      --graph-bg: #111820;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: "Avenir Next", "Helvetica Neue", Arial, sans-serif; color: var(--ink); background: var(--paper); }
    header { padding: 26px 32px 20px; background: #fbfcfa; border-bottom: 1px solid var(--line); }
    h1 { margin: 0 0 8px; font-size: 28px; font-weight: 720; letter-spacing: 0; }
    h2 { margin: 0 0 14px; font-size: 18px; letter-spacing: 0; }
    main { max-width: 1380px; margin: 0 auto; padding: 22px; }
    button, input, select { font: inherit; }
    .label { color: var(--muted); font-size: 13px; }
    .summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 14px; }
    .metric, .card, section, .graph-shell, .detail-panel { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }
    .metric { padding: 14px 16px; }
    .metric strong { display: block; font-size: 26px; color: var(--steel); }
    .graph-shell { overflow: hidden; margin-bottom: 18px; }
    .toolbar { display: grid; grid-template-columns: minmax(220px, 1fr) 190px auto auto; gap: 10px; padding: 12px; border-bottom: 1px solid var(--line); background: #fbfcfa; }
    .toolbar input, .toolbar select { min-width: 0; border: 1px solid var(--line); border-radius: 6px; padding: 9px 10px; background: #fff; color: var(--ink); }
    .toolbar button { border: 1px solid #b9c2ba; background: #fff; color: var(--ink); border-radius: 6px; padding: 9px 12px; cursor: pointer; }
    .toolbar button:hover { border-color: var(--steel); color: var(--steel); }
    .search-box { position: relative; min-width: 0; }
    .search-box input { width: 100%; }
    .search-results { position: absolute; z-index: 20; top: calc(100% + 6px); left: 0; right: 0; max-height: 330px; overflow: auto; background: #fff; border: 1px solid #c9d1ca; border-radius: 8px; box-shadow: 0 16px 44px rgba(29,39,47,.18); padding: 6px; display: none; }
    .search-results.open { display: block; }
    .search-result { width: 100%; border: 0; background: transparent; text-align: left; display: grid; grid-template-columns: 86px minmax(0, 1fr); gap: 8px; padding: 8px 9px; border-radius: 6px; cursor: pointer; color: var(--ink); }
    .search-result:hover, .search-result.active { background: #eef3ee; color: var(--ink); }
    .search-kind { color: var(--steel); font-size: 12px; white-space: nowrap; }
    .search-main { min-width: 0; }
    .search-title { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .search-path { color: var(--muted); font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-top: 2px; }
    .graph-layout { display: grid; grid-template-columns: minmax(0, 1fr) 330px; min-height: 650px; }
    .canvas-wrap { position: relative; background: radial-gradient(circle at 20% 10%, #1f2b35 0, var(--graph-bg) 42%, #0d1218 100%); min-height: 650px; }
    #graphCanvas { display: block; width: 100%; height: 650px; touch-action: none; cursor: grab; }
    #graphCanvas:active { cursor: grabbing; }
    .legend { position: absolute; left: 14px; bottom: 14px; display: flex; flex-wrap: wrap; gap: 8px; max-width: calc(100% - 28px); }
    .legend span { display: inline-flex; align-items: center; gap: 6px; padding: 5px 8px; border-radius: 999px; background: rgba(255,255,255,.9); color: #25313a; font-size: 12px; }
    .legend i { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
    .detail-panel { border: 0; border-left: 1px solid var(--line); border-radius: 0; padding: 18px; overflow: auto; background: #fff; }
    .detail-panel h2 { margin-bottom: 6px; line-height: 1.25; }
    .detail-row { padding: 10px 0; border-bottom: 1px solid #edf0ec; }
    .detail-row:last-child { border-bottom: 0; }
    .detail-key { display: block; color: var(--muted); font-size: 12px; margin-bottom: 4px; }
    .detail-value { overflow-wrap: anywhere; line-height: 1.5; }
    .relation-list { list-style: none; padding: 0; margin: 8px 0 0; }
    .relation-list li { margin: 6px 0; padding: 7px 9px; background: #f6f8f5; border-radius: 6px; font-size: 13px; }
    .status { display: inline-block; padding: 3px 8px; border-radius: 999px; background: #edf2ff; color: #2446a8; font-size: 12px; }
    .status.review { background: #fff0df; color: #8a3b15; }
    .node-label { pointer-events: none; user-select: none; font-size: 11px; fill: #eef4f5; paint-order: stroke; stroke: rgba(8,12,16,.72); stroke-width: 3px; stroke-linejoin: round; }
    .edge { stroke: rgba(218,226,225,.34); stroke-width: 1.2; }
    .edge.review { stroke: rgba(230,132,69,.72); stroke-width: 1.6; stroke-dasharray: 5 4; }
    .node circle { stroke: rgba(255,255,255,.82); stroke-width: 1.5; cursor: pointer; }
    .node.selected circle { stroke: #ffffff; stroke-width: 4; filter: drop-shadow(0 0 10px rgba(255,255,255,.55)); }
    .node.dim, .edge.dim, .node-label.dim { opacity: .12; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 14px; }
    .card { padding: 16px; }
    section { padding: 18px; margin-top: 18px; }
    li { margin: 8px 0; line-height: 1.55; }
    code { background: #eef1ed; padding: 2px 5px; border-radius: 4px; }
    .path { color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }
    @media (max-width: 900px) {
      .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .toolbar { grid-template-columns: 1fr; }
      .graph-layout { grid-template-columns: 1fr; }
      .detail-panel { border-left: 0; border-top: 1px solid var(--line); }
      main { padding: 14px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>拓霖本地知识库图谱</h1>
    <div class="label">由 Agent 知识包生成，不需要 LLM API key。更新时间：__GENERATED_AT__</div>
  </header>
  <main>
    <div class="summary">
      <div class="metric"><span class="label">产品</span><strong>__PRODUCT_COUNT__</strong></div>
      <div class="metric"><span class="label">标准</span><strong>__STANDARD_COUNT__</strong></div>
      <div class="metric"><span class="label">图谱节点</span><strong>__NODE_COUNT__</strong></div>
      <div class="metric"><span class="label">关系</span><strong>__EDGE_COUNT__</strong></div>
    </div>
    <section class="graph-shell" aria-label="交互式知识图谱">
      <div class="toolbar">
        <div class="search-box">
          <input id="graphSearch" type="search" placeholder="搜索产品、资料、来源或待确认内容" autocomplete="off">
          <div id="searchResults" class="search-results"></div>
        </div>
        <select id="typeFilter" aria-label="按节点类型筛选"></select>
        <button id="focusReview" type="button">待确认</button>
        <button id="resetGraph" type="button">重置</button>
      </div>
      <div class="graph-layout">
        <div class="canvas-wrap">
          <svg id="graphCanvas" role="img" aria-label="知识库节点关系图"></svg>
          <div class="legend" id="graphLegend"></div>
        </div>
        <aside class="detail-panel" id="nodeDetail">
          <h2>选择一个节点</h2>
          <div class="label">点击图谱中的节点，查看它的来源、状态和关联关系。</div>
        </aside>
      </div>
    </section>
    <section>
      <h2>资料信任规则</h2>
      <p>raw 层由企业主动放入，默认作为准确资料沉淀。只有资料冲突、文件无法解析、Codex 明确无法判断，或用户要求复核时，才进入人工确认。</p>
    </section>
    <section>
      <h2>产品状态</h2>
      <div class="grid">__PRODUCT_CARDS__</div>
    </section>
    <section>
      <h2>公司资料</h2>
      <ul>__COMPANY_ITEMS__</ul>
    </section>
    <section>
      <h2>标准资料</h2>
      <ul>__STANDARD_ITEMS__</ul>
    </section>
    <section>
      <h2>市场资料</h2>
      <ul>__MARKET_ITEMS__</ul>
    </section>
    <section>
      <h2>需要人工确认的内容</h2>
      <ul>__REVIEW_ITEMS__</ul>
    </section>
    <section>
      <h2>视频关键帧素材</h2>
      <ul>__FRAME_ITEMS__</ul>
    </section>
    <section>
      <h2>输出位置</h2>
      <p>图谱数据：<code>graphify-out/graph.json</code>；Agent 知识包：<code>__PACKS_PATH__</code>；检测报告素材数：__REPORT_COUNT__。</p>
    </section>
  </main>
  <script id="graph-data" type="application/json">__GRAPH_JSON__</script>
  <script>
    const graph = JSON.parse(document.getElementById('graph-data').textContent);
    const svg = document.getElementById('graphCanvas');
    const detail = document.getElementById('nodeDetail');
    const search = document.getElementById('graphSearch');
    const typeFilter = document.getElementById('typeFilter');
    const searchResults = document.getElementById('searchResults');
    const legend = document.getElementById('graphLegend');
    const nodes = graph.nodes.map((node, index) => ({ ...node, index, visible: true }));
    const byId = new Map(nodes.map(node => [node.id, node]));
    const edges = graph.edges
      .map(edge => ({ ...edge, sourceNode: byId.get(edge.source), targetNode: byId.get(edge.target), visible: true }))
      .filter(edge => edge.sourceNode && edge.targetNode);
    const colorByType = {
      knowledge_base: '#d8e7ec',
      product: '#58a6c7',
      product_fact: '#7fb069',
      selling_point: '#6fa45a',
      scenario: '#8ba65d',
      forbidden_scenario: '#d47a53',
      report_asset: '#c8953d',
      image_asset: '#b887d7',
      video_asset: '#4f8f9f',
      video_keyframe: '#65b8b0',
      company: '#6d91c2',
      company_asset: '#5b7fa3',
      standards: '#9a7a3a',
      standard: '#b59346',
      market: '#a66d4c',
      market_asset: '#a97960',
      competitor: '#c07a57',
      prospect: '#d08b63',
      review_item: '#e2632f'
    };
    const typeLabels = {
      knowledge_base: '知识库',
      product: '产品',
      product_fact: '产品事实',
      selling_point: '卖点',
      scenario: '适用场景',
      forbidden_scenario: '禁用场景',
      report_asset: '报告',
      image_asset: '图片',
      video_asset: '视频',
      video_keyframe: '视频关键帧',
      company: '公司',
      company_asset: '公司资料',
      standards: '标准域',
      standard: '标准',
      market: '市场域',
      market_asset: '市场资料',
      competitor: '竞争对手',
      prospect: '潜在客户',
      review_item: '待确认'
    };
    let selectedNode = null;
    let width = 1000;
    let height = 650;
    let alpha = 1;
    let dragging = null;
    let pointerOffset = { x: 0, y: 0 };
    let resultNodes = [];
    let activeResultIndex = -1;

    function initPositions() {
      resize();
      const groups = [...new Set(nodes.map(node => node.type))];
      nodes.forEach((node, index) => {
        const groupIndex = Math.max(0, groups.indexOf(node.type));
        const angle = (groupIndex / Math.max(1, groups.length)) * Math.PI * 2 + index * 0.09;
        const radius = node.type === 'knowledge_base' ? 0 : Math.min(width, height) * (0.18 + (index % 5) * 0.035);
        node.x = width / 2 + Math.cos(angle) * radius;
        node.y = height / 2 + Math.sin(angle) * radius;
        node.vx = 0;
        node.vy = 0;
      });
    }

    function resize() {
      const rect = svg.getBoundingClientRect();
      width = Math.max(520, rect.width || 1000);
      height = Math.max(520, rect.height || 650);
      svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    }

    function radius(node) {
      if (node.type === 'knowledge_base') return 16;
      if (node.type === 'product') return 15;
      if (node.type === 'review_item') return 12;
      if (node.type.includes('asset') || node.type === 'video_keyframe') return 9;
      return 8;
    }

    function visibleNodes() {
      return nodes.filter(node => node.visible);
    }

    function tick() {
      const active = visibleNodes();
      for (const edge of edges) {
        if (!edge.visible) continue;
        const sx = edge.sourceNode.x;
        const sy = edge.sourceNode.y;
        const tx = edge.targetNode.x;
        const ty = edge.targetNode.y;
        const dx = tx - sx;
        const dy = ty - sy;
        const distance = Math.max(1, Math.hypot(dx, dy));
        const target = edge.sourceNode.type === 'knowledge_base' ? 170 : 105;
        const force = (distance - target) * 0.0022 * alpha;
        const fx = dx / distance * force;
        const fy = dy / distance * force;
        if (edge.sourceNode !== dragging) {
          edge.sourceNode.vx += fx;
          edge.sourceNode.vy += fy;
        }
        if (edge.targetNode !== dragging) {
          edge.targetNode.vx -= fx;
          edge.targetNode.vy -= fy;
        }
      }
      for (let i = 0; i < active.length; i += 1) {
        for (let j = i + 1; j < active.length; j += 1) {
          const a = active[i];
          const b = active[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const distance = Math.max(3, Math.hypot(dx, dy));
          const force = 90 / (distance * distance) * alpha;
          const fx = dx / distance * force;
          const fy = dy / distance * force;
          if (a !== dragging) {
            a.vx -= fx;
            a.vy -= fy;
          }
          if (b !== dragging) {
            b.vx += fx;
            b.vy += fy;
          }
        }
      }
      for (const node of active) {
        if (node === dragging) continue;
        node.vx += (width / 2 - node.x) * 0.0008 * alpha;
        node.vy += (height / 2 - node.y) * 0.0008 * alpha;
        node.vx *= 0.86;
        node.vy *= 0.86;
        node.x = Math.max(24, Math.min(width - 24, node.x + node.vx));
        node.y = Math.max(24, Math.min(height - 24, node.y + node.vy));
      }
      alpha = Math.max(0.03, alpha * 0.985);
      draw();
      requestAnimationFrame(tick);
    }

    function draw() {
      const edgeMarkup = edges.map(edge => {
        const dim = selectedNode && edge.sourceNode !== selectedNode && edge.targetNode !== selectedNode ? ' dim' : '';
        const review = edge.status_label === '需要人工确认' || edge.confidence === 'uncertain' ? ' review' : '';
        const hidden = edge.visible ? '' : ' style="display:none"';
        return `<line class="edge${review}${dim}" x1="${edge.sourceNode.x}" y1="${edge.sourceNode.y}" x2="${edge.targetNode.x}" y2="${edge.targetNode.y}"${hidden}></line>`;
      }).join('');
      const nodeMarkup = nodes.map(node => {
        const fill = colorByType[node.type] || '#aeb9c0';
        const hidden = node.visible ? '' : ' style="display:none"';
        const dim = selectedNode && node !== selectedNode && !isNeighbor(node, selectedNode) ? ' dim' : '';
        const selected = node === selectedNode ? ' selected' : '';
        const label = escapeHtml(shortLabel(node.label));
        return `<g class="node${selected}${dim}" data-id="${escapeAttr(node.id)}" transform="translate(${node.x},${node.y})"${hidden}>
          <circle r="${radius(node)}" fill="${fill}"></circle>
          <text class="node-label${dim}" y="${radius(node) + 13}" text-anchor="middle">${label}</text>
        </g>`;
      }).join('');
      svg.innerHTML = `<g>${edgeMarkup}</g><g>${nodeMarkup}</g>`;
    }

    function isNeighbor(node, target) {
      return edges.some(edge => edge.visible && ((edge.sourceNode === node && edge.targetNode === target) || (edge.targetNode === node && edge.sourceNode === target)));
    }

    function shortLabel(label) {
      const text = String(label || '');
      return text.length > 18 ? text.slice(0, 17) + '…' : text;
    }

    function selectNode(node) {
      selectedNode = node;
      renderDetail(node);
      alpha = 0.55;
      draw();
    }

    function renderDetail(node) {
      const relations = edges
        .filter(edge => edge.sourceNode === node || edge.targetNode === node)
        .map(edge => {
          const other = edge.sourceNode === node ? edge.targetNode : edge.sourceNode;
          return `<li>${escapeHtml(edge.relation || '关联')} → ${escapeHtml(other.label || other.id)} <span class="label">${escapeHtml(edge.status_label || edge.confidence || '')}</span></li>`;
        })
        .join('') || '<li>暂无关联关系。</li>';
      const statusClass = node.status === 'review_required' ? 'status review' : 'status';
      detail.innerHTML = `
        <h2>${escapeHtml(node.label || node.id)}</h2>
        <div><span class="${statusClass}">${escapeHtml(node.status_label || node.status || '未标记')}</span></div>
        ${detailRow('节点类型', typeLabels[node.type] || node.type)}
        ${detailRow('来源路径', node.source_path || '')}
        ${detailRow('描述', node.description || node.summary || '')}
        ${detailRow('分类', node.category || '')}
        ${detailRow('文件类型', node.file_type || '')}
        <div class="detail-row"><span class="detail-key">关联关系</span><ul class="relation-list">${relations}</ul></div>
      `;
    }

    function detailRow(key, value) {
      if (!value) return '';
      return `<div class="detail-row"><span class="detail-key">${escapeHtml(key)}</span><div class="detail-value">${escapeHtml(value)}</div></div>`;
    }

    function applyFilter() {
      const type = typeFilter.value;
      nodes.forEach(node => {
        node.visible = !type || node.type === type || node.type === 'knowledge_base';
      });
      edges.forEach(edge => {
        edge.visible = edge.sourceNode.visible && edge.targetNode.visible;
      });
      selectedNode = null;
      detail.innerHTML = '<h2>选择一个节点</h2><div class="label">点击图谱中的节点，查看它的来源、状态和关联关系。</div>';
      alpha = 0.8;
      draw();
    }

    function focusNode(node) {
      nodes.forEach(item => item.visible = item === node || isNeighbor(item, node) || item.type === 'knowledge_base');
      edges.forEach(edge => edge.visible = edge.sourceNode.visible && edge.targetNode.visible);
      hideSearchResults();
      selectNode(node);
    }

    function resetGraph() {
      nodes.forEach(node => node.visible = true);
      edges.forEach(edge => edge.visible = true);
      typeFilter.value = '';
      search.value = '';
      hideSearchResults();
      selectedNode = null;
      detail.innerHTML = '<h2>选择一个节点</h2><div class="label">点击图谱中的节点，查看它的来源、状态和关联关系。</div>';
      initPositions();
      alpha = 1;
      draw();
    }

    function populateControls() {
      const types = [...new Set(nodes.map(node => node.type))].sort((a, b) => (typeLabels[a] || a).localeCompare(typeLabels[b] || b, 'zh-CN'));
      typeFilter.innerHTML = '<option value="">全部节点类型</option>' + types.map(type => `<option value="${escapeAttr(type)}">${escapeHtml(typeLabels[type] || type)}</option>`).join('');
      const legendTypes = ['product', 'product_fact', 'company_asset', 'standard', 'competitor', 'prospect', 'video_keyframe', 'review_item'];
      legend.innerHTML = legendTypes.map(type => `<span><i style="background:${colorByType[type] || '#aeb9c0'}"></i>${escapeHtml(typeLabels[type] || type)}</span>`).join('');
    }

    function searchableText(node) {
      return [
        node.label,
        node.id,
        typeLabels[node.type] || node.type,
        node.source_path,
        node.summary,
        node.description,
        node.category,
        node.status_label
      ].filter(Boolean).join(' ').toLowerCase();
    }

    function scoreNode(node, query) {
      const label = String(node.label || '').toLowerCase();
      const source = String(node.source_path || '').toLowerCase();
      const text = searchableText(node);
      if (!query) return -1;
      if (label === query) return 1000;
      if (label.startsWith(query)) return 800 - Math.min(label.length, 120);
      if (label.includes(query)) return 600 - label.indexOf(query);
      if (source.includes(query)) return 420 - source.indexOf(query);
      if (text.includes(query)) return 240 - text.indexOf(query);
      return -1;
    }

    function updateSearchResults() {
      const query = search.value.trim().toLowerCase();
      if (!query) {
        hideSearchResults();
        return;
      }
      resultNodes = nodes
        .map(node => ({ node, score: scoreNode(node, query) }))
        .filter(item => item.score >= 0)
        .sort((a, b) => b.score - a.score || String(a.node.label || '').localeCompare(String(b.node.label || ''), 'zh-CN'))
        .slice(0, 8)
        .map(item => item.node);
      activeResultIndex = resultNodes.length ? 0 : -1;
      renderSearchResults();
    }

    function renderSearchResults() {
      if (!resultNodes.length) {
        searchResults.innerHTML = '<div class="search-result"><span class="search-kind">无结果</span><span class="search-main"><span class="search-title">没有匹配节点</span></span></div>';
        searchResults.classList.add('open');
        return;
      }
      searchResults.innerHTML = resultNodes.map((node, index) => `
        <button type="button" class="search-result${index === activeResultIndex ? ' active' : ''}" data-index="${index}">
          <span class="search-kind">${escapeHtml(typeLabels[node.type] || node.type)}</span>
          <span class="search-main">
            <span class="search-title">${escapeHtml(node.label || node.id)}</span>
            <span class="search-path">${escapeHtml(node.source_path || node.status_label || '')}</span>
          </span>
        </button>
      `).join('');
      searchResults.classList.add('open');
    }

    function hideSearchResults() {
      resultNodes = [];
      activeResultIndex = -1;
      searchResults.classList.remove('open');
      searchResults.innerHTML = '';
    }

    function selectSearchResult(index) {
      const node = resultNodes[index];
      if (!node) return;
      search.value = node.label || node.id;
      focusNode(node);
    }

    function nodeFromPoint(event) {
      const element = event.target.closest ? event.target.closest('.node') : null;
      return element ? byId.get(element.dataset.id) : null;
    }

    function svgPoint(event) {
      const rect = svg.getBoundingClientRect();
      return {
        x: (event.clientX - rect.left) * width / rect.width,
        y: (event.clientY - rect.top) * height / rect.height
      };
    }

    svg.addEventListener('pointerdown', event => {
      const node = nodeFromPoint(event);
      if (!node) return;
      dragging = node;
      const point = svgPoint(event);
      pointerOffset = { x: node.x - point.x, y: node.y - point.y };
      svg.setPointerCapture(event.pointerId);
      selectNode(node);
    });
    svg.addEventListener('pointermove', event => {
      if (!dragging) return;
      const point = svgPoint(event);
      dragging.x = Math.max(24, Math.min(width - 24, point.x + pointerOffset.x));
      dragging.y = Math.max(24, Math.min(height - 24, point.y + pointerOffset.y));
      dragging.vx = 0;
      dragging.vy = 0;
      alpha = 0.5;
      draw();
    });
    svg.addEventListener('pointerup', event => {
      dragging = null;
      try { svg.releasePointerCapture(event.pointerId); } catch (error) {}
    });
    svg.addEventListener('click', event => {
      const node = nodeFromPoint(event);
      if (node) selectNode(node);
    });
    search.addEventListener('input', updateSearchResults);
    search.addEventListener('focus', updateSearchResults);
    search.addEventListener('keydown', event => {
      if (!searchResults.classList.contains('open') && event.key !== 'Enter') return;
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        activeResultIndex = Math.min(resultNodes.length - 1, activeResultIndex + 1);
        renderSearchResults();
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        activeResultIndex = Math.max(0, activeResultIndex - 1);
        renderSearchResults();
      } else if (event.key === 'Enter') {
        event.preventDefault();
        if (activeResultIndex >= 0) selectSearchResult(activeResultIndex);
      } else if (event.key === 'Escape') {
        hideSearchResults();
      }
    });
    searchResults.addEventListener('mousedown', event => {
      const button = event.target.closest('.search-result');
      if (!button || button.dataset.index === undefined) return;
      event.preventDefault();
      selectSearchResult(Number(button.dataset.index));
    });
    document.addEventListener('mousedown', event => {
      if (!event.target.closest('.search-box')) hideSearchResults();
    });
    typeFilter.addEventListener('change', applyFilter);
    document.getElementById('focusReview').addEventListener('click', () => {
      typeFilter.value = 'review_item';
      applyFilter();
    });
    document.getElementById('resetGraph').addEventListener('click', resetGraph);
    window.addEventListener('resize', () => {
      resize();
      alpha = 0.7;
    });

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
    }

    function escapeAttr(value) {
      return escapeHtml(value).replace(/`/g, '&#96;');
    }

    populateControls();
    initPositions();
    requestAnimationFrame(tick);
  </script>
</body>
</html>
"""
    replacements = {
        "__GENERATED_AT__": escape(graph["generated_at"]),
        "__PRODUCT_COUNT__": str(len(products)),
        "__STANDARD_COUNT__": str(len(standard_nodes)),
        "__NODE_COUNT__": str(len(graph["nodes"])),
        "__EDGE_COUNT__": str(len(graph["edges"])),
        "__PRODUCT_CARDS__": product_cards,
        "__COMPANY_ITEMS__": company_items,
        "__STANDARD_ITEMS__": standard_items,
        "__MARKET_ITEMS__": market_items,
        "__REVIEW_ITEMS__": review_items,
        "__FRAME_ITEMS__": frame_items,
        "__PACKS_PATH__": packs_path,
        "__REPORT_COUNT__": str(len(report_nodes)),
        "__GRAPH_JSON__": graph_json,
    }
    for key, value in replacements.items():
        html_text = html_text.replace(key, value)
    return html_text


def render_report(graph: dict[str, Any]) -> str:
    products = [node for node in graph["nodes"] if node["type"] == "product"]
    company_assets = [node for node in graph["nodes"] if node["type"] == "company_asset"]
    standards = [node for node in graph["nodes"] if node["type"] == "standard"]
    competitors = [node for node in graph["nodes"] if node["type"] == "competitor"]
    prospects = [node for node in graph["nodes"] if node["type"] == "prospect"]
    review_nodes = [node for node in graph["nodes"] if node["type"] == "review_item"]
    report_nodes = [node for node in graph["nodes"] if node["type"] == "report_asset"]
    image_nodes = [node for node in graph["nodes"] if node["type"] == "image_asset"]
    video_nodes = [node for node in graph["nodes"] if node["type"] == "video_asset"]
    frame_nodes = [node for node in graph["nodes"] if node["type"] == "video_keyframe"]

    lines = [
        "# GRAPH_REPORT",
        "",
        "该报告由 tuolinagent 根据本地 Agent 知识包生成，不需要 LLM API key。",
        "",
        "## 构建摘要",
        "",
        f"- 图谱类型：{graph['graph_type']}",
        f"- 节点数：{len(graph['nodes'])}",
        f"- 关系数：{len(graph['edges'])}",
        f"- 产品数：{len(products)}",
        f"- 公司资料：{len(company_assets)}",
        f"- 标准资料：{len(standards)}",
        f"- 竞争对手：{len(competitors)}",
        f"- 潜在客户：{len(prospects)}",
        f"- 需要人工确认：{len(review_nodes)}",
        "",
        "## 资料信任规则",
        "",
        "- raw 层由企业主动放入，默认作为准确资料沉淀。",
        "- 公司、标准、市场、竞品、潜在客户、检测报告资料默认进入已确认知识。",
        "- 只有资料冲突、文件无法解析、Codex 明确无法判断，或用户要求复核时，才进入人工确认。",
        "",
        "## 产品状态",
        "",
    ]
    for product in products:
        lines.append(f"- {product['label']}：{product.get('status_label', '')}；{product.get('asset_status_label', '')}")

    lines.extend(
        [
            "",
            "## 素材统计",
            "",
            f"- 检测报告：{len(report_nodes)}",
            f"- 图片：{len(image_nodes)}",
            f"- 视频：{len(video_nodes)}",
            f"- 视频关键帧：{len(frame_nodes)}",
            f"- 公司资料：{len(company_assets)}",
            f"- 标准资料：{len(standards)}",
            f"- 竞争对手：{len(competitors)}",
            f"- 潜在客户：{len(prospects)}",
            "",
            "## 待确认内容",
            "",
        ]
    )
    if not review_nodes:
        lines.append("- 当前没有需要人工确认的内容。")
    else:
        for index, node in enumerate(review_nodes[:50], start=1):
            lines.append(f"{index}. {node['label']}｜来源：{node.get('source_path', '')}")
    lines.append("")
    return "\n".join(lines)


def render_product_card(product: dict[str, Any], graph: dict[str, Any]) -> str:
    outgoing = [edge for edge in graph["edges"] if edge["source"] == product["id"]]
    review_count = sum(1 for edge in outgoing if edge.get("status_label") == "需要人工确认")
    variants = product.get("variants") or []
    variant_text = f"<div class=\"label\">变体：{escape('、'.join(variants))}</div>" if variants else ""
    return (
        "<div class=\"card\">"
        f"<h2>{escape(product['label'])}</h2>"
        f"<p><span class=\"status\">{escape(product.get('status_label', ''))}</span></p>"
        f"<div class=\"label\">素材状态：{escape(product.get('asset_status_label', ''))}</div>"
        f"{variant_text}"
        f"<div class=\"label\">关联内容：{len(outgoing)}；需要确认：{review_count}</div>"
        "</div>"
    )


def render_review_item(node: dict[str, Any]) -> str:
    desc = node.get("description") or node.get("label", "")
    return f"<li>{escape(summarize(desc, 120))}<div class=\"path\">{escape(node.get('source_path', ''))}</div></li>"


def render_frame_item(node: dict[str, Any]) -> str:
    return f"<li>{escape(node.get('label', ''))} <span class=\"status\">{escape(node.get('status_label', ''))}</span><div class=\"path\">{escape(node.get('source_path', ''))}</div></li>"


def render_domain_item(node: dict[str, Any]) -> str:
    summary = node.get("summary", "")
    summary_text = f"：{escape(summarize(summary, 90))}" if summary else ""
    return f"<li>{escape(node.get('label', ''))}{summary_text}<div class=\"path\">{escape(node.get('source_path', ''))}</div></li>"


def write_wiki_outputs(wiki_dir: Path, graph: dict[str, Any], packs_dir: Path) -> None:
    wiki_dir.mkdir(parents=True, exist_ok=True)
    products = [node for node in graph["nodes"] if node["type"] == "product"]
    write_markdown(
        wiki_dir / "index.md",
        [
            "# 拓霖本地知识库",
            "",
            "## 导航",
            "",
            "- [产品资料](products.md)",
            "- [公司资料](company.md)",
            "- [标准资料](standards.md)",
            "- [市场资料](market.md)",
            "",
            "## 产品",
            "",
            *[f"- [{item['label']}](product-{slug_for_path(item['label'])}.md)" for item in products],
        ],
    )
    write_markdown(wiki_dir / "products.md", render_products_wiki(graph))
    write_markdown(wiki_dir / "company.md", render_domain_wiki("公司资料", [node for node in graph["nodes"] if node["type"] == "company_asset"]))
    write_markdown(wiki_dir / "standards.md", render_domain_wiki("标准资料", [node for node in graph["nodes"] if node["type"] == "standard"]))
    market_nodes = [node for node in graph["nodes"] if node["type"] == "market_asset"]
    market_nodes.extend(node for node in graph["nodes"] if node["type"] in {"competitor", "prospect"})
    write_markdown(wiki_dir / "market.md", render_domain_wiki("市场资料", deduplicate_nodes(market_nodes)))
    for product in products:
        write_markdown(wiki_dir / f"product-{slug_for_path(product['label'])}.md", render_product_wiki(product, graph))


def render_products_wiki(graph: dict[str, Any]) -> list[str]:
    lines = ["# 产品资料", ""]
    for product in [node for node in graph["nodes"] if node["type"] == "product"]:
        lines.extend([f"## {product['label']}", "", f"- 状态：{product.get('status_label', '')}", f"- 素材状态：{product.get('asset_status_label', '')}", ""])
    return lines


def render_product_wiki(product: dict[str, Any], graph: dict[str, Any]) -> list[str]:
    lines = [
        f"# {product['label']}",
        "",
        f"- 状态：{product.get('status_label', '')}",
        f"- 素材状态：{product.get('asset_status_label', '')}",
        "",
        "## 关联内容",
        "",
    ]
    targets = {edge["target"] for edge in graph["edges"] if edge["source"] == product["id"]}
    for node in graph["nodes"]:
        if node["id"] in targets:
            suffix = f"｜{node.get('source_path', '')}" if node.get("source_path") else ""
            lines.append(f"- {node.get('label', '')}{suffix}")
    lines.append("")
    return lines


def render_domain_wiki(title: str, nodes: list[dict[str, Any]]) -> list[str]:
    lines = [f"# {title}", ""]
    if not nodes:
        lines.extend(["当前没有资料。", ""])
        return lines
    current_category = None
    for node in sorted(nodes, key=lambda item: (item.get("category", ""), item.get("label", ""))):
        category = node.get("category", "") or node.get("type", "")
        if category != current_category:
            current_category = category
            lines.extend([f"## {category}", ""])
        summary = f"：{node.get('summary', '')}" if node.get("summary") else ""
        source = f"｜来源：{node.get('source_path', '')}" if node.get("source_path") else ""
        lines.append(f"- {node.get('label', '')}{summary}{source}")
    lines.append("")
    return lines


def write_markdown(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def deduplicate_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    output = []
    for node in nodes:
        if node["id"] in seen:
            continue
        seen.add(node["id"])
        output.append(node)
    return output


def read_pack(packs_dir: Path, dirname: str, product: str) -> dict[str, Any]:
    path = packs_dir / dirname / f"{product}.json"
    return read_json(path) if path.exists() else {}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def product_node_id(product: str) -> str:
    return f"product:{product}"


def fact_node_id(product_id: str, field: str, value: str) -> str:
    return f"fact:{product_id}:{field}:{value}"


def asset_node_id(path: str) -> str:
    return f"asset:{path}"


def field_to_node_type(field: str) -> str:
    return {
        "核心卖点": "selling_point",
        "适用场景": "scenario",
        "禁用场景": "forbidden_scenario",
        "产品变体": "variant",
    }.get(field, "product_fact")


def summarize(value: str, limit: int = 46) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1] + "..."


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def slug_for_path(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", value).strip("-")
