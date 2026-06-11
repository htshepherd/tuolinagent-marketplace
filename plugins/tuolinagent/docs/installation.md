# 安装说明

`tuolinagent` 是本地知识库 Codex 插件。真实资料只放在本地 `raw/` 或外部资料目录，公开 GitHub 仓库不提交私有资料、图片、视频或 `graphify-out/` 产物。

## 推荐安装方式：Codex Plan 模式

企业员工不需要手动记命令。打开 Codex，切换到 Plan 模式，输入：

```text
请从这个单插件 GitHub 仓库安装 tuolinagent：<GitHub仓库链接>。

不要对这个仓库执行 codex plugin marketplace add。这个仓库不是插件市场仓库。

请先 clone 这个仓库到本地，然后在仓库目录运行 scripts/register_personal_plugin.py，把插件登记到个人 marketplace。

登记完成后，用下面命令安装：
codex plugin add tuolinagent@personal

安装前请先检查我的 Windows 电脑是否具备依赖。请优先运行仓库里的 scripts/windows_check_dependencies.ps1。

如果缺少 Git、Python 3.10+、ffmpeg 或 MinerU，请先告诉我缺少什么、有什么用、准备执行什么安装命令。等我明确回复“同意安装依赖”后再安装。

安装完成后，请重新检查依赖，然后验证 tuolinagent 项目是否可用。
```

更多安装检查见：`docs/github-release-checklist.md`。

## 依赖

- Codex
- Git：从 GitHub 下载插件仓库
- Python 3.10+：运行本地知识库脚本
- ffmpeg：视频关键帧抽取
- MinerU：PDF 转 Markdown 预处理
- Graphify：可选，仅维护者高级调试模式使用

Graphify 完整语义抽取只作为高级模式保留。默认 `codex_adapter` 模式不要求配置 Graphify 的 LLM API key。

Windows 用户可以运行依赖检查：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows_check_dependencies.ps1
```

如需由 Codex 在用户授权后安装缺少依赖：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows_check_dependencies.ps1 -Install
```

该安装命令必须在用户确认后执行。

## 准备资料

真实企业资料保留在使用人本机。公开仓库不要提交真实 `raw/`。

`raw/` 不必须和插件仓库在同一个目录。推荐做法是：企业已建好的 `raw/` 目录保持原位置，在 `config/tuolin-kb.config.json` 里配置绝对路径：

```json
{
  "raw_dir": "D:/LocalKnowledge/raw",
  "output_dir": "graphify-out",
  "packs_dir": "graphify-out/tuolin-agent-packs",
  "graphify_mode": "codex_adapter"
}
```

示例文件见：

```text
config/tuolin-kb.external-raw.example.json
```

也可以直接让 Codex 创建配置。员工在知识库工作目录里输入：

```text
请在当前项目里创建 config/tuolin-kb.config.json。
我的 raw 目录是 D:\LocalKnowledge\raw，请在配置里写成 D:/LocalKnowledge/raw。
保持默认 codex_adapter 模式，不要要求 Graphify API key。
```

生成后的配置应类似：

```json
{
  "raw_dir": "D:/LocalKnowledge/raw",
  "output_dir": "graphify-out",
  "packs_dir": "graphify-out/tuolin-agent-packs",
  "graphify_mode": "codex_adapter"
}
```

Windows 路径建议在 JSON 里写成 `D:/LocalKnowledge/raw`，不要写成 `D:\LocalKnowledge\raw`，避免反斜杠被 JSON 当作转义字符。

配置完成后，让 Codex 检查：

```text
检查一下知识库配置是否可用。
```

如果 `raw/` 就放在插件仓库根目录下，可以继续使用默认配置：

```json
{
  "raw_dir": "raw"
}
```

可以参考：

```text
examples/raw-template/
```

最小目录结构：

```text
raw/
├── 00_知识库核心资料/
├── 01_公司介绍/
│   ├── 01_公司介绍/
│   ├── 02_生产车间/
│   ├── 03_企业资质/
│   └── 04_实验室校验检测/
├── 02_标准/
│   ├── 01_国标/
│   └── 02_国际标准/
├── 03_市场/
│   ├── 01_市场现状/
│   ├── 02_竞争对手/
│   └── 03_潜在客户/
└── 04_产品/
    └── [产品名称]/
        ├── 01_报告/
        ├── 02_图片/
        └── 03_视频/
```

## 验证项目

```bash
python3 scripts/validate_project.py
```

## 构建知识库

```bash
python3 scripts/tuolin_kb/build.py
python3 scripts/tuolin_kb/extract_video_keyframes.py
python3 scripts/tuolin_kb/prepare_extraction_tasks.py
python3 scripts/tuolin_kb/apply_extraction_results.py
```

## 查看状态

```bash
python3 scripts/tuolin_kb/status.py
```

## 复核回写

先生成核心资料修改预览，不会写入：

```bash
python3 scripts/tuolin_kb/core_patch.py --preview --claim-index 1
```

人工确认后写入核心资料，并自动再生成数字资产层和 Agent 知识包：

```bash
python3 scripts/tuolin_kb/core_patch.py --patch graphify-out/tuolin-agent-packs/review/core-patches/<patch>.json --confirm WRITE_CORE_KNOWLEDGE
```
