# tidalite/main.py

import asyncio
import typer
from rich.console import Console

from . import auth, config
from .tui import run_tui

app = typer.Typer(
    name="tidalite",
    help="a simple and powerful tidal tui.",
    add_completion=False,
)
console = Console()

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """the main entrypoint for the tidalite application."""
    if ctx.invoked_subcommand is not None:
        return

    try:
        if not asyncio.run(auth.get_valid_credentials()):
            console.print("  starting authentication...")
            asyncio.run(auth.run_auth_flow())
            if not config.get_auth_credentials():
                console.print("  [bold][/bold] authentication failed. exiting.")
                return

        asyncio.run(run_tui())
    
    except (Exception, KeyboardInterrupt) as e:
        if not isinstance(e, KeyboardInterrupt):
            console.print_exception(show_locals=True)
    
    finally:
        console.print("\n  goodbye.\n")

if __name__ == "__main__":
    app()