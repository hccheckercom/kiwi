"""Kiwi AI CLI — entry point."""

import click

from . import __version__
from .commands.init_cmd import init_cmd
from .commands.scan import scan
from .commands.check import check
from .commands.dashboard import dashboard
from .commands.status import status
from .commands.upgrade import upgrade
from .commands.serve import serve
from .commands.lsp import lsp


@click.group()
@click.version_option(__version__, prog_name="kiwi")
def cli():
    """Kiwi AI — code quality scanner that learns your codebase patterns."""
    pass


cli.add_command(init_cmd, "init")
cli.add_command(scan)
cli.add_command(check)
cli.add_command(dashboard)
cli.add_command(status)
cli.add_command(upgrade)
cli.add_command(serve)
cli.add_command(lsp)


if __name__ == "__main__":
    cli()