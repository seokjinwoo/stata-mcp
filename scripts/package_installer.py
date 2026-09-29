"""Build the double-click installer ZIP from an already-built wheel."""
import argparse
import hashlib
import json
from pathlib import Path
import tomllib
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dist', type=Path, default=Path('dist'))
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    version = tomllib.loads((project / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    wheel = args.dist / f'personal_stata_mcp-{version}-py3-none-any.whl'
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    manifest = {'version': version, 'wheel': wheel.name, 'sha256': digest}
    archive = args.dist / f'stata-mcp-{version}-windows-setup.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
        for source in sorted((project / 'installer').iterdir()):
            if source.is_file() and source.suffix in {'.py', '.ps1', '.cmd', '.md'}:
                data = source.read_bytes()
                if source.suffix == '.cmd':
                    data = data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
                output.writestr(source.name, data)
        output.writestr('package.json', json.dumps(manifest, indent=2))
        output.write(wheel, 'packages/' + wheel.name)
        output.write(project / 'README.md', 'README.md')
        for source in sorted((project / 'examples').rglob('*')):
            if source.is_file() and source.suffix in {'.md', '.do', '.png', '.toml', '.json'}:
                output.write(source, source.relative_to(project).as_posix())
    with zipfile.ZipFile(archive) as check:
        assert check.testzip() is None
        assert hashlib.sha256(check.read('packages/' + wheel.name)).hexdigest() == digest
        assert '설치.cmd' in check.namelist()
    artifacts = [archive, wheel, args.dist / f'personal_stata_mcp-{version}.tar.gz']
    checksums = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in artifacts}
    (args.dist / f'checksums-{version}.json').write_text(json.dumps(checksums, indent=2), encoding='utf-8')
    print(archive.resolve())


if __name__ == '__main__':
    main()
