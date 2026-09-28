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
        raise ValueError('mcp_servers must be a TOML table. Existing config was not changed.')
    existing = servers.get('stata-local')
    if existing == entry:
        return original, None
    if existing is not None and not replace:
        raise ConfigConflict('기존 stata-local 설정이 다릅니다. 교체 동의 없이는 변경하지 않습니다.')
    document = tomlkit.parse(text)
    if 'mcp_servers' not in document:
        document['mcp_servers'] = tomlkit.table()
    document['mcp_servers']['stata-local'] = entry
    updated = tomlkit.dumps(document).encode('utf-8')
    expected = dict(before)
    expected['mcp_servers'] = {**servers, 'stata-local': entry}
    if tomllib.loads(updated.decode('utf-8')) != expected:
        raise ValueError('Configuration preservation check failed. No changes made.')
    return original, updated


def register_codex(path, entry, replace=False):
    path = Path(path)
    original, updated = _prepared_config(path, entry, replace)
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
            raise ValueError('설정 파일이 변경됐습니다. Codex 설정 편집을 마친 뒤 다시 실행하세요.')
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
            raise ValueError('설정 파일이 변경됐습니다. 이번 변경은 적용하지 않았습니다.')
        os.replace(temporary, path)
        return {'changed': True, 'backup': str(backup) if backup else None}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)


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
                    raise RuntimeError('MCP 도구를 확인할 수 없습니다.')
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
                    raise RuntimeError('예제 회귀 결과가 예상값과 다릅니다.')
                graph = run.structuredContent.get('graph_path')
                if not graph or not any(c.type == 'image' for c in run.content):
                    raise RuntimeError('그래프 반환을 확인하지 못했습니다.')
                return {'status': status.structuredContent, 'observations': e['e(N)'],
                        'coefficients': coefficients, 'graph_path': graph}

    return asyncio.run(check())


def finish_install(config, entry, install_dir, replace=False):
    config, install_dir = Path(config), Path(install_dir)
    _prepared_config(config, entry, replace)  # Fail before doing an analysis on malformed/conflicting config.
    print('Stata 연결·회귀분석·그래프를 검사합니다...', flush=True)
    result = check_connection(entry)
    install_dir.mkdir(parents=True, exist_ok=True)
    export_claude(install_dir / 'claude-desktop.local.json', entry)
    registration = register_codex(config, entry, replace)
    report = {'config': str(config), 'registration': registration, 'check': result}
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
        raise ValueError('Stata를 하나로 결정할 수 없습니다. --stata-home 및 --edition을 지정하세요.')
    if candidates:
        print('사용할 Stata를 선택하세요:')
        for index, (path, variant) in enumerate(candidates, 1):
            print(f'{index}. {path} ({variant.upper()})')
        choice = input('번호: ').strip()
        if not choice.isdigit() or not 1 <= int(choice) <= len(candidates):
            raise ValueError('올바른 Stata 번호를 선택하지 않았습니다.')
        return candidates[int(choice) - 1]
    print('Stata 설치 폴더(utilities 폴더가 들어 있는 위치)를 선택하세요.')
    selected = ''
    try:
        import tkinter
        from tkinter import filedialog
        window = tkinter.Tk()
        window.withdraw()
        try:
            selected = filedialog.askdirectory(title='Stata 설치 폴더 선택')
        finally:
            window.destroy()
    except (ImportError, RuntimeError):
        selected = input('Stata 설치 폴더 전체 경로: ').strip().strip('"')
    if not selected:
        raise ValueError('폴더 선택을 취소했습니다.')
    matches = find_stata([selected])
    if edition:
        matches = [match for match in matches if match[1] == edition]
    if not matches:
        raise ValueError('선택한 폴더에서 사용 가능한 Stata와 PyStata를 찾지 못했습니다.')
    return select_stata(selected, edition, non_interactive=False)


def main():
    parser = argparse.ArgumentParser(description='Stata MCP 연결 검사 및 Codex 등록')
    parser.add_argument('--install-dir', type=Path, required=True)
    parser.add_argument('--stata-home', type=Path)
    parser.add_argument('--edition', choices=['be', 'se', 'mp'])
    parser.add_argument('--workdir', type=Path, default=Path.home() / 'Documents' / 'StataAnalysis')
    parser.add_argument('--codex-config', type=Path, default=Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'config.toml')
    parser.add_argument('--replace-existing', action='store_true')
    parser.add_argument('--non-interactive', action='store_true')
    args = parser.parse_args()
    try:
        home, edition = select_stata(args.stata_home, args.edition, args.non_interactive)
        print(f'Stata: {home} ({edition.upper()})', flush=True)
        entry = server_entry(Path(sys.executable), home, edition, args.workdir)
        try:
            _prepared_config(args.codex_config, entry, args.replace_existing)
        except ConfigConflict:
            if args.non_interactive:
                raise
            print(f'기존 stata-local 설정이 있습니다: {args.codex_config}')
            print('다른 설정은 유지하고 stata-local만 교체합니다. 원본은 백업합니다.')
            if input('교체하려면 Y를 입력하세요 [기본: 취소]: ').strip().lower() != 'y':
                raise ValueError('기존 설정을 유지하고 설치를 중단했습니다.')
            args.replace_existing = True
        report = finish_install(args.codex_config, entry, args.install_dir, args.replace_existing)
        print('\n설치 및 연결 검사 완료. Codex를 완전히 종료한 뒤 새 대화를 여세요.')
        print(f'Codex 설정: {args.codex_config}')
        if report['registration']['backup']:
            print(f"설정 백업: {report['registration']['backup']}")
        print(f'분석 결과 폴더: {args.workdir}')
        print(f'Claude Desktop 설정 예시: {args.install_dir / "claude-desktop.local.json"}')
        return 0
    except Exception as exc:
        print(f'설치를 완료하지 못했습니다: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
