"""kiwi serve — start HTTP + WebSocket server."""

import os
import sys

import click

from ..helpers import ensure_sys_path, print_header, print_error


@click.command()
@click.option("--port", "-p", default=7891, help="Port to bind (default: 7891)")
@click.option("--host", "-h", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
@click.option("--no-watch", is_flag=True, help="Disable file watcher")
@click.option("--token", default=None, help="Set auth token (or use KIWI_TOKEN env)")
@click.option("--open", "open_browser", is_flag=True, help="Open browser to /docs after start")
def serve(port, host, no_watch, token, open_browser):
    """Start Kiwi HTTP + WebSocket server."""
    ensure_sys_path()

    try:
        import uvicorn
    except ImportError:
        print_error("Server dependencies not installed. Run: pip install kiwi-ai[server]")
        raise SystemExit(1)

    try:
        from fastapi import FastAPI
    except ImportError:
        print_error("FastAPI not installed. Run: pip install kiwi-ai[server]")
        raise SystemExit(1)

    if token:
        os.environ["KIWI_TOKEN"] = token

    print_header(f"Kiwi server starting at http://{host}:{port}")
    click.echo(f"  Docs: http://{host}:{port}/docs")
    click.echo(f"  WebSocket: ws://{host}:{port}/ws")
    click.echo(f"  File watcher: {'disabled' if no_watch else 'enabled'}")
    click.echo(f"  Auth: {'token required' if token or os.environ.get('KIWI_TOKEN') else 'open (local only)'}")
    click.echo()

    if open_browser:
        import webbrowser
        webbrowser.open(f"http://{host}:{port}/docs")

    uvicorn.run(
        "server.app:create_app",
        host=host,
        port=port,
        factory=True,
        log_level="info",
        reload=False,
    )