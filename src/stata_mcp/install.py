"""Windows setup finishing step; runs only when explicitly invoked by the installer."""
import argparse
import asyncio
from datetime import datetime, timedelta
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import tomllib

import tomlkit


def tr(ko, en):
    """Installer language only; does not change the AI app or Stata language."""
    return en if os.environ.get('STATA_MCP_INSTALL_LANGUAGE', 'ko') == 'en' else ko


class ConfigConflict(ValueError):
    pass


def server_entry(python, stata_home, edition, workdir):
    return {'command': str(Path(python).resolve()), 'args': ['-m', 'stata_mcp'],
            'startup_timeout_sec': 30, 'tool_timeout_sec': 240,
            'env': {'STATA_HOME': str(Path(stata_home).resolve()), 'STATA_EDITION': edition,
                    'STATA_WORKDIR': str(Path(workdir).resolve()),
                    'STATA_TIMEOUT': '120', 'PYTHONUTF8': '1'}}


def find_stata(roots):
    found = set()
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for home in [root, *sorted(root.glob('Stata*'))]:
            if not (home / 'utilities' / 'pystata').is_dir():
                continue
            for edition in ('be', 'se', 'mp'):
                if (home / f'Stata{edition.upper()}-64.exe').is_file():
                    found.add((home.resolve(), edition))
    return sorted(found, key=lambda item: (str(item[0]).lower(), item[1]))


def _prepared_config(path, entry, replace):
    original = path.read_bytes() if path.exists() else None
    text = (original or b'').decode('utf-8-sig')
    before = tomllib.loads(text)
    servers = before.get('mcp_servers', {})
    if not isinstance(servers, dict):
        raise ValueError(tr('mcp_servers는 TOML 테이블이어야 합니다. 기존 설정은 변경하지 않았습니다.', 'mcp_servers must be a TOML table. Existing config was not changed.'))
    existing = servers.get('stata-local')
    if existing == entry:
        return original, None
    if existing is not None and not replace:
        raise ConfigConflict(tr('기존 stata-local 설정이 다릅니다. 교체 동의 없이는 변경하지 않습니다.', 'Existing stata-local settings differ. Replacement requires your consent.'))
    document = tomlkit.parse(text)
    if 'mcp_servers' not in document:
        document['mcp_servers'] = tomlkit.table()
    document['mcp_servers']['stata-local'] = entry
    updated = tomlkit.dumps(document).encode('utf-8')
    expected = dict(before)
    expected['mcp_servers'] = {**servers, 'stata-local': entry}
    if tomllib.loads(updated.decode('utf-8')) != expected:
        raise ValueError(tr('설정 보존 검사에 실패했습니다. 변경하지 않았습니다.', 'Configuration preservation check failed. No changes made.'))
    return original, updated


def register_codex(path, entry, replace=False):
    path = Path(path)
    original, updated = _prepared_config(path, entry, replace)
    return _write_config(path, original, updated)


def _write_config(path, original, updated):
    if updated is None:
        return {'changed': False, 'backup': None}
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive lock also protects two copies of this installer running concurrently.
    lock = path.with_name(path.name + '.stata-install.lock')
    with lock.open('x'):
        pass
    temporary = None
    try:
        if (path.read_bytes() if path.exists() else None) != original:
            raise ValueError(tr('설정 파일이 변경됐습니다. 앱 설정 편집을 마친 뒤 다시 실행하세요.', 'The configuration changed. Finish editing the app settings and run setup again.'))
        backup = None
        if original is not None:
            backup = path.with_name(path.name + '.before-stata-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.bak')
            with backup.open('xb') as stream:
                stream.write(original)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        if (path.read_bytes() if path.exists() else None) != original:
            raise ValueError(tr('설정 파일이 변경됐습니다. 이번 변경은 적용하지 않았습니다.', 'The configuration changed. This update was not applied.'))
        os.replace(temporary, path)
        return {'changed': True, 'backup': str(backup) if backup else None}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(tr('JSON 설정에 중복 키가 있습니다. 원본을 수정한 뒤 다시 실행하세요.', 'The JSON configuration contains duplicate keys. Correct the original file and try again.'))
        result[key] = value
    return result


