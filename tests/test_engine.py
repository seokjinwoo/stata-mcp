"""Real Stata tests; STATA_HOME must point to a licensed local installation."""
import importlib.util
import json
import os
from pathlib import Path

import pytest


def test_engine_is_available():
    assert importlib.util.find_spec('stata_mcp'), 'Stata MCP package is not implemented'


@pytest.fixture
def session(tmp_path):
    from stata_mcp.config import Settings
    from stata_mcp.engine import Session
    home = os.environ.get('STATA_HOME')
    if not home:
        pytest.skip('Set STATA_HOME to run licensed integration tests')
    s = Session(Settings(Path(home), 'be', tmp_path / '작업 폴더', timeout=30))
    yield s
    s.close()


DATA = 'clear\ninput double x y\n1 3\n2 5\n3 7\n4 9\nend\nregress y x'


def test_regression_state_and_named_results(session):
    result = session.run(code=DATA)
    assert result['ok'], result
    assert Path(result['code_path']).read_text(encoding='utf-8') == DATA + '\n'
    assert 'Number of obs' in Path(result['log_path']).read_text(encoding='utf-8')
    values = session.results()
    assert values['run_id'] == result['run_id']
    assert values['e']['e(N)'] == 4
    assert values['e']['e(b)']['column_names'] == ['x', '_cons']
    assert values['e']['e(b)']['values'][0] == pytest.approx([2, 1])
    json.dumps(values, allow_nan=False)
    meta = session.describe()
    assert meta['observations'] == 4
    assert [v['name'] for v in meta['variables']] == ['x', 'y']
    assert 'rows' not in meta
    assert session.run(code='generate z = x * 10')['ok']
    assert session.describe()['variable_count'] == 3


def test_failure_invalidates_results_without_replaying_or_rolling_back(session):
    assert session.run(code=DATA)['ok']
    failure = session.run(code='generate before_error = 1\nnot_a_stata_command')
    assert not failure['ok']
    assert failure['error_code'] == 199
    assert 'r(199)' in Path(failure['log_path']).read_text(encoding='utf-8')
    assert not session.results()['ok']
    assert session.results()['run_id'] == failure['run_id']
    assert 'e' not in session.results()
    assert 'before_error' in [v['name'] for v in session.describe()['variables']]


def test_reset_loses_memory_and_changes_session_id(session):
    assert session.run(code=DATA)['ok']
    old = session.status()['session_id']
    assert session.reset()['session_id'] != old
    assert session.describe()['observations'] == 0
    assert not session.results()['ok']


def test_unicode_do_file_graph_and_replay(session, tmp_path):
    source = tmp_path / '한글 예제.do'
    source.write_text(DATA + '\nscatter y x\n', encoding='utf-8')
    first = session.run(do_file=str(source), export_graph=True)
    assert first['ok'], first
    assert Path(first['graph_path']).read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    assert 'scatter' in Path(first['code_path']).read_text(encoding='utf-8')
    saved = session.results()['e']['e(b)']['values'][0]
    session.reset()
    again = session.run(do_file=first['code_path'])
    assert again['ok']
    assert session.results()['e']['e(b)']['values'][0] == pytest.approx(saved)


def test_timeout_terminates_worker_and_requires_fresh_session(session):
    assert session.run(code=DATA)['ok']
    old = session.status()['session_id']
    process = session._process
    result = session.run(code='sleep 10000', timeout=0.5)
    assert not result['ok'] and result['error_type'] == 'timeout'
    assert result['session_lost']
    assert process.poll() is not None
    assert not session.results()['ok']
    assert session.status()['session_id'] != old
    assert session.describe()['observations'] == 0


def test_independent_sessions(session, tmp_path):
    from stata_mcp.config import Settings
    from stata_mcp.engine import Session
    assert session.run(code=DATA)['ok']
    other = Session(Settings(session.settings.stata_home, 'be', tmp_path / 'other'))
    try:
        assert other.describe()['observations'] == 0
        assert session.describe()['observations'] == 4
    finally:
        other.close()


@pytest.mark.parametrize('args', [{}, {'code': ' '}, {'code': 'clear', 'do_file': 'x'}, {'code': 'clear', 'timeout': 0}, {'code': 'clear', 'timeout': float('nan')}])
def test_invalid_input_is_rejected_before_execution(session, args):
    with pytest.raises(ValueError):
        session.run(**args)


def test_output_truncation_retains_full_log(session):
    result = session.run(code='forvalues i=1/600 {\n display "abcdefghijklmnopqrstuvwxyz0123456789"\n}')
    assert result['ok']
    assert result['output_truncated']
    assert len(result['output']) <= 16000
    assert len(Path(result['log_path']).read_text(encoding='utf-8')) > 16000


def test_matrix_limit_and_missing_are_explicit(session):
    result = session.run(code='program define bigresults, rclass\n matrix big = J(70,70,.)\n return matrix big = big\nend\nbigresults')
    assert result['ok'], result
    matrix = session.results()['r']['r(big)']
    assert matrix['shape'] == [70, 70]
    assert matrix['truncated']
    assert matrix['values'][0][0] is None


def test_close_stops_worker_even_when_event_log_write_fails(session, monkeypatch):
    session.status()
    process = session._process
    original_open = Path.open

    def full_disk(path, *args, **kwargs):
        if path.name == 'events.jsonl':
            raise OSError('simulated full disk')
        return original_open(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, 'open', full_disk)
        with pytest.raises(OSError):
            session.close()
        assert process.poll() is not None


def test_startup_event_failure_does_not_leave_worker_running(session, monkeypatch):
    original_open = Path.open

    def full_disk(path, *args, **kwargs):
        if path.name == 'events.jsonl':
            raise OSError('simulated full disk')
        return original_open(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, 'open', full_disk)
        with pytest.raises(OSError):
            session.status()
        assert session._process is None
