# tidalite/models.py

from typing import Optional, List, Union, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

# --- Auth Models ---
class Credentials(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str
    expires_in: int
    user: dict # user info can be nested
    scope: str
    user_id: int
    expires_at: Optional[float] = None

# base models to avoid repetition
class BaseItem(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        extra='ignore'  # ignore extra fields from api
    )
    
    id: Union[int, str]
    name: Optional[str] = None # playlists use 'title'
    title: Optional[str] = None # artists use 'name'

# --- item models ---
class Artist(BaseItem):
    type: Optional[str] = None

class Album(BaseItem):
    cover: Optional[str] = None
    explicit: Optional[bool] = None
    audio_quality: Optional[str] = Field(None, alias='audioQuality')
    artist: Optional[Artist] = None  # some albums have artist info
    number_of_tracks: Optional[int] = Field(None, alias='numberOfTracks')
    
class Track(BaseItem):
    duration: int
    track_number: Optional[int] = Field(None, alias='trackNumber')
    volume_number: Optional[int] = Field(None, alias='volumeNumber')
    artist: Optional[Artist] = None
    artists: Optional[List[Artist]] = []
    album: Optional[Album] = None
    audio_quality: Optional[str] = Field(None, alias='audioQuality')
    explicit: Optional[bool] = None

    @property
    def display_title(self) -> str:
        if self.artist:
            return f"{self.artist.name} - {self.title}"
        return self.title or "untitled"

    @property
    def duration_str(self) -> str:
        mins, secs = divmod(self.duration, 60)
        return f"{mins}:{secs:02d}"

class Video(BaseItem):
    duration: int
    image_id: Optional[str] = Field(None, alias='imageId')
    artist: Optional[Artist] = None
    artists: Optional[List[Artist]] = []
    album: Optional[Album] = None

class Playlist(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        extra='ignore'  # ignore extra fields from api
    )
    
    uuid: str
    title: Optional[str] = None
    description: Optional[str] = None
    number_of_tracks: int = Field(0, alias='numberOfTracks')
    number_of_videos: int = Field(0, alias='numberOfVideos')
    creator: Optional[Dict[str, Any]] = None  # keep as flexible dict to avoid validation issues
    
    @property
    def id(self) -> str:
        """Playlists are identified by uuid."""
        return self.uuid

# --- response models for specific endpoints ---
class Page(BaseModel):
    # for home, explore, etc.
    id: str
    title: str
    rows: List

class Mix(BaseItem):
    mix_type: str = Field(..., alias='mixType')

class ArtistBio(BaseModel):
    source: str
    text: str
    summary: str

class StreamDetails(BaseModel):
    url: Optional[str] = None
    track_id: int = Field(..., alias='trackId')
    audio_quality: str = Field(..., alias='audioQuality')
    asset_presentation: Optional[str] = Field(None, alias='assetPresentation')
    audio_mode: Optional[str] = Field(None, alias='audioMode')
    streaming_session_id: Optional[str] = Field(None, alias='streamingSessionId')
    codec: Optional[str] = None
    manifest_mime_type: Optional[str] = Field(None, alias='manifestMimeType')
    manifest_hash: Optional[str] = Field(None, alias='manifestHash')
    manifest: Optional[str] = None
    album_replay_gain: Optional[float] = Field(None, alias='albumReplayGain')
    album_peak_amplitude: Optional[float] = Field(None, alias='albumPeakAmplitude')
    track_replay_gain: Optional[float] = Field(None, alias='trackReplayGain')
    track_peak_amplitude: Optional[float] = Field(None, alias='trackPeakAmplitude')
    bit_depth: Optional[int] = Field(None, alias='bitDepth')
    sample_rate: Optional[int] = Field(None, alias='sampleRate')
    
    # for backward compatibility
    @property
    def sound_quality(self) -> str:
        """Backward compatibility property."""
        return self.audio_quality

# --- search result models ---
class SearchResults(BaseModel):
    artists: List[Artist] = []
    albums: List[Album] = []
    tracks: List[Track] = []
    playlists: List[Playlist] = []
