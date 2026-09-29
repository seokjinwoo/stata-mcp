import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from stata_mcp import install

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize('language,expected', [('en', 'Select an app'), ('ko', '연결할 앱을 선택')])
def test_app_prompt_uses_selected_language(monkeypatch, capsys, language, expected):
    monkeypatch.setenv('STATA_MCP_INSTALL_LANGUAGE', language)
    monkeypatch.setattr('builtins.input', lambda prompt: '3')
    assert install.select_client(None, False) == 'both'
    assert expected in capsys.readouterr().out


def test_english_conflict_preserves_config(monkeypatch, tmp_path):
    monkeypatch.setenv('STATA_MCP_INSTALL_LANGUAGE', 'en')
    config = tmp_path / 'claude.json'
    original = b'{"mcpServers":{"stata-local":{"command":"old"}}}'
    config.write_bytes(original)
    with pytest.raises(install.ConfigConflict, match='Existing Claude'):
        install.register_claude(config, {'command': 'new', 'args': [], 'env': {}})
    assert config.read_bytes() == original


@pytest.mark.parametrize('language,expected', [('en', 'Package verification failed'), ('ko', '설치 파일 검증에 실패')])
def test_bootstrap_errors_use_language(tmp_path, language, expected):
    bundle = tmp_path / 'bundle'
    (bundle / 'packages').mkdir(parents=True)
    (bundle / 'packages/test.whl').write_bytes(b'wrong')
    (bundle / 'package.json').write_text(json.dumps({'version': '0.1.5', 'wheel': 'test.whl', 'sha256': '0' * 64}))
    target = tmp_path / 'target'
    result = subprocess.run([sys.executable, str(ROOT / 'installer/bootstrap.py'), '--bundle', str(bundle),
        '--install-dir', str(target), '--language', language], capture_output=True, encoding='utf-8',
        env=dict(os.environ, PYTHONUTF8='1'))
    assert result.returncode == 1
    assert expected in result.stderr
    assert not target.exists()


@pytest.mark.skipif(os.name != 'nt', reason='Windows installer')
@pytest.mark.parametrize('language,expected', [('en', '64-bit Python'), ('ko', '64비트 Python')])
def test_language_is_set_before_python_detection(tmp_path, language, expected):
    result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        str(ROOT / 'installer/install.ps1'), '-Language', language, '-PythonPath', str(tmp_path / 'missing.exe'),
        '-NonInteractive'], capture_output=True, encoding='utf-8')
    assert result.returncode == 1
    assert expected in result.stdout


@pytest.mark.skipif(os.name != 'nt', reason='Windows installer')
def test_interactive_language_selection_reaches_bootstrap(tmp_path):
    result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        str(ROOT / 'installer/install.ps1'), '-PythonPath', sys.executable, '-InstallDir', str(tmp_path / 'target')],
        input='2\n', capture_output=True, encoding='utf-8', env=dict(os.environ, PYTHONUTF8='1'))
    assert result.returncode == 1  # Source checkout has no release package.json.
    assert 'English' in result.stdout
    assert 'Setup could not be completed' in result.stderr
    assert not (tmp_path / 'target').exists()
