"""Protect users' existing configuration and reject broken installer inputs."""
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tomllib

import pytest


@pytest.fixture
def installer():
    assert importlib.util.find_spec('stata_mcp.install'), 'Installer is not implemented yet'
    return importlib.import_module('stata_mcp.install')


def test_registration_preserves_settings_and_backup_and_is_idempotent(installer, tmp_path):
    config = tmp_path / 'config.toml'
    original = b'# user preferences\r\nmodel = "my-model"\r\n[mcp_servers.other]\r\ncommand = "other.exe" # keep comment\r\n'
    config.write_bytes(original)
    entry = {'command': 'C:/한글 folder/python.exe', 'args': ['-m', 'stata_mcp'],
             'env': {'STATA_EDITION': 'be'}}
    result = installer.register_codex(config, entry)
    parsed = tomllib.loads(config.read_text(encoding='utf-8'))
    assert parsed['model'] == 'my-model'
    assert parsed['mcp_servers']['other'] == {'command': 'other.exe'}
    assert parsed['mcp_servers']['stata-local']['command'] == 'C:/한글 folder/python.exe'
    assert '# keep comment' in config.read_text(encoding='utf-8')
    assert Path(result['backup']).read_bytes() == original
    installed = config.read_bytes()
    assert installer.register_codex(config, entry)['changed'] is False
    assert config.read_bytes() == installed
    assert len(list(tmp_path.glob('*.bak'))) == 1


def test_conflict_requires_explicit_replace_and_preserves_other_servers(installer, tmp_path):
    config = tmp_path / 'config.toml'
    original = b'[mcp_servers."stata-local"]\ncommand="old.exe"\n[mcp_servers.other]\ncommand="keep.exe"\n'
    config.write_bytes(original)
    with pytest.raises(installer.ConfigConflict):
        installer.register_codex(config, {'command': 'new.exe'})
    assert config.read_bytes() == original
    result = installer.register_codex(config, {'command': 'new.exe'}, replace=True)
    parsed = tomllib.loads(config.read_text())
    assert parsed['mcp_servers'] == {'stata-local': {'command': 'new.exe'}, 'other': {'command': 'keep.exe'}}
    assert Path(result['backup']).read_bytes() == original


def test_malformed_config_is_never_overwritten(installer, tmp_path):
    config = tmp_path / 'config.toml'
    original = b'[broken\n'
    config.write_bytes(original)
    with pytest.raises(ValueError):
        installer.register_codex(config, {'command': 'python.exe'}, replace=True)
    assert config.read_bytes() == original
    assert len(list(tmp_path.iterdir())) == 1


def test_new_config_and_claude_export_have_correct_paths(installer, tmp_path):
    entry = installer.server_entry(Path('C:/Tools/Python/python.exe'), Path('C:/Program Files/StataNow19'), 'be', tmp_path)
    config = tmp_path / 'new' / 'config.toml'
    installer.register_codex(config, entry)
    parsed = tomllib.loads(config.read_text(encoding='utf-8'))
    assert parsed['mcp_servers']['stata-local']['args'] == ['-m', 'stata_mcp']
    assert parsed['mcp_servers']['stata-local']['env']['STATA_EDITION'] == 'be'
    dest = tmp_path / 'claude.json'
    installer.export_claude(dest, entry)
    claude = json.loads(dest.read_text(encoding='utf-8'))['mcpServers']['stata-local']
    assert claude['command'] == entry['command']
    assert 'startup_timeout_sec' not in claude
    assert 'tool_timeout_sec' not in claude


def test_discovery_requires_pystata_and_exact_edition_executable(installer, tmp_path):
    good = tmp_path / 'StataNow19'
    (good / 'utilities' / 'pystata').mkdir(parents=True)
    (good / 'StataBE-64.exe').touch()
    (good / 'StataBE-64_old.exe').touch()
    broken = tmp_path / 'Stata18'
    broken.mkdir()
    (broken / 'StataMP-64.exe').touch()
    assert installer.find_stata([tmp_path]) == [(good.resolve(), 'be')]
    (good / 'StataSE-64.exe').touch()
    assert installer.find_stata([tmp_path]) == [(good.resolve(), 'be'), (good.resolve(), 'se')]


def test_installer_checks_real_mcp_regression_and_graph(installer, tmp_path):
    if not os.environ.get('STATA_HOME'):
        pytest.skip('Set STATA_HOME')
    entry = installer.server_entry(Path(sys.executable), Path(os.environ['STATA_HOME']), 'be', tmp_path)
    result = installer.check_connection(entry)
    assert result['observations'] == 74
    assert result['coefficients'] == pytest.approx([-49.5122206664, 1.7465591583, 1946.0686679649])
    assert Path(result['graph_path']).read_bytes().startswith(b'\x89PNG\r\n\x1a\n')


