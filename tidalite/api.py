# tidalite/api.py

import json
import base64
from typing import Optional, List, Dict, Any

import httpx
from . import auth, config, models

class APIClient:
    def __init__(self):
        self._client = httpx.AsyncClient(http2=True)
        self.user: Optional[Dict[str, Any]] = None
        self.country_code: Optional[str] = None

    async def _request(self, method: str, url: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> httpx.Response:
        creds = await auth.get_valid_credentials()
        if not creds:
            raise ConnectionError("not authenticated. please restart tidalite.")
        
        if not self.user:
            self.user = creds.get('user')
            self.country_code = self.user.get('countryCode') if self.user else 'us'

        headers = {"authorization": f"bearer {creds['access_token']}"}
        if params is None:
            params = {}
        if "countryCode" not in params:
            params["countryCode"] = self.country_code

        response = await self._client.request(method, url, params=params, headers=headers, json=data)
        response.raise_for_status()
        return response

    async def get_user_playlists(self) -> List[models.Playlist]:
        if not self.user: return []
        res = await self._request("get", f"{config.api_url_v1}/users/{self.user['userId']}/playlistsandfavoriteplaylists")
        return [models.Playlist(**p) for p in res.json()['items']]

    async def get_playlist_tracks(self, playlist_id: str) -> List[models.Track]:
        res = await self._request("get", f"{config.api_url_v1}/playlists/{playlist_id}/items")
        return [models.Track(**t['item']) for t in res.json()['items'] if t.get('item')]

    async def get_album_tracks(self, album_id: int) -> List[models.Track]:
        res = await self._request("get", f"{config.api_url_v1}/albums/{album_id}/items")
        return [models.Track(**t['item']) for t in res.json()['items'] if t.get('item')]

    async def get_artist_top_tracks(self, artist_id: int) -> List[models.Track]:
        res = await self._request("get", f"{config.api_url_v1}/artists/{artist_id}/toptracks")
        return [models.Track(**t) for t in res.json()['items']]
        
    async def get_artist_albums(self, artist_id: int) -> List[models.Album]:
        res = await self._request("get", f"{config.api_url_v1}/artists/{artist_id}/albums")
        return [models.Album(**a) for a in res.json()['items']]

    async def get_artist_bio(self, artist_id: int) -> models.ArtistBio:
        res = await self._request("get", f"{config.api_url_v1}/artists/{artist_id}/bio")
        return models.ArtistBio(**res.json())

    async def search(self, query: str) -> models.SearchResults:
        params = {"query": query, "types": "artists,albums,playlists,tracks", "limit": 20}
        res = await self._request("get", f"{config.api_url_v1}/search", params=params)
        data = res.json()
        return models.SearchResults(
            artists=[models.Artist(**a) for a in data.get('artists', {}).get('items', [])],
            albums=[models.Album(**a) for a in data.get('albums', {}).get('items', [])],
            playlists=[models.Playlist(**p) for p in data.get('playlists', {}).get('items', [])],
            tracks=[models.Track(**t) for t in data.get('tracks', {}).get('items', [])],
        )

    async def get_stream_details(self, track_id: int) -> models.StreamDetails:
        params = {"audioquality": "lossless", "playbackmode": "stream", "assetpresentation": "full"}
        res = await self._request("get", f"{config.api_url_v1}/tracks/{track_id}/playbackinfopostpaywall", params=params)
        data = res.json()
        
        if data.get('manifestMimeType') == "application/vnd.tidal.bts":
            manifest_data = json.loads(base64.b64decode(data['manifest']).decode('utf-8'))
            data['url'] = manifest_data['urls'][0]
            data['codec'] = manifest_data.get('codecs')
        else:
            # basic fallback for non-bts manifests, may not always work
            data['url'] = data.get('urls', [None])[0]

        return models.StreamDetails(**data)
        
    async def get_page(self, page_name: str) -> dict:
        # e.g., pages/home, pages/explore
        res = await self._request("get", f"{config.api_url_v1}/pages/{page_name}")
        return res.json()

    async def close(self):
        await self._