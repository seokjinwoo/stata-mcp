"""All Stata native-library interaction lives in this child process."""
import os
import json
from pathlib import Path
import re
import sys

from .results import snapshot


def _run(stata, config, request):
    code_path = Path(request['code_path'])
    log_path = code_path.with_name('output.log')
    error = None
    values = None
    warning = None
    graph_path = None
    config.set_output_file(str(log_path), replace=True)
    try:
        stata.run(f'do "{code_path.as_posix()}"', inline=False, echo=True)
        try:
            values = snapshot()
        except Exception as exc:
            warning = f'Result extraction failed: {type(exc).__name__}: {exc}'
        if request.get('export_graph'):
            candidate = code_path.with_name('graph.png')
            try:
                stata.run(f'graph export "{candidate.as_posix()}", as(png) width(1200) replace', inline=False)
                graph_path = str(candidate)
            except Exception as exc:
                warning = (warning + '; ' if warning else '') + f'Graph export failed: {exc}'
    except Exception as exc:
        error = str(exc)
        # PyStata puts failed command output in the exception, not its output file.
        print(error, file=config.stoutputf, flush=True)
    finally:
        config.close_output_file()
        config.stoutputf = None  # PyStata close_output_file leaves a closed handle.
    with log_path.open(encoding='utf-8', errors='replace') as log:
        output = log.read(16001)
    codes = re.findall(r'r\((\d+)\)', error or '')
    return {'ok': error is None, 'output': output[:16000], 'output_truncated': len(output) > 16000,
            'error': error[-8000:] if error else None, 'error_code': int(codes[-1]) if error and codes else None,
            'error_type': 'stata' if error else None, 'warning': warning,
            'graph_path': graph_path, 'values': values}


def worker_main(settings, session_dir):
    # Pipes carry RPC; stdout/stderr (including native writes) cannot corrupt MCP stdio.
    protocol = os.fdopen(os.dup(1), 'w', encoding='utf-8', newline='\n', buffering=1)
    def send(value):
        protocol.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')
        protocol.flush()
    diagnostic = open(Path(session_dir) / 'worker.log', 'a', encoding='utf-8', buffering=1)
    for fd in (1, 2):
        os.dup2(diagnostic.fileno(), fd)
    sys.stdout = diagnostic
    sys.stderr = diagnostic
    try:
        os.chdir(settings.workdir)
        sys.path.insert(0, str(settings.stata_home / 'utilities'))
        from pystata import config
        config.init(settings.edition, splash=False)
        from pystata import stata
        import sfi
        config.set_graph_show(False)
        config.set_streaming_output('on')
        stata.run('set more off\nset linesize 120', inline=False)
        info = {'version': sfi.Scalar.getValue('c(stata_version)'), 'edition': settings.edition,
                'stata_home': str(settings.stata_home), 'workdir': str(settings.workdir)}
        send({'ok': True, **info})
        for line in sys.stdin:
            request = json.loads(line)
            op = request['op']
            if op == 'close':
                break
            if op == 'run':
                response = _run(stata, config, request)
            elif op == 'describe':
                count = sfi.Data.getVarCount()
                response = {'ok': True, 'observations': sfi.Data.getObsTotal(), 'variable_count': count,
                            'variables': [{'name': sfi.Data.getVarName(i), 'type': sfi.Data.getVarType(i),
                                           'label': sfi.Data.getVarLabel(i)} for i in range(min(count, 1000))],
                            'truncated': count > 1000}
            else:
                response = {'ok': False, 'error': 'Unknown operation'}
            send(response)
    except EOFError:
        pass
    except BaseException as exc:
        try:
            send({'ok': False, 'error': f'{type(exc).__name__}: {exc}', 'error_type': 'worker'})
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        protocol.close()


if __name__ == '__main__':
    from .config import Settings
    session_dir = Path(sys.argv[1])
    saved = json.loads((session_dir / 'settings.json').read_text(encoding='utf-8'))
    worker_main(Settings(**saved), session_dir)
