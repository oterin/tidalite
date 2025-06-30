# tidalite

terminal cli for tidal music streaming.

## install

```bash
pip install -e .  # in repo root, or use 'pip install tidalite' once published
```

on linux you may need additional packages for `sounddevice`/`soundfile` (e.g. portaudio, libsndfile).

## quickstart

```bash
# first time – authenticate your account
$ tidalite login

# search for tracks
$ tidalite search "radiohead" --type tracks --limit 10

# play a track by id
$ tidalite play 441808188

# download a track
$ tidalite download 441808188 -o ~/music

# see your favourites
$ tidalite favorites

# interactive prompt
$ tidalite interactive
```

keys: `ctrl+c` stops playback; `tidalite logout` removes stored credentials.

## commands

* `login` – device-flow authentication.
* `logout` – clear credentials.
* `search <query>` – search library (tracks, albums, artists, playlists).
* `play <track_id>` – stream track.
* `download <track_id>` – save lossless flac.
* `favorites` – list favourite items.
* `album <id>` / `playlist <id>` / `artist <id>` – browse.
* `status` – show current playback.
* `interactive` – minimal interactive shell.

## config

credentials are stored in `~/.config/tidalite/config.json`. delete or run `tidalite logout` to reset.

## license

mit. 