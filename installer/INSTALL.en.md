# Stata MCP setup — Windows / Codex / Claude Desktop

[한국어](설치안내.md) | **English**

## Requirements

- A working Stata installation with a valid license. Tested: StataNow 19.5 BE.
- 64-bit Python 3.11 or later. Tested: Python 3.12.
- Codex or Claude Desktop installed on the same Windows PC, and internet access.

Setup does not install Python, Stata, or the AI apps. Administrator privileges are not required.

## Install

1. Download `stata-mcp-0.1.5-windows-setup.zip` from the [v0.1.5 release](https://github.com/seokjinwoo/stata-mcp/releases/tag/v0.1.5). No GitHub login is needed.
2. Extract the entire ZIP.
3. Double-click **install.cmd** or **설치.cmd**.
4. At **언어 선택 / Select language**, choose **2. English**. Enter alone selects Korean.
5. After the Python environment and dependencies are ready, choose **1. Codex / 2. Claude Desktop / 3. Both**.
6. Select your Stata installation if prompted. If it is not detected, select the folder containing `utilities/pystata` and the Stata executable.
7. If an existing `stata-local` entry differs, enter `Y` only if you want to replace it. Other servers and preferences are preserved, and the original configuration is backed up.
8. Wait for the real Stata regression and graph check and app registration to finish.
9. Fully quit and restart the selected apps. In a new conversation, ask:

> Call stata-local's stata_status tool and check the connection.

The installation check uses Stata's built-in auto dataset in a separate session. The ZIP also includes the DID example code and graph in `examples/`.

The language choice applies to setup messages, menus, and installer errors. It does not translate Stata output, dependency installation logs, operating system errors, or change your AI app's language.

## Claude Desktop

Setup adds `stata-local` to `mcpServers` in `%APPDATA%\Claude\claude_desktop_config.json` by default. It uses only `command`, `args`, and `env`.

Check the actual configuration location in **Settings → Developer → Edit Config**. If your app uses another location, pass it with `-ClaudeConfig`. This is local desktop setup, not a remote connector URL for claude.ai.

Configuration registration and standard MCP execution are verified. Final tool invocation inside the Claude Desktop UI has not yet been verified. Restart the app and test it; organizational policies may restrict local MCP servers.

[Official local MCP connection guide](https://modelcontextprotocol.io/docs/develop/connect-local-servers)

## Locations and reinstalling

- Server: `%LOCALAPPDATA%\StataMCP\envs\0.1.5`
- Codex config: `%CODEX_HOME%\config.toml`, or `%USERPROFILE%\.codex\config.toml` when CODEX_HOME is unset
- Claude config: `%APPDATA%\Claude\claude_desktop_config.json`
- Analysis outputs: `%USERPROFILE%\Documents\StataAnalysis`
- Installation check: the `installation-check` subfolder of the analysis folder
- Installation report: `%LOCALAPPDATA%\StataMCP\installation-result.json`
- Manual Claude configuration example: `%LOCALAPPDATA%\StataMCP\claude-desktop.local.json`
- Backups: `.before-stata-<timestamp>.bak` beside each modified configuration

After success, the downloaded ZIP and extracted folder can be removed. Keep the installed environment and Python itself. Reinstalling the same version reuses its environment and leaves identical settings unchanged. A new version uses a separate environment and asks before replacing the existing server entry. Old environments are not automatically deleted. Codex and Claude use separate Stata sessions.

## Advanced options

Run from the extracted ZIP folder:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 `
  -Language en -Client both `
  -PythonPath "C:\Python312\python.exe" `
  -StataHome "C:\Program Files\StataNow19" -Edition be
```

- `-Language en` or `-Language ko`: skip the language menu.
- `-Client codex`, `-Client claude`, or `-Client both`: skip app selection.
- `-ClaudeConfig` and `-CodexConfig`: specify the actual configuration file paths.
- `-InstallDir` and `-WorkDir`: set installation and analysis folders.
- `-NonInteractive`: do not prompt; fail if a choice or replacement consent is needed. Without explicit language and app options, defaults are Korean and Codex for compatibility.
- `-ReplaceExisting`: consent to replacing `stata-local` in the selected apps.

Direct Python entry points also accept `--language en|ko`. The launcher sets the execution policy only for its own PowerShell process; it does not change the machine's permanent policy.

## Troubleshooting and feedback

- Python not found: install 64-bit Python 3.12, or use `-PythonPath`.
- Stata not found: select the installation folder containing `utilities/pystata` and the appropriate edition executable.
- License error: confirm that Stata runs normally on its own.
- Package download failure: check internet, proxy, and organizational restrictions.
- Invalid configuration: fix the reported TOML/JSON error; setup will not overwrite the malformed file.
- Interrupted installation lock: only after confirming that no other setup is running, remove `install.lock` in the installation folder or `.stata-install.lock` beside the configuration file.
- No tools in the app: fully restart the app, confirm the configuration path, and check local MCP policies.

Send feedback through [GitHub Issues](https://github.com/seokjinwoo/stata-mcp/issues). Include Windows/Stata versions, app, language, failed step, and a redacted error message. Do not upload private research data or complete configuration files.

The server executes Stata commands with your user permissions. It does not automatically upload data or logs to GitHub. Results and graphs returned by MCP go to the AI client you are using.