def _prepared_claude_config(path, entry, replace):
    original = path.read_bytes() if path.exists() else None
    before = json.loads(original.decode('utf-8-sig'), object_pairs_hook=_unique_json_object) if original is not None else {}
    if not isinstance(before, dict) or not isinstance(before.get('mcpServers', {}), dict):
        raise ValueError(tr('Claude 설정과 mcpServers는 JSON 객체여야 합니다. 원본은 변경하지 않았습니다.', 'Claude configuration and mcpServers must be JSON objects. The original file was not changed.'))
    servers = before.get('mcpServers', {})
    claude = {key: entry[key] for key in ('command', 'args', 'env')}
    if servers.get('stata-local') == claude:
        return original, None
    if 'stata-local' in servers and not replace:
        raise ConfigConflict(tr('기존 Claude stata-local 설정이 다릅니다. 교체 동의가 필요합니다.', 'Existing Claude stata-local settings differ. Replacement requires your consent.'))
    updated = {**before, 'mcpServers': {**servers, 'stata-local': claude}}
    return original, (json.dumps(updated, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def register_claude(path, entry, replace=False):
    path = Path(path)
    original, updated = _prepared_claude_config(path, entry, replace)
    return _write_config(path, original, updated)


def default_claude_config():
    return Path(os.environ.get('APPDATA', str(Path.home() / 'AppData' / 'Roaming'))) / 'Claude' / 'claude_desktop_config.json'


def client_configs(client, codex_config, claude_config=None):
    configs = {}
    if client not in ('codex', 'claude', 'both'):
        raise ValueError(tr('지원하지 않는 앱입니다.', 'Unsupported app.'))
    if client in ('codex', 'both'):
        configs['codex'] = (Path(codex_config), _prepared_config, register_codex)
    if client in ('claude', 'both'):
        configs['claude'] = (Path(claude_config) if claude_config is not None else default_claude_config(), _prepared_claude_config, register_claude)
    if len({path.resolve() for path, _, _ in configs.values()}) != len(configs):
        raise ValueError(tr('Codex와 Claude 설정은 서로 다른 파일이어야 합니다.', 'Codex and Claude configurations must use different files.'))
    return configs


def select_client(client, non_interactive):
    if client:
        return client
    if non_interactive:
        return 'codex'  # Preserve existing scripted installs.
    print(tr('연결할 앱을 선택하세요: 1. Codex  2. Claude Desktop  3. 둘 다', 'Select an app: 1. Codex  2. Claude Desktop  3. Both'))
    choice = input(tr('번호 [기본: 1]: ', 'Number [default: 1]: ')).strip() or '1'
    if choice not in ('1', '2', '3'):
        raise ValueError(tr('앱 번호는 1, 2, 3 중에서 선택하세요.', 'Select app number 1, 2, or 3.'))
    return {'1': 'codex', '2': 'claude', '3': 'both'}[choice]


def export_claude(path, entry):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    claude = {key: entry[key] for key in ('command', 'args', 'env')}
    path.write_text(json.dumps({'mcpServers': {'stata-local': claude}}, ensure_ascii=False, indent=2), encoding='utf-8')


def check_connection(entry):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def check():
        env = dict(entry['env'])
        # Use a separate session and directory, never the user's current analysis.
        env['STATA_WORKDIR'] = str(Path(env['STATA_WORKDIR']) / 'installation-check')
        params = StdioServerParameters(command=entry['command'], args=entry['args'], env=env)
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=180)) as client:
                await client.initialize()
                names = {tool.name for tool in (await client.list_tools()).tools}
                if not {'stata_status', 'stata_run', 'stata_results'}.issubset(names):
                    raise RuntimeError(tr('MCP 도구를 확인할 수 없습니다.', 'Could not verify the MCP tools.'))
                status = await client.call_tool('stata_status', {})
                if status.isError:
                    raise RuntimeError(str(status.structuredContent))
                run = await client.call_tool('stata_run', {'code': 'sysuse auto, clear\nregress price mpg weight\ntwoway (scatter price weight) (lfit price weight)', 'export_graph': True})
                if run.isError or not run.structuredContent.get('ok'):
                    raise RuntimeError(str(run.structuredContent))
                values = await client.call_tool('stata_results', {})
                if values.isError:
                    raise RuntimeError(str(values.structuredContent))
                e = values.structuredContent['e']
                coefficients = e['e(b)']['values'][0]
                expected = [-49.51222066635617, 1.746559158345751, 1946.0686679649016]
                if e['e(N)'] != 74 or len(coefficients) != 3 or not all(math.isclose(a, b, rel_tol=1e-7) for a, b in zip(coefficients, expected)):
                    raise RuntimeError(tr('예제 회귀 결과가 예상값과 다릅니다.', 'The example regression results do not match the expected values.'))
                graph = run.structuredContent.get('graph_path')
                if not graph or not any(c.type == 'image' for c in run.content):
                    raise RuntimeError(tr('그래프 반환을 확인하지 못했습니다.', 'Could not verify the returned graph.'))
                return {'status': status.structuredContent, 'observations': e['e(N)'],
                        'coefficients': coefficients, 'graph_path': graph}

    return asyncio.run(check())


