"""kiwi lsp — start LSP server for universal IDE support."""

import sys

import click

from ..helpers import ensure_sys_path, print_header, print_error


@click.command()
@click.option("--stdio", is_flag=True, default=True, help="Use stdio transport (default)")
@click.option("--tcp", is_flag=True, help="Use TCP transport instead of stdio")
@click.option("--port", default=7892, help="TCP port (only with --tcp)")
@click.option("--severity", default="ALL", type=click.Choice(["CRITICAL", "HIGH", "SUGGEST", "ALL"]))
@click.option("--platform", default=None, type=click.Choice(["wp", "nextjs"]))
def lsp(stdio, tcp, port, severity, platform):
    """Start Kiwi LSP server for IDE integration."""
    ensure_sys_path()

    try:
        import pygls
    except ImportError:
        print_error("LSP dependencies not installed. Run: pip install kiwi-ai[lsp]")
        raise SystemExit(1)

    try:
        import lsprotocol
    except ImportError:
        print_error("lsprotocol not installed. Run: pip install kiwi-ai[lsp]")
        raise SystemExit(1)

    args = []
    if tcp:
        args.extend(["--tcp", "--port", str(port)])

    from lsp.server import main as lsp_main
    lsp_main(args if args else None)
