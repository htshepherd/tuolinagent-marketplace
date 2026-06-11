# 开发说明

首版开发范围：

1. Codex插件骨架
2. 配置与项目校验
3. Codex抽取适配层优先的build/update封装
4. 四个核心产品manifest和构建分区状态
5. 按产品 raw 目录生成的Agent知识包与公司、标准、市场全库知识域包
6. status状态查看
7. Codex视觉/语义抽取任务队列
8. 视频关键帧写入video_pack
9. confirmed-only内部问答
10. evidence_pack复核列表
11. core_patch核心资料补丁预览与确认写回

核心 Python 包在 `tuolin_kb/`。

插件内部脚本入口在 `scripts/tuolin_kb/`。

默认构建模式是 `codex_adapter`：`build.py` 不调用 Graphify 的语义抽取，因此不要求 LLM API key。Graphify 的完整语义抽取只作为高级模式保留，需维护者在配置中显式设置 `graphify_mode: graphify_semantic`。

自然语言“整理一下拓霖知识库”不是直接构建全库，也不是状态报表。默认含义是根据当前资料状态推荐一个最有业务价值的下一步，说明做完能得到什么，并等待确认；只有用户明确说“查看知识库状态”时，才展示完整七分区状态。“从头构建”或“全量重建”必须拆成构建分区队列逐个执行。不要把“重新设计知识库体系”混入构建操作；重新设计属于PRD/架构任务。

构建和更新只做确定性编译：扫描 raw、生成知识包、抽取视频关键帧、生成素材分析清单和刷新 manifest。Codex 不得在 build/update 后自动分析图片、检测报告或视频关键帧，也不得自动合并结果。

继续看资料和整理成可用资料必须由自然语言明确触发。用户说“整理一下拓霖知识库”时，默认推荐一个最有业务价值的下一步，不输出完整技术状态报表；用户说“查看知识库状态”时，才展示七个构建分区和数量。普通用户可见选项必须说明执行后能得到什么，不要把“应用分析结果”“分析素材”作为主选项。整理成可用资料成功后，对应结果标记为 `applied: true`。

raw层资料由企业主动放入，默认准确。公司介绍、标准、市场、竞品、潜在客户、检测报告默认作为已确认知识沉淀；只有资料冲突、文件无法解析、Codex明确无法判断或用户要求复核时，才进入复核清单。PDF正文必须先由MinerU转换为raw原目录同名Markdown；Codex读取Markdown正文，PDF原件保留为证据附件。

用户可见文案必须映射内部术语：`inferred` 显示为“待确认”，`uncertain` 显示为“不确定”，`pending` 显示为“待处理”，`confirmed` 显示为“已确认”，`review_required` 显示为“需要人工确认”，`evidence_pack` 显示为“复核清单”，`tasks.json` 显示为“素材分析清单”，`claim` 显示为“内容”。

用户可见回答不要描述内部检索路径。不要输出“按 tuolin-kb 规则”“先看 manifest”“读取 evidence_pack”“查 video_pack”“只回答 confirmed”这类实现话术。改用“我会先用已整理好的产品资料回答”“这部分还待确认”“我只列出需要你判断的内容”等业务语言。

回写话术尤其要保守。不要输出“按复核回写流程”“定位待复核 claim”“写入 raw/00_知识库核心资料/”“更新复核状态并校验”。对用户只说“生成修改预览”“等待你确认”“确认后加入核心资料”。核心资料回写必须先运行预览，再由人工显式确认令牌写入；写入后自动执行增量构建并再生成 Agent 知识包。再生成失败时报告错误，不回滚已确认写入的核心资料。

测试使用标准库 `unittest`：

```bash
python3 -m unittest tests/test_tuolin_kb.py
python3 -m unittest tests/test_tuolin_kb_round2.py
```

第二轮脚本：

```bash
python3 scripts/tuolin_kb/prepare_extraction_tasks.py
python3 scripts/tuolin_kb/recommend_next_step.py
python3 scripts/tuolin_kb/extract_video_keyframes.py
python3 scripts/tuolin_kb/apply_extraction_results.py
python3 scripts/tuolin_kb/review_claims.py
python3 scripts/tuolin_kb/core_patch.py --preview --claim-index 1
python3 scripts/tuolin_kb/query.py "石英纤维隔热带适合室内排烟管吗？"
```
