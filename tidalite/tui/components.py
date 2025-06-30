# tidalite/tui/components.py

from typing import List, Any, Callable, Optional, Dict
from rich.panel import Panel
from rich.text import Text
from rich.progress_bar import ProgressBar
from rich.align import Align
from rich.console import Renderable, Console, ConsoleOptions, RenderResult
from rich.segment import Segments
from rich.style import Style

from . import theme
from ..player import Player
from ..models import Track

# --- base clickable component ---
class Clickable(Renderable):
    """a base class for components that can be clicked."""
    def __init__(self, renderable: Renderable, on_click: Optional[Callable] = None, metadata: Optional[Dict] = None):
        self.renderable = renderable
        self.on_click = on_click
        self.metadata = metadata or {}
        self.is_hovering = False

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        segments = console.render(self.renderable, options)
        style = theme.STYLE_BUTTON_HOVER if self.is_hovering else theme.STYLE_BUTTON
        # wrap the component with metadata for the event system
        for segment in segments:
            meta = {
                "@click": "app.dispatch_click",
                "on_click": self.on_click,
                **self.metadata
            }
            yield segment.apply_meta(meta).with_style(style)

# --- footer / now playing bar ---
class Footer:
    def __init__(self, player: Player):
        self.player = player

    def __rich__(self) -> Panel:
        status = self.player.status
        is_playing = status['state'] == 'playing'
        is_paused = status['state'] == 'paused'

        # playback control buttons
        play_pause_icon = "⏸" if is_playing else "▶"
        play_pause_button = Clickable(Text(play_pause_icon), self.player.toggle_pause)
        stop_button = Clickable(Text("■"), self.player.stop)

        # text content and progress bar
        if is_playing or is_paused:
            track, pos, dur = status['track'], status['position'], status['duration']
            progress = ProgressBar(
                total=dur, completed=pos,
                complete_style=theme.STYLE_PROGRESS_PLAYING if is_playing else theme.STYLE_PROGRESS_PAUSED,
                style=theme.STYLE_DIM
            )
            duration_str = f"{int(pos//60)}:{int(pos%60):02d} / {track.duration_str}"
            footer_style = theme.STYLE_FOOTER_PLAYING if is_playing else theme.STYLE_FOOTER_PAUSED

            content_text = Text(f" {track.display_title}", style=footer_style)
            content_text.append(f"  {duration_str}", style=theme.STYLE_DIM)

            controls_and_info = Text.assemble(
                " ", play_pause_button, " ", stop_button, " ", content_text
            )
            renderable = Text.assemble(controls_and_info, "\n", progress)
            border_style = footer_style
        else:
            renderable = Align.center(Text("stopped", style=theme.STYLE_DIM))
            border_style = theme.STYLE_DIM

        return Panel(renderable, box=theme.BOX_STYLE, border_style=border_style)

# --- generic selectable list with mouse support ---
class SelectableList:
    def __init__(self, items: List[Any], formatter: Callable[[Any, bool, bool], str], title: Optional[str] = None):
        self.items = items
        self.formatter = formatter
        self.title = title
        self.selected_index = 0
        self.scroll_offset = 0
        self.is_focused = False
        self.on_select: Optional[Callable[[Any], None]] = None
        self.on_change: Optional[Callable[[Any], None]] = None
        self.hover_index = -1

    def handle_click(self, item_index: int):
        self.selected_index = item_index
        if self.on_select:
            self.on_select(self.selected_item)
            
    def move(self, direction: int):
        new_index = max(0, min(len(self.items) - 1, self.selected_index + direction))
        if new_index != self.selected_index:
            self.selected_index = new_index
            if self.on_change:
                self.on_change(self.selected_item)

    @property
    def selected_item(self) -> Optional[Any]:
        return self.items[self.selected_index] if self.items else None

    def __rich_console__(self, console, options):
        height = options.max_height
        
        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        if self.selected_index >= self.scroll_offset + height:
            self.scroll_offset = self.selected_index - height + 1
            
        text = Text()
        for i in range(self.scroll_offset, min(len(self.items), self.scroll_offset + height)):
            is_selected = (i == self.selected_index)
            is_hovering = (i == self.hover_index)
            line = self.formatter(self.items[i], is_selected and self.is_focused, is_hovering)
            
            # add metadata for mouse events
            meta = {
                "@click": "app.dispatch_click",
                "on_click": self.handle_click,
                "item_index": i,
                "@mouse.enter": f"app.dispatch_hover",
                "component_id": id(self),
                "hover_item_index": i,
                "@mouse.leave": f"app.dispatch_hover",
            }
            text.append(line, style=Style.from_meta(meta))
            text.append("\n")
        
        panel = Panel(
            text,
            title=self.title if self.title else "",
            box=theme.BOX_STYLE_FOCUSED if self.is_focused else theme.BOX_STYLE,
            border_style=theme.STYLE_FOCUSED if self.is_focused else theme.STYLE_DIM
        )
        yield panel
