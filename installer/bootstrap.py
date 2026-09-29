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


def tr(ko, en):
    """Installer language only; does not change the AI app or Stata language."""
    return en if os.environ.get('STATA_MCP_INSTALL_LANGUAGE', 'ko') == 'en' else ko


def prepare_environment(path):
    marker = path / '.stata-mcp-managed'
    if path.exists() and not marker.is_file():
        raise ValueError(tr('기존 폴더를 보호하기 위해 중단했습니다: {path}. 다른 설치 위치를 사용하세요.', 'Stopped to protect the existing folder: {path}. Choose another installation location.').format(path=path))
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
    parser.add_argument('--language', choices=['ko', 'en'], default=os.environ.get('STATA_MCP_INSTALL_LANGUAGE', 'ko'))
    parser.add_argument('--install-dir', type=Path, default=Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))) / 'StataMCP')
    args, remaining = parser.parse_known_args()
    os.environ['STATA_MCP_INSTALL_LANGUAGE'] = args.language
    lock = None
    try:
        if sys.version_info < (3, 11) or struct.calcsize('P') != 8:
            raise ValueError(tr('64비트 Python 3.11 이상이 필요합니다. 검증 버전은 Python 3.12입니다.', '64-bit Python 3.11 or later is required. Python 3.12 is the tested version.'))
        bundle = args.bundle.resolve()
        manifest = json.loads((bundle / 'package.json').read_text(encoding='utf-8'))
        version, name = manifest['version'], manifest['wheel']
        if not re.fullmatch(r'\d+\.\d+\.\d+', version) or Path(name).name != name or not name.endswith('.whl'):
            raise ValueError(tr('설치 패키지 정보가 올바르지 않습니다.', 'Invalid installation package metadata.'))
        wheel = bundle / 'packages' / name
        if hashlib.sha256(wheel.read_bytes()).hexdigest() != manifest['sha256']:
            raise ValueError(tr('설치 파일 검증에 실패했습니다. 공식 릴리스 ZIP을 다시 다운로드하세요.', 'Package verification failed. Download the official release ZIP again.'))
        args.install_dir = args.install_dir.resolve()
        args.install_dir.mkdir(parents=True, exist_ok=True)
        candidate = args.install_dir / 'install.lock'
        try:
            with candidate.open('x') as stream:
                stream.write(str(os.getpid()))
        except FileExistsError:
            raise ValueError(tr('다른 설치가 진행 중이거나 이전 설치가 중단됐습니다. 설치 창을 확인하세요: {path}', 'Another installation is running or a previous installation was interrupted. Check the setup windows: {path}').format(path=candidate)) from None
        lock = candidate
        print(tr('설치 위치: {path}', 'Installation location: {path}').format(path=args.install_dir), flush=True)
        print(tr('1/3 Python 전용 환경을 준비합니다...', '1/3 Preparing a dedicated Python environment...'), flush=True)
        python = prepare_environment(args.install_dir / 'envs' / version)
        print(tr('2/3 서버와 필요한 패키지를 설치합니다. 인터넷 연결이 필요합니다...', '2/3 Installing the server and dependencies. Internet access is required...'), flush=True)
        subprocess.run([str(python), '-m', 'pip', '--disable-pip-version-check', '--no-input', 'install', str(wheel)], check=True)
        print(tr('3/3 Stata 연결 검사 및 앱 설정을 준비합니다...', '3/3 Preparing the Stata connection check and app configuration...'), flush=True)
        return subprocess.run([str(python), '-m', 'stata_mcp.install', '--language', args.language, '--install-dir', str(args.install_dir), *remaining]).returncode
    except Exception as exc:
        print(tr('설치를 완료하지 못했습니다: {error}', 'Setup could not be completed: {error}').format(error=exc), file=sys.stderr)
        return 1
    finally:
        if lock is not None:
            lock.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(main())
