# tidalite/player.py

import mpv
from typing import Optional, Dict

from .models import Track

class Player:
    def __init__(self):
        try:
            # configure mpv for terminal-only operation
            self._player = mpv.MPV(
                ytdl=False, 
                input_default_bindings=True,
                input_vo_keyboard=True,
                vo='null' # no video window
            )
            self.current_track: Optional[Track] = None
            self.queue: list[tuple[Track, str]] = []
        except FileNotFoundError:
            raise RuntimeError("mpv is not installed or not in your path.")

    def play(self, track: Track, url: str):
        self.current_track = track
        self._player.play(url)
        self._player['pause'] = False
        
    def toggle_pause(self):
        if self.current_track:
            self._player['pause'] = not self._player['pause']

    def stop(self):
        self.current_track = None
        self._player.stop()

    def next(self):
        if self.queue:
            track, url = self.queue.pop(0)
            self.play(track, url)
        else:
            self.stop()
            
    @property
    def status(self) -> Dict:
        if not self.current_track or self._player.playback_abort:
            return {"state": "stopped", "track": None, "position": 0, "duration": 0, "paused": True}

        # check if track has finished
        if self._player.percent_pos is not None and self._player.percent_pos >= 100:
             self.next() # play next in queue or stop
             # return the old status for one last frame to avoid flicker
             return self.status
        
        return {
            "state": "playing" if not self._player.pause else "paused",
            "track": self.current_track,
            "position": self._player.playback_time or 0,
            "duration": self._player.duration or self.current_track.duration,
            "paused": self._player.pause,
        }
