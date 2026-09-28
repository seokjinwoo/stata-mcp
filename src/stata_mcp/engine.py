"""Serialized session lifecycle, artifact ownership, and bounded worker RPC."""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import uuid

from .config import Settings


class Session:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = threading.RLock()
        self._process = None
        self._responses = None
        self._reader = None
        self._info = None
        self._session_id = None
        self._session_dir = None
        self._last = None
        self._values = None

    def _record(self, event):
        if self._session_dir:
            with (self._session_dir / 'events.jsonl').open('a', encoding='utf-8') as f:
                f.write(json.dumps({'time': datetime.now(timezone.utc).isoformat(), **event}, ensure_ascii=False) + '\n')

    def _stop(self):
        if self._process:
            if self._process.poll() is None:
                self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
            if self._reader:
                self._reader.join(timeout=2)
            self._process.stdin.close()
            self._process.stdout.close()
        self._process = self._responses = self._reader = None
        self._values = None

    @staticmethod
    def _read_responses(process, responses):
        try:
            for line in process.stdout:
                responses.put(json.loads(line))
        except (OSError, ValueError) as exc:
            responses.put({'ok': False, 'error_type': 'worker', 'error': f'Invalid worker response: {exc}'})
        finally:
            responses.put({'ok': False, 'error_type': 'worker', 'error': 'Worker exited', 'session_lost': True})

    def _start(self):
        if self._process is not None and self._process.poll() is None:
            return
        self._stop()
        self._session_id = uuid.uuid4().hex
        self._session_dir = self.settings.workdir / 'runs' / self._session_id
        self._session_dir.mkdir(parents=True, exist_ok=True)
        settings = {'stata_home': str(self.settings.stata_home), 'edition': self.settings.edition,
                    'workdir': str(self.settings.workdir), 'timeout': self.settings.timeout,
                    'startup_timeout': self.settings.startup_timeout}
        (self._session_dir / 'settings.json').write_text(json.dumps(settings), encoding='utf-8')
        env = dict(os.environ, PYTHONUTF8='1', PYTHONUNBUFFERED='1')
        with (self._session_dir / 'bootstrap.log').open('w', encoding='utf-8') as diagnostic:
            self._process = subprocess.Popen([sys.executable, '-m', 'stata_mcp.worker', str(self._session_dir)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=diagnostic,
                text=True, encoding='utf-8', bufsize=1, env=env,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self._responses = queue.Queue()
        self._reader = threading.Thread(target=self._read_responses, args=(self._process, self._responses), daemon=True)
        self._reader.start()
        try:
            self._record({'event': 'worker_spawned', 'pid': self._process.pid})
            try:
                info = self._responses.get(timeout=self.settings.startup_timeout)
            except queue.Empty:
                raise RuntimeError('Stata initialization timed out; check installation, bootstrap.log and worker.log') from None
            if not info.get('ok'):
                raise RuntimeError(info.get('error', 'Stata initialization failed'))
            self._info = info
            self._record({'event': 'session_started', 'session_id': self._session_id})
        except BaseException:
            self._stop()
            raise

    def _request(self, payload, timeout):
        try:
            self._process.stdin.write(json.dumps(payload, ensure_ascii=False) + '\n')
            self._process.stdin.flush()
            try:
                response = self._responses.get(timeout=timeout)
            except queue.Empty:
                self._record({'event': 'timeout', 'session_lost': True})
                self._stop()
                return {'ok': False, 'error_type': 'timeout', 'error': 'Execution timed out; worker terminated. Memory was lost. No retry performed.', 'session_lost': True}
            if response.get('error_type') == 'worker':
                self._stop()
                response['session_lost'] = True
            return response
        except (EOFError, OSError, BrokenPipeError) as exc:
            self._stop()
            return {'ok': False, 'error_type': 'worker', 'error': f'Worker exited: {exc}', 'session_lost': True}

    def status(self):
        with self._lock:
            self._start()
            return {**self._info, 'session_id': self._session_id, 'state': 'ready', 'session_dir': str(self._session_dir)}

    def describe(self):
        with self._lock:
            self._start()
            return {**self._request({'op': 'describe'}, self.settings.timeout), 'session_id': self._session_id}

    def run(self, code=None, do_file=None, timeout=None, export_graph=False):
        if (code is None) == (do_file is None):
            raise ValueError('Provide exactly one of code or do_file')
        limit = self.settings.timeout if timeout is None else timeout
        if not isinstance(limit, (int, float)) or not math.isfinite(limit) or limit <= 0:
            raise ValueError('Timeout must be finite and positive')
        source_path = None
        if do_file is not None:
            source_path = Path(do_file).expanduser()
            if not source_path.is_absolute():
                source_path = self.settings.workdir / source_path
            source_path = source_path.resolve(strict=True)
            code = source_path.read_text(encoding='utf-8-sig')
        if not isinstance(code, str) or not code.strip() or '\x00' in code:
            raise ValueError('Code must be nonempty text without NUL characters')
        with self._lock:
            self._start()
            run_id = uuid.uuid4().hex
            folder = self._session_dir / run_id
            folder.mkdir()
            code_path = folder / 'code.do'
            code_path.write_text(code if code.endswith('\n') else code + '\n', encoding='utf-8', newline='\n')
            (folder / 'output.log').touch()
            self._values = None
            self._last = {'ok': False, 'run_id': run_id, 'session_id': self._session_id}
            self._record({'event': 'run_started', 'run_id': run_id, 'source_path': str(source_path) if source_path else None})
            response = self._request({'op': 'run', 'code_path': str(code_path), 'export_graph': export_graph}, limit)
            values = response.pop('values', None)
            result = {**response, 'run_id': run_id, 'session_id': self._session_id,
                      'code_path': str(code_path), 'log_path': str(folder / 'output.log')}
            if 'output' not in result:
                with (folder / 'output.log').open(encoding='utf-8', errors='replace') as f:
                    output = f.read(16001)
                result.update(output=output[:16000], output_truncated=len(output) > 16000)
            result['artifacts'] = [str(p) for p in folder.iterdir() if p.is_file()]
            if result['ok'] and values is not None:
                self._values = {'ok': True, 'run_id': run_id, 'session_id': self._session_id, **values}
                (folder / 'results.json').write_text(json.dumps(self._values, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
                result['artifacts'].append(str(folder / 'results.json'))
            (folder / 'run.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            self._last = result
            self._record({'event': 'run_finished', 'run_id': run_id, 'ok': result['ok']})
            return result

    def results(self):
        with self._lock:
            if self._values is not None:
                return self._values
            return {'ok': False, 'run_id': (self._last or {}).get('run_id'),
                    'error': 'No result snapshot is available. Last execution failed, session reset, or no successful run exists.'}

    def reset(self):
        with self._lock:
            self._record({'event': 'reset', 'session_lost': True})
            self._stop()
            self._last = None
            return self.status()

    def close(self):
        with self._lock:
            try:
                self._record({'event': 'closed'})
            finally:
                self._stop()
