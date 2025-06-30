# tidalite/api.py

import json
import base64
from typing import Optional, List, Dict, Any

import httpx
from . import auth, config, models

class APIClient:
    def __init__(self, creds: models.Credentials):
        self._client = httpx.AsyncClient(http2=True)
        self.creds = creds
        self.country_code = creds.user.get('countryCode', 'US')

    def update_credentials(self, creds: models.Credentials):
        """Update the credentials, e.g., after a token refresh."""
        self.creds = creds

    async def _request(self, method: str, url: str, params: Optional[dict] = None, data: Optional[dict] = None) -> httpx.Response:
        """Makes an authenticated request to the Tidal API."""
        if not self.creds or not self.creds.access_token:
            raise ConnectionError("not authenticated. please restart tidalite.")

        headers = {
            "authorization": f"Bearer {self.creds.access_token}",
            "user-agent": "TIDAL_ANDROID/1039 okhttp/4.2.2"
        }
        
        final_params = {"countryCode": self.country_code}
        if params:
            final_params.update(params)

        try:
            response = await self._client.request(method, url, params=final_params, headers=headers, json=data)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            # provide more detailed error information
            error_details = f"{e.response.status_code} {e.response.reason_phrase}"
            if e.response.status_code == 401:
                raise ConnectionError(f"authentication failed: {error_details}. please login again.")
            elif e.response.status_code == 404:
                raise ValueError(f"resource not found: {error_details}. url: {url}")
            elif e.response.status_code == 403:
                raise PermissionError(f"access forbidden: {error_details}. check your subscription.")
            else:
                raise ConnectionError(f"api error: {error_details}")

    async def check_login(self) -> bool:
        """Checks if the current access token is valid."""
        try:
            await self._request("get", f"{config.api_url_v1}/users/{self.creds.user_id}/subscription")
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return False
            raise
        except (ConnectionError, PermissionError):
            return False

    async def get_user_playlists(self) -> List[models.Playlist]:
        res = await self._request("get", f"{config.api_url_v1}/users/{self.creds.user_id}/playlists")
        return [models.Playlist(**p) for p in res.json()['items']]

    async def get_user_favorite_albums(self) -> List[models.Album]:
        res = await self._request("get", f"{config.api_url_v1}/users/{self.creds.user_id}/favorites/albums")
        return [models.Album(**a['item']) for a in res.json()['items'] if a.get('item')]
        
    async def get_user_favorite_tracks(self) -> List[models.Track]:
        res = await self._request("get", f"{config.api_url_v1}/users/{self.creds.user_id}/favorites/tracks")
        return [models.Track(**t['item']) for t in res.json()['items'] if t.get('item')]

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
        params = {"audioquality": "LOSSLESS", "playbackmode": "STREAM", "assetpresentation": "FULL"}
        res = await self._request("get", f"{config.desktop_api_url}/tracks/{track_id}/playbackinfo", params=params)
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

    async def get_track(self, track_id:int)->models.Track:
        res=await self._request("get",f"{config.api_url_v1}/tracks/{track_id}")
        return models.Track(**res.json())

    async def close(self):
        await self._client.aclose()
