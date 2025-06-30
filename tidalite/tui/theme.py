# tidalite/tui/theme.py

from rich import box

# styles
STYLE_NORMAL = "white"
STYLE_DIM = "dim"
STYLE_BOLD = "bold"
STYLE_FOCUSED = "bold yellow"
STYLE_INVERSE = "black on white"
STYLE_ERROR = "bold red"

# component styles
STYLE_HEADER = "bold"
STYLE_SIDEBAR_TITLE = "bold"
STYLE_DETAIL_PANE_TITLE = "bold"

STYLE_FOOTER_PLAYING = "bold"
STYLE_FOOTER_PAUSED = "dim"

STYLE_PROGRESS_PLAYING = "white"
STYLE_PROGRESS_PAUSED = "bright_black"

# clickable button styles
STYLE_BUTTON = "white"
STYLE_BUTTON_HOVER = "black on white"

# box styles
BOX_STYLE = box.SIMPLE
BOX_STYLE_FOCUSED = box.HEAVY
