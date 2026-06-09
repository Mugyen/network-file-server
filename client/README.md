# Network File Server Client

This package contains the React SPA for the Network File Server.

## Development

```bash
npm install
npm run dev
```

The Vite dev server expects the Python backend to be running separately and proxies `/api` requests to the local server.

## Build

```bash
npm run build
```

## Test

```bash
npm run typecheck   # tsc
npm run test:unit   # vitest (jsdom)
npm run lint        # eslint
npm run e2e         # Playwright (needs backend running)
```

## Notes

- The app supports both LAN mode and relay-mounted remote access.
- Route handling is mode-aware through `src/utils/remoteMount.ts`.
- Shared client API paths live in `src/api/endpoints.ts`.
