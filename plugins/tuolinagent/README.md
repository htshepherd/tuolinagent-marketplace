# tuolinagent

Local knowledge base plugin for Codex.

It helps a user keep private files on their own computer, build local knowledge artifacts, and query them through Codex. The default workflow does not require a separate Graphify model API key.

## Install With Codex

In Codex Plan mode, paste:

```text
Install tuolinagent from this single-plugin GitHub repository:
https://github.com/htshepherd/tuolinagent

Do not run codex plugin marketplace add for this repository. This is not a marketplace repository.

Clone the repository locally, run scripts/register_personal_plugin.py from the cloned repository, then install it with:
codex plugin add tuolinagent@personal

Before using it, check my Windows computer dependencies with scripts/windows_check_dependencies.ps1.

If anything is missing, explain what is missing and what command you plan to run. Do not install software until I confirm.
```

## Local Data

Keep private source files on the user's computer. Do not commit private data or generated outputs to GitHub.

The source data folder can be outside the plugin directory. Configure it in `config/tuolin-kb.config.json`:

```json
{
  "raw_dir": "D:/LocalKnowledge/raw",
  "output_dir": "graphify-out",
  "packs_dir": "graphify-out/tuolin-agent-packs",
  "graphify_mode": "codex_adapter"
}
```

You can also ask Codex to create it:

```text
Create config/tuolin-kb.config.json in this project.
My raw folder is D:\LocalKnowledge\raw. Write it as D:/LocalKnowledge/raw in JSON.
Keep graphify_mode as codex_adapter and do not ask for a Graphify API key.
```

If the data folder is inside this repository, the default value works:

```json
{
  "raw_dir": "raw"
}
```

## Dependency Check

On Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows_check_dependencies.ps1
```

With explicit user approval, missing dependencies can be installed with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows_check_dependencies.ps1 -Install
```

## Basic Commands

```bash
python3 scripts/validate_project.py
python3 scripts/tuolin_kb/build.py
python3 scripts/tuolin_kb/status.py
```

## Safety

- Keep private data in `raw/` or an external folder configured by `raw_dir`.
- Do not commit `raw/`, `graphify-out/`, local config files, or secrets.
- Use the default `codex_adapter` mode unless you explicitly need advanced Graphify semantic mode.
