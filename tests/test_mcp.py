"""Full stdio protocol tests, not direct calls to decorated functions."""
import asyncio
import base64
from datetime import timedelta
import json
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest


def test_stdio_analysis_image_error_and_reset(tmp_path):
    if not os.environ.get('STATA_HOME'):
        pytest.skip('Set STATA_HOME')

    async def workflow():
        params = StdioServerParameters(command=sys.executable, args=['-m', 'stata_mcp'], env={
            'PYTHONPATH': str(Path(__file__).parents[1] / 'src'),
            'PYTHONUTF8': '1', 'STATA_HOME': os.environ['STATA_HOME'],
            'STATA_EDITION': 'be', 'STATA_WORKDIR': str(tmp_path / 'mcp work'),
            'STATA_STARTUP_TIMEOUT': '10',
        })
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=90)) as client:
                await client.initialize()
                names = {t.name for t in (await client.list_tools()).tools}
                assert names == {'stata_status', 'stata_describe', 'stata_run', 'stata_results', 'stata_reset'}
                status = await client.call_tool('stata_status', {})
                assert not status.isError, status.structuredContent
                assert status.structuredContent['edition'] == 'be'
                code = 'clear\ninput double x y\n1 3\n2 5\n3 7\n4 9\nend\nregress y x\nscatter y x'
                run = await client.call_tool('stata_run', {'code': code, 'export_graph': True})
                assert not run.isError, run
                assert run.structuredContent['ok']
                images = [c for c in run.content if c.type == 'image']
                assert len(images) == 1
                assert base64.b64decode(images[0].data).startswith(b'\x89PNG\r\n\x1a\n')
                values = await client.call_tool('stata_results', {})
                assert values.structuredContent['e']['e(N)'] == 4
                assert values.structuredContent['e']['e(b)']['values'][0] == pytest.approx([2, 1])
                info = await client.call_tool('stata_describe', {})
                assert info.structuredContent['observations'] == 4
                invalid = await client.call_tool('stata_run', {'code': 'clear', 'do_file': 'anything'})
                assert invalid.isError
                # Validation does not execute code or erase the last successful snapshot.
                assert (await client.call_tool('stata_describe', {})).structuredContent['observations'] == 4
                failed = await client.call_tool('stata_run', {'code': 'not_a_stata_command'})
                assert failed.isError
                assert failed.structuredContent['error_code'] == 199
                assert (await client.call_tool('stata_results', {})).isError
                await client.call_tool('stata_reset', {})
                assert (await client.call_tool('stata_describe', {})).structuredContent['observations'] == 0

    asyncio.run(workflow())