def finish_install(config, entry, install_dir, replace=False, *, client='codex', claude_config=None):
    install_dir = Path(install_dir)
    configs = client_configs(client, config, claude_config)
    for path, prepare, _ in configs.values():
        prepare(path, entry, replace)  # Validate every selected config before analysis or writes.
    print(tr('Stata 연결·회귀분석·그래프를 검사합니다...', 'Checking the Stata connection, regression, and graph...'), flush=True)
    result = check_connection(entry)
    install_dir.mkdir(parents=True, exist_ok=True)
    export_claude(install_dir / 'claude-desktop.local.json', entry)
    report = {'language': os.environ.get('STATA_MCP_INSTALL_LANGUAGE', 'ko'), 'client': client, 'registrations': {}, 'check': result}
    for name, (path, _, register) in configs.items():
        report['registrations'][name] = {'config': str(path), **register(path, entry, replace)}
        print(tr('{name} 설정 등록 완료: {path}', '{name} configuration registered: {path}').format(name=name, path=path), flush=True)
    if 'codex' in report['registrations']:
        report['config'] = str(config)
        report['registration'] = report['registrations']['codex']
    (install_dir / 'installation-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def select_stata(home, edition, non_interactive):
    roots = [home] if home else [os.environ.get('STATA_HOME', ''), os.environ.get('ProgramFiles', 'C:/Program Files'), os.environ.get('ProgramW6432', 'C:/Program Files')]
    candidates = find_stata([r for r in roots if r])
    if edition:
        candidates = [c for c in candidates if c[1] == edition]
    if len(candidates) == 1:
        return candidates[0]
    if non_interactive:
        raise ValueError(tr('Stata를 하나로 결정할 수 없습니다. --stata-home 및 --edition을 지정하세요.', 'Could not select a single Stata installation. Specify --stata-home and --edition.'))
    if candidates:
        print(tr('사용할 Stata를 선택하세요:', 'Select the Stata installation to use:'))
        for index, (path, variant) in enumerate(candidates, 1):
            print(f'{index}. {path} ({variant.upper()})')
        choice = input(tr('번호: ', 'Number: ')).strip()
        if not choice.isdigit() or not 1 <= int(choice) <= len(candidates):
            raise ValueError(tr('올바른 Stata 번호를 선택하지 않았습니다.', 'Invalid Stata selection.'))
        return candidates[int(choice) - 1]
    print(tr('Stata 설치 폴더(utilities 폴더가 들어 있는 위치)를 선택하세요.', 'Select the Stata installation folder containing the utilities folder.'))
    selected = ''
    try:
        import tkinter
        from tkinter import filedialog
        window = tkinter.Tk()
        window.withdraw()
        try:
            selected = filedialog.askdirectory(title=tr('Stata 설치 폴더 선택', 'Select the Stata installation folder'))
        finally:
            window.destroy()
    except (ImportError, RuntimeError):
        selected = input(tr('Stata 설치 폴더 전체 경로: ', 'Full path to the Stata installation folder: ')).strip().strip('"')
    if not selected:
        raise ValueError(tr('폴더 선택을 취소했습니다.', 'Folder selection was cancelled.'))
    matches = find_stata([selected])
    if edition:
        matches = [match for match in matches if match[1] == edition]
    if not matches:
        raise ValueError(tr('선택한 폴더에서 사용 가능한 Stata와 PyStata를 찾지 못했습니다.', 'Could not find a usable Stata installation and PyStata in the selected folder.'))
    return select_stata(selected, edition, non_interactive=False)


def main():
    parser = argparse.ArgumentParser(description='Stata MCP setup / Stata MCP 설치')
    parser.add_argument('--language', choices=['ko', 'en'], default=os.environ.get('STATA_MCP_INSTALL_LANGUAGE', 'ko'))
    parser.add_argument('--install-dir', type=Path, required=True)
    parser.add_argument('--stata-home', type=Path)
    parser.add_argument('--edition', choices=['be', 'se', 'mp'])
    parser.add_argument('--workdir', type=Path, default=Path.home() / 'Documents' / 'StataAnalysis')
    parser.add_argument('--codex-config', type=Path, default=Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'config.toml')
    parser.add_argument('--claude-config', type=Path, default=default_claude_config())
    parser.add_argument('--client', choices=['codex', 'claude', 'both'])
    parser.add_argument('--replace-existing', action='store_true')
    parser.add_argument('--non-interactive', action='store_true')
    args = parser.parse_args()
    os.environ['STATA_MCP_INSTALL_LANGUAGE'] = args.language
    try:
        client = select_client(args.client, args.non_interactive)
        home, edition = select_stata(args.stata_home, args.edition, args.non_interactive)
        print(f'Stata: {home} ({edition.upper()})', flush=True)
        entry = server_entry(Path(sys.executable), home, edition, args.workdir)
        replace = args.replace_existing
        for name, (path, prepare, _) in client_configs(client, args.codex_config, args.claude_config).items():
            try:
                prepare(path, entry, args.replace_existing)
            except ConfigConflict:
                if args.non_interactive:
                    raise
                print(tr('기존 {name} stata-local 설정이 있습니다: {path}', 'Existing {name} stata-local configuration: {path}').format(name=name, path=path))
                print(tr('다른 설정은 유지하고 stata-local만 교체합니다. 원본은 백업합니다.', 'Only stata-local will be replaced. Other settings are preserved and the original file is backed up.'))
                if input(tr('교체하려면 Y를 입력하세요 [기본: 취소]: ', 'Enter Y to replace [default: cancel]: ')).strip().lower() != 'y':
                    raise ValueError(tr('기존 설정을 유지하고 설치를 중단했습니다.', 'Setup stopped. Existing settings were kept.'))
                replace = True
        report = finish_install(args.codex_config, entry, args.install_dir, replace, client=client, claude_config=args.claude_config)
        print(tr('\n설치 및 연결 검사 완료. 선택한 앱을 완전히 종료한 뒤 다시 실행하고 새 대화를 여세요.', '\nSetup and connection checks completed. Fully quit the selected apps, restart them, and open a new conversation.'))
        for registration in report['registrations'].values():
            if registration['backup']:
                print(tr('설정 백업: {path}', 'Configuration backup: {path}').format(path=registration['backup']))
        print(tr('분석 결과 폴더: {path}', 'Analysis output folder: {path}').format(path=args.workdir))
        print(tr('Claude Desktop 설정 예시: {path}', 'Claude Desktop configuration example: {path}').format(path=args.install_dir / 'claude-desktop.local.json'))
        return 0
    except Exception as exc:
        print(tr('설치를 완료하지 못했습니다: {error}', 'Setup could not be completed: {error}').format(error=exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
