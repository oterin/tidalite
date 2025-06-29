# tidalite/tui/views.py

import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional, Any

from rich.layout import Layout
from rich.align import Align
from rich.text import Text
from rich.panel import Panel

from . import theme
from .components import SelectableList
from .. import models, api, player

# --- view base class ---
class View(ABC):
    def __init__(self, app: 'TUIApp'):
        self.app = app
        self.api: api.APIClient = app.api
        self.player: player.Player = app.player
        self.layout = Layout()

    async def on_enter(self):
        """called when the view becomes active."""
        pass
    
    async def on_leave(self):
        """called when the view is popped from the stack."""
        pass

    @abstractmethod
    async def handle_input(self, key: str):
        """process user input."""
        pass

# --- list-based view ---
class ListView(View):
    def __init__(self, app: 'TUIApp', items: List[Any], title: str, item_formatter):
        super().__init__(app)
        self.title = title
        self.list = SelectableList(items, title=title, formatter=item_formatter)
        self.list.is_focused = True
        self.layout.update(self.list)

    async def on_enter(self):
        self.app.set_header_path([self.title])

    async def handle_input(self, key: str):
        if key in ("j", "down"):
            self.list.move(1)
        elif key in ("k", "up"):
            self.list.move(-1)
        elif key == "enter":
            await self.on_select()
    
    async def on_select(self):
        item = self.list.selected_item
        if isinstance(item, models.Playlist):
            tracks = await self.api.get_playlist_tracks(item.id)
            await self.app.push_view(TrackListView(self.app, tracks, item.title))
        elif isinstance(item, models.Album):
            tracks = await self.api.get_album_tracks(item.id)
            await self.app.push_view(TrackListView(self.app, tracks, item.title))
        elif isinstance(item, models.Artist):
            await self.app.push_view(ArtistView(self.app, item))

# --- track list view ---
class TrackListView(ListView):
    def __init__(self, app: 'TUIApp', tracks: List[models.Track], title: str):
        super().__init__(app, tracks, title, self.format_track)
    
    def format_track(self, track: models.Track, is_focused: bool) -> str:
        style = theme.STYLE_FOCUSED if is_focused else theme.STYLE_BOLD
        num = f"{track.track_number: >2}." if track.track_number else "  "
        return Text.assemble((f" {num} ", theme.STYLE_DIM), (track.title or "", style), (f" ({track.duration_str})", theme.STYLE_DIM))

    async def on_select(self):
        track = self.list.selected_item
        if not track: return
        details = await self.api.get_stream_details(track.id)
        if details.url:
            self.player.play(track, details.url)

# --- home navigation view ---
class HomeView(ListView):
    def __init__(self, app: 'TUIApp'):
        items = ["my playlists", "my favorite albums", "my favorite artists", "search"]
        super().__init__(app, items, "home", lambda i, f: Text.assemble((" > " if f else "   "), (i, theme.STYLE_FOCUSED if f else theme.STYLE_NORMAL)))

    async def on_enter(self):
        self.app.set_header_path([])

    async def on_select(self):
        item = self.list.selected_item
        if item == "my playlists":
            playlists = await self.api.get_user_playlists()
            await self.app.push_view(ListView(self.app, playlists, "playlists", lambda p,f: Text.assemble((" > " if f else "   "), (p.title, theme.STYLE_FOCUSED if f else theme.STYLE_NORMAL))))
        elif item == "search":
             await self.app.push_view(SearchView(self.app))

# --- artist detail view ---
class ArtistView(View):
    def __init__(self, app: 'TUIApp', artist: models.Artist):
        super().__init__(app)
        self.artist = artist
        self.bio: Optional[models.ArtistBio] = None
        self.top_tracks: List[models.Track] = []
        self.albums: List[models.Album] = []
        self.active_list: Optional[SelectableList] = None
        
        self.layout.split_column(Layout(name="bio"), Layout(name="lists"))
        self.layout["lists"].split_row(Layout(name="tracks"), Layout(name="albums"))

    async def on_enter(self):
        self.app.set_header_path([self.artist.name or "artist"])
        self.bio, self.top_tracks, self.albums = await asyncio.gather(
            self.api.get_artist_bio(self.artist.id),
            self.api.get_artist_top_tracks(self.artist.id),
            self.api.get_artist_albums(self.artist.id)
        )
        self.layout["bio"].update(Panel(self.bio.text, title="biography", box=theme.BOX_STYLE, border_style=theme.STYLE_DIM))
        self.track_list = SelectableList(self.top_tracks, title="top tracks", formatter=lambda t,f: Text.assemble((" > " if f else "   "), (t.title or "", theme.STYLE_FOCUSED if f else theme.STYLE_NORMAL)))
        self.album_list = SelectableList(self.albums, title="albums", formatter=lambda a,f: Text.assemble((" > " if f else "   "), (a.title or "", theme.STYLE_FOCUSED if f else theme.STYLE_NORMAL)))
        self.active_list = self.track_list
        self.active_list.is_focused = True
        self.layout["tracks"].update(self.track_list)
        self.layout["albums"].update(self.album_list)

    async def handle_input(self, key: str):
        if key in ("j", "down"): self.active_list.move(1)
        elif key in ("k", "up"): self.active_list.move(-1)
        elif key == "tab": self._switch_pane()
        elif key == "enter":
            item = self.active_list.selected_item
            if isinstance(item, models.Track):
                details = await self.api.get_stream_details(item.id)
                if details.url: self.player.play(item, details.url)
            elif isinstance(item, models.Album):
                await self.app.push_view(TrackListView(self.app, await self.api.get_album_tracks(item.id), item.title or "album"))
    
    def _switch_pane(self):
        self.active_list.is_focused = False
        self.active_list = self.album_list if self.active_list == self.track_list else self.track_list
        self.active_list.is_focused = True

# --- search view ---
class SearchView(View):
    # a basic search view; could be expanded with a proper text input component
    def __init__(self, app: 'TUIApp'):
        super().__init__(app)
        self.query = ""
        self.layout.update(self.render())

    def render(self) -> Panel:
        return Panel(Align.center(f"search query: {self.query}_"), title="search", box=theme.BOX_STYLE, border_style=theme.STYLE_BOLD)

    async def on_enter(self):
        self.app.set_header_path(["search"])

    async def handle_input(self, key: str):
        if key == "enter":
            if not self.query: return
            results = await self.api.search(self.query)
            # for now, just show tracks from search
            await self.app.push_view(TrackListView(self.app, results.tracks, f"search results for '{self.query}'"))
        elif key == "backspace":
            self.query = self.query[:-1]
        elif len(key) == 1:
            self.query += key
        self.layout.update(self.render())