def test_failed_stata_check_does_not_register_config(installer, tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text('model="keep"\n')
    entry = installer.server_entry(Path(sys.executable), tmp_path / 'missing-stata', 'be', tmp_path / 'work')
    with pytest.raises(Exception):
        installer.finish_install(config, entry, tmp_path / 'install')
    assert config.read_text() == 'model="keep"\n'


def test_selected_folder_with_two_editions_offers_choice(installer, tmp_path, monkeypatch):
    # Only the native folder dialog and user input are replaced; discovery is real.
    import tkinter
    from tkinter import filedialog
    home = tmp_path / 'custom'
    (home / 'utilities' / 'pystata').mkdir(parents=True)
    (home / 'StataBE-64.exe').touch()
    (home / 'StataMP-64.exe').touch()
    class Window:
        def withdraw(self): pass
        def destroy(self): pass
    monkeypatch.setattr(tkinter, 'Tk', Window)
    monkeypatch.setattr(filedialog, 'askdirectory', lambda **kwargs: str(home))
    monkeypatch.setattr('builtins.input', lambda _: '2')
    assert installer.select_stata(tmp_path / 'missing', None, False) == (home.resolve(), 'mp')


def test_claude_merge_backup_and_repeat(installer, tmp_path):
    config = tmp_path / 'claude_desktop_config.json'
    original = b'{"preferences":{"theme":"dark"},"mcpServers":{"other":{"command":"keep"}}}'
    config.write_bytes(original)
    entry = installer.server_entry(sys.executable, tmp_path, 'be', tmp_path / '한글 folder')
    result = installer.register_claude(config, entry)
    parsed = json.loads(config.read_text(encoding='utf-8'))
    assert parsed['preferences'] == {'theme': 'dark'}
    assert parsed['mcpServers']['other'] == {'command': 'keep'}
    assert parsed['mcpServers']['stata-local'] == {k: entry[k] for k in ('command', 'args', 'env')}
    assert Path(result['backup']).read_bytes() == original
    installed = config.read_bytes()
    assert installer.register_claude(config, entry)['changed'] is False
    assert config.read_bytes() == installed


@pytest.mark.parametrize('original', [b'{bad', b'[]', b'{"mcpServers":null}', b'{"mcpServers":[]}', b'{"x":1,"x":2}'])
def test_claude_rejects_invalid_config_without_changes(installer, tmp_path, original):
    config = tmp_path / 'claude.json'
    config.write_bytes(original)
    with pytest.raises(ValueError):
        installer.register_claude(config, {'command': 'python', 'args': [], 'env': {}}, replace=True)
    assert config.read_bytes() == original


def test_claude_conflict_requires_replace(installer, tmp_path):
    config = tmp_path / 'claude.json'
    original = b'{"mcpServers":{"stata-local":{"command":"old"},"other":{"command":"keep"}}}'
    config.write_bytes(original)
    entry = {'command': 'new', 'args': [], 'env': {}}
    with pytest.raises(installer.ConfigConflict):
        installer.register_claude(config, entry)
    assert config.read_bytes() == original
    installer.register_claude(config, entry, replace=True)
    assert json.loads(config.read_text())['mcpServers'] == {'stata-local': entry, 'other': {'command': 'keep'}}


@pytest.mark.parametrize('client', ['codex', 'claude', 'both'])
def test_installer_registers_only_selected_clients(installer, tmp_path, monkeypatch, client):
    monkeypatch.setattr(installer, 'check_connection', lambda entry: {'observations': 74})
    codex, claude = tmp_path / 'config.toml', tmp_path / 'claude.json'
    entry = installer.server_entry(sys.executable, tmp_path, 'be', tmp_path / 'analysis')
    report = installer.finish_install(codex, entry, tmp_path / 'install', client=client, claude_config=claude)
    assert codex.exists() == (client in ('codex', 'both'))
    assert claude.exists() == (client in ('claude', 'both'))
    assert set(report['registrations']) == ({'codex', 'claude'} if client == 'both' else {client})


def test_both_configs_preflight_before_any_write(installer, tmp_path, monkeypatch):
    def unexpected(entry):
        pytest.fail('Stata must not run before config preflight')
    monkeypatch.setattr(installer, 'check_connection', unexpected)
    codex, claude = tmp_path / 'config.toml', tmp_path / 'claude.json'
    claude.write_bytes(b'{broken')
    entry = installer.server_entry(sys.executable, tmp_path, 'be', tmp_path)
    with pytest.raises(ValueError):
        installer.finish_install(codex, entry, tmp_path / 'install', client='both', claude_config=claude)
    assert not codex.exists()
    assert claude.read_bytes() == b'{broken'


def test_client_selection(installer, monkeypatch):
    assert installer.select_client('claude', False) == 'claude'
    assert installer.select_client(None, True) == 'codex'
    monkeypatch.setattr('builtins.input', lambda _: '3')
    assert installer.select_client(None, False) == 'both'
