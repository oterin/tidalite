# tidalite/models.py

from typing import Optional, List, Union
from pydantic import BaseModel, Field

# base models to avoid repetition
class BaseItem(BaseModel):
    id: Union[int, str]
    name: Optional[str] = None # playlists use 'title'
    title: Optional[str] = None # artists use 'name'

    class Config:
        allow_population_by_field_name = True
        extra = 'ignore' # ignore extra fields from api

# --- item models ---
class Artist(BaseItem):
    type: Optional[str] = None

class Album(BaseItem):
    cover: Optional[str] = None
    explicit: Optional[bool] = None
    audio_quality: Optional[str] = Field(None, alias='audioQuality')
    
class Track(BaseItem):
    duration: int
    track_number: Optional[int] = Field(None, alias='trackNumber')
    volume_number: Optional[int] = Field(None, alias='volumeNumber')
    artist: Optional[Artist]
    artists: List[Artist]
    album: Optional[Album]
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
    artist: Optional[Artist]
    artists: List[Artist]
    album: Optional[Album]

class Playlist(BaseItem):
    uuid: str
    description: Optional[str] = None
    number_of_tracks: int = Field(0, alias='numberOfTracks')
    number_of_videos: int = Field(0, alias='numberOfVideos')
    creator: Optional[Artist] = Field(None)
    
    @property
    def id(self) -> str: # playlists are identified by uuid
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
    sound_quality: str = Field(..., alias='soundQuality')
    codec: Optional[str] = None
    manifest_mime_type: Optional[str] = Field(None, alias='manifestMimeType')
    manifest: Optional[str] = None
    
# --- search result models ---
class SearchResults(BaseModel):
    artists: List[Artist] = []
    albums: List[Album] = []
    tracks: List[Track] = []
    playlists: List[Playlist] = []
