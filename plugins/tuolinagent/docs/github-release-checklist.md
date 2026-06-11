# GitHub发布检查清单

发布 `tuolinagent` 到 GitHub 前，先完成下面检查。

## 必须确认

- `.codex-plugin/plugin.json` 存在，插件名为 `tuolinagent`。
- `skills/tuolin-kb/SKILL.md` 存在。
- `README.md`、`docs/installation.md` 已更新。
- `.gitignore` 忽略真实 `raw/`、`graphify-out/`、`.DS_Store`、本地密钥和临时文件。
- 公开仓库不得包含真实客户资料、检测报告、图片、视频、市场资料或本地生成的知识包。
- `examples/raw-template/` 只能包含目录模板和脱敏示例。

## 发布前本地检查

在仓库根目录运行：

```bash
python3 -m unittest discover -s tests -p 'test*.py' -q
python3 -m compileall -q tuolin_kb scripts/tuolin_kb
python3 scripts/validate_project.py
```

如果目录已经初始化为 Git 仓库，运行：

```bash
git status --short
git check-ignore raw graphify-out .DS_Store
```

`raw/` 和 `graphify-out/` 必须被忽略，不得出现在待提交文件中。

## Windows员工安装验收

在一台 Windows 电脑上，用 Codex Plan 模式输入：

```text
请从这个 GitHub 仓库安装 tuolinagent：<GitHub仓库链接>。
安装前请先运行 scripts/windows_check_dependencies.ps1 检查依赖。
缺少依赖时，先告诉我缺少什么、有什么用、准备执行什么命令，等我确认后再安装。
```

验收通过标准：

- Codex 能安装插件。
- Codex 能检查 Git、Python 3.10+、ffmpeg、MinerU、Graphify。
- 缺少依赖时，Codex 会等待用户授权。
- 用户不需要配置 Graphify API key。
- 放入 `raw/` 后，用户说“整理一下知识库”，Codex 会按构建分区推荐下一步，不默认全量扫描。
