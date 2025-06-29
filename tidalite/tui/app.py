# tidalite/tui/app.py

import asyncio
import sys
from typing import List

from rich.console import Console
from rich.layout import Layout
from rich.live import Live

from .components import Header, Footer
from .views import View, HomeView
from ..api import APIClient
from ..player import Player

# platform-specific key capture
try:
    import msvcrt
    async def get_key(): return await asyncio.to_thread(msvcrt.getch)
except ImportError:
    import termios, tty
    async def get_key():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            # read up to 3 bytes for arrow key escape sequences
            char = sys.stdin.read(3)
        finally:
            termios.tcsetattr(fd, termios.tcsadrain, old_settings)
        return char

class TUIApp:
    def __init__(self):
        self.api = APIClient()
        self.player = Player()
        self.console = Console()
        self.running = True
        
        self.header = Header()
        self.footer = Footer(self.player)
        self.layout = self._make_layout()
        
        self.view_stack: List[View] = []

    def _make_layout(self) -> Layout:
        layout = Layout(name="root")
        layout.split(
            Layout(self.header, name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(self.footer, name="footer", size=4),
        )
        return layout

    def set_header_path(self, path: List[str]):
        self.header.path = ["tidalite"] + path
        
    async def push_view(self, view: View):
        if self.view_stack:
            await self.view_stack[-1].on_leave()
        self.view_stack.append(view)
        await view.on_enter()
        self.layout["body"].update(view.layout)

    async def pop_view(self):
        if len(self.view_stack) > 1:
            old_view = self.view_stack.pop()
            await old_view.on_leave()
            new_view = self.view_stack[-1]
            await new_view.on_enter()
            self.layout["body"].update(new_view.layout)

    async def _handle_input(self):
        """the main input handler loop."""
        raw_key = await get_key()
        key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key

        # normalize arrow keys and other special keys
        key_map = {
            '\x1b[a': 'up',
            '\x1b[b': 'down',
            '\x1b[c': 'right',
            '\x1b[d': 'left',
            '\r': 'enter',
            '\x7f': 'backspace',
            '\t': 'tab',
            '\x1b': 'esc',
        }
        key = key_map.get(key, key)
        
        if key == 'q': self.running = False
        elif key == ' ': self.player.toggle_pause()
        elif key in ('b', 'esc'): await self.pop_view()
        
        if self.view_stack:
            await self.view_stack[-1].handle_input(key.lower())
    
    async def run(self):
        """run the main application loop."""
        try:
            await self.push_view(HomeView(self))
            with Live(self.layout, screen=True, redirect_stderr=False, refresh_per_second=4) as live:
                while self.running:
                    self.layout["footer"].update(Footer(self.player))
                    await self._handle_input()
        finally:
            await self.api.close()
            self.player.stop()

async def run_tui():
    """the entrypoint function to create and run the tui app."""
    await TUIApp().run()
