"""Standard-library-only installer bootstrap. Run through install.cmd on Windows."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import venv


def prepare_environment(path):
    marker = path / '.stata-mcp-managed'
    if path.exists() and not marker.is_file():
        raise ValueError(f'기존 폴더를 보호하기 위해 중단했습니다: {path}. 다른 설치 위치를 사용하세요.')
    if not path.exists():
        path.mkdir(parents=True)
        marker.write_text('Stata MCP installer\n', encoding='utf-8')
    python = path / 'Scripts' / 'python.exe'
    if not python.is_file():
        venv.EnvBuilder(with_pip=True).create(path)
    return python


def main():
    parser = argparse.ArgumentParser(description='Stata MCP Windows installer')
    parser.add_argument('--bundle', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--install-dir', type=Path, default=Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))) / 'StataMCP')
    args, remaining = parser.parse_known_args()
    lock = None
    try:
        if sys.version_info < (3, 11) or struct.calcsize('P') != 8:
            raise ValueError('64비트 Python 3.11 이상이 필요합니다. 검증 버전은 Python 3.12입니다.')
        bundle = args.bundle.resolve()
        manifest = json.loads((bundle / 'package.json').read_text(encoding='utf-8'))
        version, name = manifest['version'], manifest['wheel']
        if not re.fullmatch(r'\d+\.\d+\.\d+', version) or Path(name).name != name or not name.endswith('.whl'):
            raise ValueError('설치 패키지 정보가 올바르지 않습니다.')
        wheel = bundle / 'packages' / name
        if hashlib.sha256(wheel.read_bytes()).hexdigest() != manifest['sha256']:
            raise ValueError('설치 파일 검증에 실패했습니다. 공식 릴리스 ZIP을 다시 다운로드하세요.')
        args.install_dir = args.install_dir.resolve()
        args.install_dir.mkdir(parents=True, exist_ok=True)
        candidate = args.install_dir / 'install.lock'
        try:
            with candidate.open('x') as stream:
                stream.write(str(os.getpid()))
        except FileExistsError:
            raise ValueError(f'다른 설치가 진행 중이거나 이전 설치가 중단됐습니다. 설치 창을 확인하세요: {candidate}') from None
        lock = candidate
        print(f'설치 위치: {args.install_dir}', flush=True)
        print('1/3 Python 전용 환경을 준비합니다...', flush=True)
        python = prepare_environment(args.install_dir / 'envs' / version)
        print('2/3 서버와 필요한 패키지를 설치합니다. 인터넷 연결이 필요합니다...', flush=True)
        subprocess.run([str(python), '-m', 'pip', '--disable-pip-version-check', '--no-input', 'install', str(wheel)], check=True)
        print('3/3 Stata 연결 검사 및 Codex 설정을 준비합니다...', flush=True)
        return subprocess.run([str(python), '-m', 'stata_mcp.install', '--install-dir', str(args.install_dir), *remaining]).returncode
    except Exception as exc:
        print(f'설치를 완료하지 못했습니다: {exc}', file=sys.stderr)
        return 1
    finally:
        if lock is not None:
            lock.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(main())
