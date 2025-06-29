# tidalite/player.py

import httpx
import sounddevice as sd
import soundfile as sf
import threading
from typing import Optional, Dict

from .models import Track

class Player:
    def __init__(self):
        self.current_track: Optional[Track] = None
        self.playback_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        
        self.stream: Optional[sd.OutputStream] = None
        self.position = 0
        self.duration = 0
        self.is_paused = False

    def play(self, track: Track, url: str):
        self.stop() # stop any currently playing track
        self.current_track = track
        self.duration = track.duration
        self.position = 0
        self.is_paused = False

        self.stop_event.clear()
        self.pause_event.set() # set to "playing" state

        self.playback_thread = threading.Thread(target=self._stream_audio, args=(url,), daemon=True)
        self.playback_thread.start()

    def _stream_audio(self, url: str):
        """this function runs in a separate thread to not block the tui."""
        try:
            with httpx.stream("GET", url) as response:
                response.raise_for_status()
                with sf.SoundFile(response, 'r') as snd_file:
                    self.stream = sd.OutputStream(
                        samplerate=snd_file.samplerate,
                        channels=snd_file.channels,
                        dtype='float32' # use float32 for better quality
                    )
                    self.stream.start()
                    
                    blocksize = 1024 * 16 # read in 16kb chunks
                    while not self.stop_event.is_set():
                        self.pause_event.wait() # this will block if paused
                        data = snd_file.read(blocksize, dtype='float32')
                        if len(data) == 0:
                            break # end of file
                        
                        self.stream.write(data)
                        self.position += len(data) / snd_file.samplerate

        except Exception:
            # handle potential errors like network issues or invalid audio files
            pass
        finally:
            if self.stream:
                self.stream.stop()
                self.stream.close()
            # once the stream finishes or is stopped, clear the track
            self.current_track = None

    def toggle_pause(self):
        if not self.current_track:
            return
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.pause_event.clear() # clear event to pause the loop
        else:
            self.pause_event.set() # set event to resume the loop

    def stop(self):
        if self.playback_thread and self.playback_thread.is_alive():
            self.stop_event.set()
            self.pause_event.set() # unblock if paused
            self.playback_thread.join(timeout=0.5)
        
        self.current_track = None
        self.position = 0
        self.is_paused = False

    @property
    def status(self) -> Dict:
        if not self.current_track:
            return {"state": "stopped", "track": None, "position": 0, "duration": 0, "paused": True}
        
        return {
            "state": "paused" if self.is_paused else "playing",
            "track": self.current_track,
            "position": self.position,
            "duration": self.duration,
            "paused": self.is_paused,
        }
