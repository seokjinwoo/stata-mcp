"""Installer must validate the bundle before creating an environment."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import os

import pytest


BOOTSTRAP = Path(__file__).parents[1] / 'installer' / 'bootstrap.py'


@pytest.mark.skipif(os.name != 'nt', reason='Windows launcher')
def test_powershell_detects_valid_python(tmp_path):
    # Source tree has no bundled wheel, so setup must stop at the manifest,
    # but a valid interpreter must not be rejected by Windows argument quoting.
    result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', str(BOOTSTRAP.with_name('install.ps1')), '-PythonPath', sys.executable,
        '-InstallDir', str(tmp_path / 'target'), '-NonInteractive'], capture_output=True)
    assert b'Python: ' in result.stdout
    assert b'64-bit Python 3.11+ is required' not in result.stdout
    assert not (tmp_path / 'target').exists()


def test_tampered_wheel_does_not_create_environment(tmp_path):
    assert BOOTSTRAP.exists(), 'Bootstrap is not implemented yet'
    bundle = tmp_path / 'bundle'
    (bundle / 'packages').mkdir(parents=True)
    (bundle / 'packages' / 'test.whl').write_bytes(b'changed')
    (bundle / 'package.json').write_text(json.dumps({'version': '0.1.1', 'wheel': 'test.whl', 'sha256': '0' * 64}))
    target = tmp_path / 'installation'
    result = subprocess.run([sys.executable, str(BOOTSTRAP), '--bundle', str(bundle), '--install-dir', str(target), '--non-interactive'], capture_output=True, text=True)
    assert result.returncode != 0
    assert not target.exists()


def test_foreign_environment_is_not_modified(tmp_path):
    assert BOOTSTRAP.exists(), 'Bootstrap is not implemented yet'
    spec = importlib.util.spec_from_file_location('bootstrap', BOOTSTRAP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    env = tmp_path / 'existing'
    env.mkdir()
    sentinel = env / 'user-data.txt'
    sentinel.write_text('keep')
    try:
        module.prepare_environment(env)
    except ValueError:
        pass
    else:
        raise AssertionError('Unmanaged environment must be rejected')
    assert list(env.iterdir()) == [sentinel]
    assert sentinel.read_text() == 'keep'


@pytest.mark.skipif(os.name != 'nt', reason='Windows Python discovery')
def test_discovers_python_outside_path(tmp_path):
    helper = BOOTSTRAP.with_name('python-discovery.ps1')
    assert helper.exists(), 'Fallback discovery not implemented yet'
    script = tmp_path / 'probe.ps1'
    # Explicit candidate roots test the same fallback used for registry locations.
    helper_text = str(helper).replace("'", "''")
    root_text = str(Path(sys.executable).parent).replace("'", "''")
    script.write_text(f". '{helper_text}'\nFind-PythonInFolders @('{root_text}')\n", encoding='utf-8-sig')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)], capture_output=True, text=True)
    assert result.returncode == 0
    assert Path(result.stdout.strip()).resolve() == Path(sys.executable).resolve()
