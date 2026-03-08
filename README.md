# WiFi File Server

Share files over your local WiFi network. Any device on the same network can browse and download files via a web browser.

## Setup

```bash
uv sync
```

## Run

```bash
uv run wifi-file-server /path/to/folder
uv run wifi-file-server /path/to/folder --port 9000
uv run wifi-file-server /path/to/folder --host 127.0.0.1 --port 9000
```

Open the printed URL on any device on the same network.

## API

- `GET /api/files` -- list root directory
- `GET /api/files?path=subdir` -- list subdirectory

## Test

```bash
uv run pytest server/tests/ -v
```

## Requirements

- Python 3.11+
- uv
