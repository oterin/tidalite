# tidalite/main.py

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Optional, List

import typer
import httpx
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.text import Text

from . import auth, config, api, player
from .models import Credentials, Track, Album, Playlist, Artist

app = typer.Typer(
    name="tidalite",
    help="A lightweight Tidal client for your terminal with full API access.",
    add_completion=False,
)
console = Console()

# global api client
api_client: Optional[api.APIClient] = None
audio_player = player.Player()

def get_api_client() -> api.APIClient:
    """Get authenticated API client."""
    global api_client
    if not api_client:
        console.print("[red]not authenticated. run 'tidalite login' first.[/red]")
        raise typer.Exit(1)
    return api_client

async def ensure_authenticated():
    """Ensure user is authenticated and refresh token if needed."""
    global api_client
    
    creds_dict = config.get_auth_credentials()
    creds = Credentials(**creds_dict) if creds_dict else None

    if not creds:
        console.print("[red]no credentials found. run 'tidalite login' first.[/red]")
        raise typer.Exit(1)
    
    api_client = api.APIClient(creds)

    # validate credentials and refresh if needed
    if not await api_client.check_login():
        console.print("session expired, refreshing...")
        new_creds = await auth.refresh_token(creds.refresh_token)
        if not new_creds:
            console.print("[red]session refresh failed. run 'tidalite login' again.[/red]")
            config.save_auth_credentials(None)
            raise typer.Exit(1)
        config.save_auth_credentials(new_creds.dict())
        api_client.update_credentials(new_creds)
        console.print("[green]session refreshed.[/green]")

@app.command()
def login():
    """Authenticate with Tidal and save credentials."""
    async def _login():
        console.print("starting authentication flow...")
        creds = await auth.authenticate()
        if not creds:
            console.print("[red]authentication failed.[/red]")
            return
        config.save_auth_credentials(creds.dict())
        console.print("[green]authentication successful![/green]")
    
    asyncio.run(_login())

@app.command()
def logout():
    """Clear stored credentials."""
    config.save_auth_credentials(None)
    console.print("credentials cleared.")

@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of results per type"),
    type_filter: str = typer.Option("all", "--type", "-t", help="Filter by type: all, tracks, albums, artists, playlists")
):
    """Search for tracks, albums, artists, and playlists."""
    async def _search():
        await ensure_authenticated()
        client = get_api_client()
        
        with console.status(f"searching for '{query}'..."):
            results = await client.search(query)
        
        if type_filter in ("all", "tracks") and results.tracks:
            table = Table(title="🎵 Tracks")
            table.add_column("ID", style="dim")
            table.add_column("Title")
            table.add_column("Artist")
            table.add_column("Album")
            table.add_column("Duration")
            
            for track in results.tracks[:limit]:
                table.add_row(
                    str(track.id),
                    track.title or "unknown",
                    track.artist.name if track.artist else "unknown",
                    track.album.title if track.album else "unknown",
                    track.duration_str
                )
            console.print(table)
        
        if type_filter in ("all", "albums") and results.albums:
            table = Table(title="💿 Albums")
            table.add_column("ID", style="dim")
            table.add_column("Title")
            table.add_column("Artist")
            table.add_column("Tracks", justify="right")
            
            for album in results.albums[:limit]:
                table.add_row(
                    str(album.id),
                    album.title or "unknown",
                    album.artist.name if hasattr(album, 'artist') and album.artist else "various",
                    str(album.number_of_tracks) if hasattr(album, 'number_of_tracks') else "?"
                )
            console.print(table)
        
        if type_filter in ("all", "artists") and results.artists:
            table = Table(title="👤 Artists")
            table.add_column("ID", style="dim")
            table.add_column("Name")
            
            for artist in results.artists[:limit]:
                table.add_row(str(artist.id), artist.name or "unknown")
            console.print(table)
        
        if type_filter in ("all", "playlists") and results.playlists:
            table = Table(title="📋 Playlists")
            table.add_column("ID", style="dim")
            table.add_column("Title")
            table.add_column("Tracks", justify="right")
            
            for playlist in results.playlists[:limit]:
                table.add_row(
                    playlist.id,
                    playlist.title or "unknown",
                    str(playlist.number_of_tracks)
                )
            console.print(table)
    
    asyncio.run(_search())

