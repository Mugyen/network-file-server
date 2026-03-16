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

Scan the QR code printed in the terminal from any device on the same network.

## Relay (remote access)

Start the relay server to expose mounts outside your LAN:

```bash
uv run wifi-relay              # binds 0.0.0.0:8001
uv run wifi-relay --port 9001  # custom port
uv run wifi-relay --host 127.0.0.1  # localhost only
```

Mount a local folder through the relay from any machine:

```bash
uv run wifi-file-server /path/to/folder mount --relay http://relay-host:8001
```

## API

- `GET /api/files?path=` -- list directory contents
- `POST /api/files/upload?path=&conflict_resolution=` -- upload files (multipart)
- `GET /api/files/download?path=` -- download single file
- `POST /api/files/download-zip` -- download multiple files as ZIP (JSON body: `{"paths": [...]}`)
- `PATCH /api/files/rename` -- rename file/folder (JSON body: `{"path": "...", "new_name": "..."}`)
- `DELETE /api/files` -- delete files/folders (JSON body: `{"paths": [...]}`)
- `POST /api/folders` -- create folder (JSON body: `{"parent_path": "...", "name": "..."}`)
- `GET /api/server-info` -- server IP, port, URL, QR code (SVG), all LAN IPs

## Test

```bash
uv run pytest server/tests/ -v
```

## Client Development

```bash
cd client && npm install && npm run dev
```

Vite proxies `/api` requests to `localhost:8000`. Run the backend in a separate terminal.

## Features

- Browse files and folders with double-click navigation and breadcrumbs
- Upload via drag-and-drop or toolbar button with progress tracking
- Download individual files or batch-download selected files as ZIP
- Select files with checkboxes, select all, batch delete with confirmation
- Rename files inline, create new folders
- Responsive layout -- mobile-friendly

## Requirements

- Python 3.11+
- uv
- Node.js 20+ (for client)
