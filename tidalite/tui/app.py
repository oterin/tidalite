# tidalite/tui/app.py

import asyncio
import sys
import platform
from typing import List, Optional, Callable
from functools import partial

from rich.console import Console
from rich.layout import Layout
from rich.live import Live

from .components import Footer
from .views import View, HomeView
from ..api import APIClient
from ..player import Player

class TUIApp:
    def __init__(self):
        self.api = APIClient()
        self.player = Player()
        self.running = True
        self.view_stack: List[View] = []
        
        # rich setup for mouse support
        self.console = Console()
        self.layout = self._make_layout()
        self.live = Live(self.layout, screen=True, redirect_stderr=False, refresh_per_second=10, transient=True)

    def _make_layout(self) -> Layout:
        # header is now part of the view to be dynamic
        layout = Layout(name="root")
        layout.split(
            Layout(name="body", ratio=1),
            Layout(Footer(self.player), name="footer", size=4),
        )
        return layout

    def set_header_path(self, path: List[str]):
        # this is now a placeholder, views manage their own headers via layout
        pass
        
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

    # --- event dispatchers ---
    def dispatch_click(self, message):
        """dispatch a click event to the component that was clicked."""
        on_click_func = message.style.meta.get("on_click")
        if on_click_func:
            # pass metadata from the component to the handler
            handler_args = {k: v for k, v in message.style.meta.items() if k not in ["@click", "on_click"]}
            on_click_func(**handler_args)

    async def dispatch_hover(self, message):
        """dispatch a hover event to the active view."""
        meta = message.style.meta
        component_id = meta.get("component_id")
        item_index = meta.get("hover_item_index") if message.name == "mouse.enter" else None
        if component_id and self.view_stack:
            await self.view_stack[-1].handle_hover(component_id, item_index)

    async def _event_loop(self):
        """process rich live events, including keyboard and mouse."""
        await self.push_view(HomeView(self))
        async for event in self.live.events:
            if not self.running:
                break
            
            final_key = None
            if isinstance(event, str): # keyboard input
                final_key = event
            elif event.name.startswith("mouse"):
                if event.name == "mouse.scroll_down": final_key = "down"
                elif event.name == "mouse.scroll_up": final_key = "up"
                elif event.name == "mouse.press":
                    self.dispatch_click(event)
            
            if final_key in ('q', 'ctrl+c'): self.running = False
            elif final_key == ' ': self.player.toggle_pause()
            elif final_key in ('b', 'esc'): await self.pop_view()
            
            if self.view_stack and final_key:
                await self.view_stack[-1].handle_input(final_key)

    async def run(self):
        """run the main application loop."""
        with self.live:
            await self._event_loop()
        # cleanup
        self.player.stop()
        await self.api.close()

async def run_tui():
    await TUIApp().run(