@app.command()
def play(track_id: int = typer.Argument(..., help="Track ID to play")):
    """Play a track by ID."""
    async def _play():
        await ensure_authenticated()
        client = get_api_client()
        
        try:
            with console.status("getting stream details..."):
                stream_details = await client.get_stream_details(track_id)
            
            if not stream_details.url:
                console.print("[red]no stream url available for this track.[/red]")
                return
            
            # get track info for display
            search_results = await client.search(str(track_id))
            track = None
            for t in search_results.tracks:
                if t.id == track_id:
                    track = t
                    break
            
            if not track or not track.duration:
                try:
                    track = await client.get_track(track_id)
                except Exception:
                    from .models import Track
                    track = Track(id=track_id, title=f"Track {track_id}", duration=0)
            
            console.print(f"[green]playing:[/green] {track.display_title}")
            console.print(f"[dim]quality: {stream_details.audio_quality}[/dim]")
            console.print("[dim]press ctrl+c to stop[/dim]")
            
            audio_player.play(track, stream_details.url)
            
            # non-blocking key reader
            import sys, platform, select, msvcrt
            def read_key():
                if platform.system()=="Windows":
                    if msvcrt.kbhit():
                        return msvcrt.getch().decode(errors="ignore").lower()
                    return None
                else:
                    if not sys.stdin.isatty():
                        return None
                    dr,_,_ = select.select([sys.stdin],[],[],0)
                    if dr:
                        return sys.stdin.read(1).lower()
                    return None

            last_shown=""
            while audio_player.current_track:
                key=read_key()
                if key in ("q","\x03"):
                    break
                elif key in (" ", "p"):
                    audio_player.toggle_pause()

                status = audio_player.status
                if status["state"]=="stopped":
                    break
                pos_min = int(status["position"] // 60)
                pos_sec = int(status["position"] % 60)
                dur_min = int(status["duration"] // 60)
                dur_sec = int(status["duration"] % 60)
                state_icon = "⏸" if status["paused"] else "▶"
                line=f"{state_icon} {pos_min:02d}:{pos_sec:02d} / {dur_min:02d}:{dur_sec:02d}"
                if line!=last_shown:
                    print("\r"+line+" "*10, end="", flush=True)
                    last_shown=line

                await asyncio.sleep(0.2)
                
        except Exception as e:
            console.print(f"[red]error: {str(e)}[/red]")
    
    asyncio.run(_play())

@app.command()
def download(
    track_id: int = typer.Argument(..., help="Track ID to download"),
    output_dir: str = typer.Option("./downloads", "--output", "-o", help="Output directory"),
    quality: str = typer.Option("lossless", "--quality", "-q", help="Audio quality")
):
    """Download a track."""
    async def _download():
        await ensure_authenticated()
        client = get_api_client()
        
        try:
            with console.status("getting stream details..."):
                stream_details = await client.get_stream_details(track_id)
            
            if not stream_details.url:
                console.print("[red]no stream url available for this track.[/red]")
                return

            # get track info for filename
            search_results = await client.search(str(track_id))
            track = None
            for t in search_results.tracks:
                if t.id == track_id:
                    track = t
                    break
            
            if not track:
                filename = f"track_{track_id}.flac"
            else:
                # create safe filename
                artist = track.artist.name if track.artist else "unknown"
                title = track.title or "unknown"
                safe_artist = "".join(c for c in artist if c.isalnum() or c in (' ', '-', '_')).strip()
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
                filename = f"{safe_artist} - {safe_title}.flac"
            
            # create output directory
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            file_path = output_path / filename
            
            console.print(f"downloading to: {file_path}")
            
            # download with progress bar
            async with httpx.AsyncClient() as http_client:
                async with http_client.stream("GET", stream_details.url) as response:
                    response.raise_for_status()
                    
                    total_size = int(response.headers.get("content-length", 0))
                    
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        TaskProgressColumn(),
                        console=console
                    ) as progress:
                        task = progress.add_task("downloading...", total=total_size)
                        
                        with open(file_path, "wb") as f:
                            async for chunk in response.aiter_bytes(8192):
                                f.write(chunk)
                                progress.update(task, advance=len(chunk))
            
            console.print(f"[green]downloaded:[/green] {file_path}")
                
        except Exception as e:
            console.print(f"[red]error: {str(e)}[/red]")
    
    asyncio.run(_download())

@app.command()
def favorites():
    """Show your favorite tracks, albums, and playlists."""
    async def _favorites():
        await ensure_authenticated()
        client = get_api_client()
        
        with console.status("loading favorites..."):
            tracks = await client.get_user_favorite_tracks()
            albums = await client.get_user_favorite_albums()
            playlists = await client.get_user_playlists()
        
        if tracks:
            table = Table(title="❤️ Favorite Tracks")
            table.add_column("ID", style="dim")
            table.add_column("Title")
            table.add_column("Artist")
            table.add_column("Duration")
            
            for track in tracks[:20]:  # limit to 20
                table.add_row(
                    str(track.id),
                    track.title or "unknown",
                    track.artist.name if track.artist else "unknown",
                    track.duration_str
                )
            console.print(table)
        
        if albums:
            table = Table(title="💿 Favorite Albums")
            table.add_column("ID", style="dim")
            table.add_column("Title")
            table.add_column("Artist")
            
            for album in albums[:20]:  # limit to 20
                table.add_row(
                    str(album.id),
                    album.title or "unknown",
                    album.artist.name if album.artist else "various"
                )
            console.print(table)
        
        if playlists:
            table = Table(title="📋 Your Playlists")
            table.add_column("ID", style="dim")
            table.add_column("Title")
            table.add_column("Tracks", justify="right")
            
            for playlist in playlists[:20]:  # limit to 20
                table.add_row(
                    playlist.id,
                    playlist.title or "unknown",
                    str(playlist.number_of_tracks)
                )
            console.print(table)
    
    asyncio.run(_favorites())

@app.command()
def album(album_id: int = typer.Argument(..., help="Album ID to show tracks")):
    """Show tracks in an album."""
    async def _album():
        await ensure_authenticated()
        client = get_api_client()
        
        with console.status("loading album tracks..."):
            tracks = await client.get_album_tracks(album_id)
        
        if not tracks:
            console.print("[yellow]no tracks found in this album.[/yellow]")
            return
        
        table = Table(title=f"💿 Album {album_id} Tracks")
        table.add_column("Track", justify="right", style="dim")
        table.add_column("ID", style="dim")
        table.add_column("Title")
        table.add_column("Duration")
        
        for track in tracks:
            table.add_row(
                str(track.track_number or "?"),
                str(track.id),
                track.title or "unknown",
                track.duration_str
            )
        console.print(table)
    
    asyncio.run(_album())

@app.command()
def playlist(playlist_id: str = typer.Argument(..., help="Playlist ID to show tracks")):
    """Show tracks in a playlist."""
    async def _playlist():
        await ensure_authenticated()
        client = get_api_client()
        
        with console.status("loading playlist tracks..."):
            tracks = await client.get_playlist_tracks(playlist_id)
        
        if not tracks:
            console.print("[yellow]no tracks found in this playlist.[/yellow]")
            return
        
        table = Table(title=f"📋 Playlist {playlist_id} Tracks")
        table.add_column("#", justify="right", style="dim")
        table.add_column("ID", style="dim")
        table.add_column("Title")
        table.add_column("Artist")
        table.add_column("Duration")
        
        for i, track in enumerate(tracks, 1):
            table.add_row(
                str(i),
                str(track.id),
                track.title or "unknown",
                track.artist.name if track.artist else "unknown",
                track.duration_str
            )
        console.print(table)
    
    asyncio.run(_playlist())

@app.command()
def artist(
    artist_id: int = typer.Argument(..., help="Artist ID"),
    show: str = typer.Option("tracks", "--show", "-s", help="Show: tracks, albums, bio")
):
    """Show artist information, top tracks, or albums."""
    async def _artist():
        await ensure_authenticated()
        client = get_api_client()
        
        if show == "tracks":
            with console.status("loading artist top tracks..."):
                tracks = await client.get_artist_top_tracks(artist_id)
            
            if not tracks:
                console.print("[yellow]no tracks found for this artist.[/yellow]")
                return

            table = Table(title=f"👤 Artist {artist_id} Top Tracks")
            table.add_column("ID", style="dim")
            table.add_column("Title")
            table.add_column("Album")
            table.add_column("Duration")
            
            for track in tracks:
                table.add_row(
                    str(track.id),
                    track.title or "unknown",
                    track.album.title if track.album else "unknown",
                    track.duration_str
                )
            console.print(table)
        
        elif show == "albums":
            with console.status("loading artist albums..."):
                albums = await client.get_artist_albums(artist_id)
            
            if not albums:
                console.print("[yellow]no albums found for this artist.[/yellow]")
                return

            table = Table(title=f"👤 Artist {artist_id} Albums")
            table.add_column("ID", style="dim")
            table.add_column("Title")
            table.add_column("Year", style="dim")
            
            for album in albums:
                table.add_row(
                    str(album.id),
                    album.title or "unknown",
                    "?"  # year info not in current model
                )
            console.print(table)
        
        elif show == "bio":
            try:
                with console.status("loading artist bio..."):
                    bio = await client.get_artist_bio(artist_id)
                
                panel = Panel(
                    bio.text,
                    title=f"👤 Artist {artist_id} Bio",
                    subtitle=f"Source: {bio.source}"
                )
                console.print(panel)
            except Exception:
                console.print("[yellow]no bio available for this artist.[/yellow]")
    
    asyncio.run(_artist())

@app.command()
def status():
    """Show current playback status."""
    status = audio_player.status
    
    if status["state"] == "stopped":
        console.print("[dim]no track playing[/dim]")
        return
    
    track = status["track"]
    pos_min = int(status["position"] // 60)
    pos_sec = int(status["position"] % 60)
    dur_min = int(status["duration"] // 60)
    dur_sec = int(status["duration"] % 60)
    
    state_icon = "⏸" if status["paused"] else "▶"
    state_text = "paused" if status["paused"] else "playing"
    
    table = Table(title="🎵 Now Playing")
    table.add_column("Property")
    table.add_column("Value")
    
    table.add_row("Track", track.display_title if track else "unknown")
    table.add_row("Status", f"{state_icon} {state_text}")
    table.add_row("Position", f"{pos_min:02d}:{pos_sec:02d} / {dur_min:02d}:{dur_sec:02d}")
    
    console.print(table)

@app.command()
def interactive():
    """Start interactive mode for browsing and playing music."""
    async def _interactive():
        await ensure_authenticated()
        client = get_api_client()
        
        console.print("[bold]tidalite interactive mode[/bold]")
        console.print("commands: search, play <id>, download <id>, favorites, quit")
        
        while True:
            try:
                command = Prompt.ask("\ntidalite", default="search")
                
                if command.lower() in ("quit", "exit", "q"):
                    break
                elif command.lower() == "favorites":
                    await _show_favorites(client)
                elif command.startswith("search "):
                    query = command[7:].strip()
                    if query:
                        await _interactive_search(client, query)
                elif command.startswith("play "):
                    try:
                        track_id = int(command[5:].strip())
                        await _interactive_play(client, track_id)
                    except ValueError:
                        console.print("[red]invalid track id[/red]")
                elif command.startswith("download "):
                    try:
                        track_id = int(command[9:].strip())
                        await _interactive_download(client, track_id)
                    except ValueError:
                        console.print("[red]invalid track id[/red]")
                else:
                    console.print("[yellow]unknown command. try: search <query>, play <id>, download <id>, favorites, quit[/yellow]")
                    
            except KeyboardInterrupt:
                break
            except EOFError:
                break
        
        console.print("\n[dim]goodbye![/dim]")
    
    async def _show_favorites(client):
        tracks = await client.get_user_favorite_tracks()
        if tracks:
            console.print("\n[bold]❤️ favorite tracks:[/bold]")
            for i, track in enumerate(tracks[:10], 1):
                console.print(f"{i}. [dim]{track.id}[/dim] {track.display_title}")
    
    async def _interactive_search(client, query):
        results = await client.search(query)
        
        if results.tracks:
            console.print(f"\n[bold]🎵 tracks for '{query}':[/bold]")
            for i, track in enumerate(results.tracks[:10], 1):
                console.print(f"{i}. [dim]{track.id}[/dim] {track.display_title}")
        
        if results.albums:
            console.print(f"\n[bold]💿 albums for '{query}':[/bold]")
            for i, album in enumerate(results.albums[:5], 1):
                artist_name = album.artist.name if hasattr(album, 'artist') and album.artist else "various"
                console.print(f"{i}. [dim]{album.id}[/dim] {artist_name} - {album.title}")
    
    async def _interactive_play(client, track_id):
        try:
            stream_details = await client.get_stream_details(track_id)
            if stream_details.url:
                # create basic track for playback
                from .models import Track
                track = Track(id=track_id, title=f"Track {track_id}", duration=0)
                console.print(f"[green]playing track {track_id}[/green]")
                audio_player.play(track, stream_details.url)
            else:
                console.print("[red]no stream available[/red]")
        except Exception as e:
            console.print(f"[red]error: {str(e)}[/red]")
    
    async def _interactive_download(client, track_id):
        try:
            stream_details = await client.get_stream_details(track_id)
            if stream_details.url:
                console.print(f"[green]downloading track {track_id}...[/green]")
                # simple download without progress for interactive mode
                async with httpx.AsyncClient() as http_client:
                    response = await http_client.get(stream_details.url)
                    response.raise_for_status()
                    
                    filename = f"track_{track_id}.flac"
                    with open(filename, "wb") as f:
                        f.write(response.content)
                    
                    console.print(f"[green]saved as {filename}[/green]")
            else:
                console.print("[red]no stream available[/red]")
        except Exception as e:
            console.print(f"[red]error: {str(e)}[/red]")
    
    asyncio.run(_interactive())

if __name__ == "__main__":
    app()
