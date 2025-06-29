# tidalite/tui/theme.py

from rich import box

# styles
STYLE_NORMAL = "white"
STYLE_DIM = "dim"
STYLE_BOLD = "bold"
STYLE_FOCUSED = "bold yellow" # the only exception for focus indication
STYLE_HEADER = "bold"
STYLE_FOOTER_PLAYING = "bold"
STYLE_FOOTER_PAUSED = "dim"
STYLE_PROGRESS_PLAYING = "white"
STYLE_PROGRESS_PAUSED = "bright_black"

# box styles
BOX_STYLE = box.SIMPLE
