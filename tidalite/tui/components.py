# tidalite/tui/components.py

from typing import List, Any, Callable, Optional
from rich.panel import Panel
from rich.text import Text
from rich.progress_bar import ProgressBar
from rich.align import Align

from . import theme
from ..player import Player

# --- header ---
class Header:
    def __init__(self):
        self.path: List[str] = ["tidalite"]

    def __rich__(self) -> Panel:
        path_str = " / ".join(self.path)
        header_text = Text()
        header_text.append("tidalite", style=theme.STYLE_BOLD)
        if len(self.path) > 1:
            header_text.append(" / ", style=theme.STYLE_DIM)
            header_text.append(" / ".join(self.path[1:]), style=theme.STYLE_DIM)
        return Panel(Align.center(header_text), box=theme.BOX_STYLE, border_style=theme.STYLE_DIM)

# --- footer / now playing bar ---
class Footer:
    def __init__(self, player: Player):
        self.player = player

    def __rich__(self) -> Panel:
        status = self.player.status
        if status['state'] == 'stopped':
            return Panel(Align.center(Text("stopped", style=theme.STYLE_DIM)), box=theme.BOX_STYLE, border_style=theme.STYLE_DIM)
            
        track, pos, dur, paused = status['track'], status['position'], status['duration'], status['paused']
        is_playing = not paused

        # progress bar
        progress = ProgressBar(
            total=dur, completed=pos, 
            complete_style=theme.STYLE_PROGRESS_PLAYING if is_playing else theme.STYLE_PROGRESS_PAUSED,
            style=theme.STYLE_DIM
        )
        
        # text content
        state_icon = "" if is_playing else ""
        duration_str = f"{int(pos//60)}:{int(pos%60):02d} / {track.duration_str}"
        
        footer_style = theme.STYLE_FOOTER_PLAYING if is_playing else theme.STYLE_FOOTER_PAUSED
        content_text = Text()
        content_text.append(f"{state_icon} {track.display_title}", style=footer_style)
        content_text.append(f"  {duration_str}", style=theme.STYLE_DIM)

        # combine and return panel
        return Panel(Text.assemble(content_text, "\n", progress), box=theme.BOX_STYLE, border_style=footer_style)

# --- generic selectable list ---
class SelectableList:
    def __init__(
        self,
        items: List[Any],
        formatter: Callable[[Any, bool], str],
        title: Optional[str] = None,
    ):
        self.items = items
        self.formatter = formatter
        self.title = title
        self.selected_index = 0
        self.scroll_offset = 0
        self.is_focused = False

    def move(self, direction: int):
        self.selected_index = max(0, min(len(self.items) - 1, self.selected_index + direction))

    @property
    def selected_item(self) -> Optional[Any]:
        return self.items[self.selected_index] if self.items else None

    def __rich_console__(self, console, options):
        height = options.max_height
        
        # auto-scrolling logic
        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        if self.selected_index >= self.scroll_offset + height:
            self.scroll_offset = self.selected_index - height + 1
            
        text = Text()
        for i in range(self.scroll_offset, min(len(self.items), self.scroll_offset + height)):
            is_selected = (i == self.selected_index)
            line = self.formatter(self.items[i], is_selected and self.is_focused)
            text.append(line + "\n")
        
        panel = Panel(
            text,
            title=self.title if self.title else "",
            box=theme.BOX_STYLE,
            border_style=theme.STYLE_BOLD if self.is_focused else theme.STYLE_DIM
        )
        yield panel
