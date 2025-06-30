# tidalite/tui/views.py

import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional, Any, TYPE_CHECKING, Tuple

from rich.layout import Layout
from rich.align import Align
from rich.text import Text
from rich.panel import Panel
from rich.markup import escape

from . import theme
from .components import SelectableList
from .. import models, api, player

if TYPE_CHECKING:
    from .app import TUIApp

# --- view base class ---
class View(ABC):
    def __init__(self, app: 'TUIApp'):
        self.app = app
        self.api: api.APIClient = app.api
        self.player: player.Player = app.player
        self.layout = Layout()
        self.detail_pane = Panel(Align.center("no selection", style=theme.STYLE_DIM), box=theme.BOX_STYLE, border_style=theme.STYLE_DIM, title="details")

    async def on_enter(self): pass
    async def on_leave(self): pass
    @abstractmethod
    async def handle_input(self, key: str): pass
    async def handle_hover(self, component_id: int, item_index: Optional[int]): pass

# --- three pane view for browsing ---
class ThreePaneView(View):
    def __init__(self, app: 'TUIApp', nav_items: List[Tuple[str, Callable]], content_loader: Callable):
        super().__init__(app)
        self.content_loader = content_loader
        self.nav_list = self._create_nav_list(nav_items)
        self.content_list: Optional[SelectableList] = None
        self.active_list: Optional[SelectableList] = self.nav_list

        self.layout.split_row(
            Layout(self.nav_list, name="nav", size=30),
            Layout(name="main"),
            Layout(self.detail_pane, name="detail", size=40),
        )
        self.layout["main"].update(Panel(Align.center("select an item to begin.", style=theme.STYLE_DIM), box=theme.BOX_STYLE))

    def _create_nav_list(self, items) -> SelectableList:
        nav_list = SelectableList(items, self.format_nav_item, title="library")
        nav_list.on_select = self.on_nav_select
        nav_list.is_focused = True
        return nav_list
        
    def format_nav_item(self, item: Tuple, is_focused: bool, is_hover: bool) -> Text:
        name, _ = item
        style = theme.STYLE_FOCUSED if is_focused else theme.STYLE_INVERSE if is_hover else theme.STYLE_NORMAL
        return Text.assemble((" > " if is_focused or is_hover else "   "), (name, style))
        
    async def on_nav_select(self, item: Tuple):
        name, loader = item
        self.app.set_header_path([name])
        content_items = await loader()
        
        self.content_list = SelectableList(content_items, self.format_content_item, title=name)
        self.content_list.on_select = self.on_content_select
        self.content_list.on_change = self.on_content_change
        
        self.layout["main"].update(self.content_list)
        await self.on_content_change(self.content_list.selected_item) # load initial detail view
        self._switch_focus()

    def _switch_focus(self):
        self.active_list.is_focused = False
        if self.active_list == self.nav_list and self.content_list:
            self.active_list = self.content_list
        else:
            self.active_list = self.nav_list
        self.active_list.is_focused = True

    async def handle_input(self, key: str):
        if key in ("j", "down"): self.active_list.move(1)
        elif key in ("k", "up"): self.active_list.move(-1)
        elif key == "tab": self._switch_focus()
        elif key == "enter": self.active_list.on_select(self.active_list.selected_item)

    async def handle_hover(self, component_id: int, item_index: Optional[int]):
        for component in (self.nav_list, self.content_list):
            if component and id(component) == component_id:
                component.hover_index = item_index if item_index is not None else -1

    @abstractmethod
    def format_content_item(self, item: Any, is_focused: bool, is_hover: bool) -> Text: pass
    
    @abstractmethod
    async def on_content_select(self, item: Any): pass
    
    async def on_content_change(self, item: Any):
        if item:
            # default detail view, can be overridden
            self.detail_pane.renderable = Align.center(f"selected: {escape(item.title or item.name)}", style=theme.STYLE_DIM)
        else:
            self.detail_pane.renderable = Align.center("no selection", style=theme.STYLE_DIM)
        

# --- specific view implementations ---

class HomeView(ThreePaneView):
    def __init__(self, app: 'TUIApp'):
        nav_items = [
            ("playlists", self.api.get_user_playlists),
            # add more here, e.g. ("favorite albums", self.api.get_user_favorite_albums)
        ]
        super().__init__(app, nav_items, self.api.get_user_playlists)

    def format_content_item(self, item: models.Playlist, is_focused: bool, is_hover: bool) -> Text:
        style = theme.STYLE_FOCUSED if is_focused else theme.STYLE_INVERSE if is_hover else theme.STYLE_NORMAL
        return Text.assemble((" > " if is_focused or is_hover else "   "), (item.title or "untitled", style))

    async def on_content_select(self, item: models.Playlist):
        tracks = await self.api.get_playlist_tracks(item.id)
        await self.app.push_view(TrackView(self.app, tracks, item.title))
        
    async def on_content_change(self, item: Any):
        if isinstance(item, models.Playlist):
            text = Text()
            text.append(f"{item.title}\n\n", style="bold")
            text.append(f"{item.number_of_tracks} tracks\n", style="dim")
            text.append(f"by {item.creator.name if item.creator else 'unknown'}", style="dim")
            self.detail_pane.renderable = text
        else:
            await super().on_content_change(item)

class TrackView(View):
    def __init__(self, app: 'TUIApp', tracks: List[models.Track], title: str):
        super().__init__(app)
        self.title = title
        self.track_list = SelectableList(tracks, self.format_track, title)
        self.track_list.on_select = self.on_track_select
        self.track_list.is_focused = True
        self.layout.update(self.track_list)

    async def on_enter(self):
        self.app.set_header_path([self.title])
    
    def format_track(self, track: models.Track, is_focused: bool, is_hover: bool) -> Text:
        style = theme.STYLE_FOCUSED if is_focused else theme.STYLE_INVERSE if is_hover else theme.STYLE_NORMAL
        num = f"{track.track_number: >2}." if track.track_number else "  "
        artist = track.artist.name if track.artist else "unknown artist"
        return Text.assemble((f" {num} ", theme.STYLE_DIM), (track.title or "", style), (f"  {artist}", theme.STYLE_DIM), (f" ({track.duration_str})", theme.STYLE_DIM))

    async def on_track_select(self, track: models.Track):
        if not track: return
        details = await self.api.get_stream_details(track.id)
        if details.url:
            self.player.play(track, details.url)

    async def handle_input(self, key: str):
        if key in ("j", "down"): self.track_list.move(1)
        elif key in ("k", "up"): self.track_list.move(-1)
        elif key == "enter": await self.on_track_select(self.track_list.selected_item)

    async def handle_hover(self, component_id: int, item_index: Optional[int]):
        if id(self.track_list) == component_id:
            self.track_list.hover_index = item_index if item_index is not None else -1
