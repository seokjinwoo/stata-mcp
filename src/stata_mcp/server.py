"""Client-neutral MCP stdio interface."""
import asyncio
import base64
from contextlib import asynccontextmanager
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, ImageContent, TextContent, ToolAnnotations

from .config import Settings
from .engine import Session


def create_server(settings=None):
    session = Session(settings or Settings.from_env())

    @asynccontextmanager
    async def lifespan(_server):
        try:
            yield {}
        finally:
            await asyncio.to_thread(session.close)

    mcp = FastMCP('Stata Local', lifespan=lifespan, log_level='WARNING', instructions=(
        'Use the user\'s local licensed Stata. A server instance owns one persistent session; '
        'commands run sequentially. Inspect metadata before choosing variables. '
        'stata_run executes arbitrary local code with user permissions; it is not a sandbox. '
        'Keep source files intact unless overwriting is explicitly requested. '
        'A successful command is not evidence that the statistical model is appropriate. '
        'Use stata_results for named numeric output. e() can persist from earlier commands. '
        'Returned output reaches the AI client. Timeout/reset loses memory. '
        'Use export_graph=true to return the current graph as a PNG image. '
        'Default regression tables: show each coefficient followed by <br> and its standard error '
        'in parentheses, NOT p-values in parentheses. Use * p<0.10, ** p<0.05, *** p<0.01 '
        'from unrounded p-values, with this legend below every table. Preserve the fitted model\'s '
        'standard error type (robust/clustered/conventional) and label it. For multiple models align '
        'coefficients across columns and put each standard error directly underneath its coefficient '
        'INSIDE THE SAME TABLE CELL using <br>. Never put standard errors in a separate table row. Use '
        'stata_results.regression_report when available; never invent significance for omitted terms '
        'or unavailable p-values. Include N, R-squared and adjusted R-squared when available. '
        'Follow an explicit user request for a different table format.'
    ))

    async def invoke(method, **kwargs):
        try:
            result = await asyncio.to_thread(method, **kwargs)
        except (ValueError, OSError, RuntimeError) as exc:
            result = {'ok': False, 'error_type': type(exc).__name__, 'error': str(exc)}
        content = [TextContent(type='text', text=json.dumps(result, ensure_ascii=False, allow_nan=False))]
        graph = result.get('graph_path')
        if graph and result.get('ok'):
            path = Path(graph)
            if path.is_file() and path.stat().st_size <= 8 * 1024 * 1024:
                content.append(ImageContent(type='image', mimeType='image/png', data=base64.b64encode(path.read_bytes()).decode('ascii')))
        return CallToolResult(content=content, structuredContent=result, isError=not result.get('ok', False))

    read = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)

    @mcp.tool(annotations=read)
    async def stata_status() -> CallToolResult:
        """Initialize if needed and report Stata version, edition, session ID and artifact directory. No license identifiers."""
        return await invoke(session.status)

    @mcp.tool(annotations=read)
    async def stata_describe() -> CallToolResult:
        """Read current data metadata: observation count and variable names, types, labels. Does not return raw rows."""
        return await invoke(session.describe)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True))
    async def stata_run(code: str | None = None, do_file: str | None = None,
                        timeout: float | None = None, export_graph: bool = False) -> CallToolResult:
        """Run exactly one of Stata code or a UTF-8 do-file. Relative file paths resolve from STATA_WORKDIR.

        Data and estimates persist. Saves code, logs and result snapshots. No automatic rollback or retry.
        timeout is positive seconds (default STATA_TIMEOUT); timeout terminates the worker and loses memory.
        export_graph exports the current graph after successful execution, including an existing graph if code
        creates none. Generate your intended graph in the same call. Only the current graph is exported.
        Arbitrary Stata code can write files or invoke other programs; this is a trusted local execution tool.
        """
        return await invoke(session.run, code=code, do_file=do_file, timeout=timeout, export_graph=export_graph)

    @mcp.tool(annotations=read)
    async def stata_results() -> CallToolResult:
        """Read the last successful run's bounded r(), e(), s() snapshot with matrix labels.

        Fails after a failed execution or reset. e() may be inherited from earlier commands; this is a
        session snapshot, not proof the last command estimated a model. Check run ID and e(cmdline).
        regression_report provides a verified OLS table: estimates with <br> and standard errors in
        parentheses in the SAME CELL, * p<0.10, ** p<0.05, *** p<0.01. No separate SE row.
        Use this format for comparative tables too.
        If unavailable, replay the intended stored regression (estimates replay) before retrieving
        results; do not reuse unrelated r(table). Preserve robust/clustered standard errors.
        """
        return await invoke(session.results)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False))
    async def stata_reset() -> CallToolResult:
        """Discard in-memory data, estimates, macros and programs, and start a new Stata session. Files remain."""
        return await invoke(session.reset)

    return mcp


def main():
    create_server().run(transport='stdio')
