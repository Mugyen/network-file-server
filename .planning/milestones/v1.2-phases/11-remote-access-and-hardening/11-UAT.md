---
status: resolved
phase: 11-remote-access-and-hardening
source: [11-01-SUMMARY.md, 11-02-SUMMARY.md, 11-03-SUMMARY.md]
started: 2026-03-11T16:00:00Z
updated: 2026-03-16T00:00:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server. Start the relay. Start the agent. Agent connects, displays mount URL with QR code and mount code. Visit the mount URL in browser — file browser loads.
result: pass

### 2. Mount with Password Protection
expected: Start agent with `network-file-server mount ./test-files --server http://localhost:8001 --password secret`. Visit mount URL in browser. Login page appears (same as LAN password mode). Enter wrong password — rejected. Enter correct password — file browser loads. Refresh page — session persists (cookie works).
result: pass
note: Re-verified after heartbeat/disconnect fixes (985e88c, 0c5ccd3). Login works, session cookie persists after reload.

### 3. Password Cookie Isolation
expected: Start two agents on different directories with different passwords (two terminal tabs). Visit first mount URL — login with first password, access granted. Visit second mount URL in same browser — you should see a separate login page (not auto-authenticated from first mount's session).
result: pass
note: Cookie isolation works. Observed separate issues — WS /m/{code}/ws connects then immediately disconnects (causes "Reconnecting..." UI), and no logout button or TTL display in UI.

### 4. TTL Auto-Expiry
expected: Start agent with `network-file-server mount ./test-files --server http://localhost:8001 --ttl 1m`. Terminal shows countdown ("Expires in 59s" or similar, updating periodically). After 1 minute, agent prints unmounting message and exits cleanly (no reconnect attempts). Visiting the mount URL after expiry shows relay's error/expired page.
result: pass
note: Required fixes — TTL countdown print timing, WebSocketClientAdapter missing close(), ConnectionClosed not caught, hardcoded /api/ paths, and SPA HTML error redirect.

### 5. SPA File Browsing Through Relay
expected: With a mount active (no password), visit `/m/{code}/` in browser. File browser loads showing test files. Navigate into subdirectories — breadcrumbs and URL update correctly. Download a file — downloads successfully. Upload a file — appears in listing. Preview an image or PDF — preview modal works.
result: issue
reported: "Uploading large files is failing, and worse without visible reason for the user to understand. 500 Internal Server Error. FrameTooLargeError: Payload size 10040506 exceeds maximum 65536 bytes — the relay proxy tries to send the entire upload request (including file body) in a single OPEN frame."
severity: blocker

### 6. Remote Badge Display
expected: When accessing files through the relay mount URL, a green "Remote" pill badge is visible in the header next to the app title, matching the style of existing mode badges (like "Read Only" or "Protected"). In LAN mode (direct localhost access), the Remote badge does NOT appear.
result: pass

### 7. Real-Time Clipboard Sync Through Relay
expected: Open mount URL in two browser tabs (or two devices). In one tab, open the clipboard/scratchpad panel and type or paste text. The other tab's scratchpad updates in real-time with the same content.
result: issue
reported: "Sync works between tabs, but there's no copy-to-clipboard button — needed for mobile where you can't easily select text. Also, relay is only accessible via localhost, can't connect from another device."
severity: minor

### 8. Real-Time Transfer Notifications Through Relay
expected: Open mount URL in browser. In a second tab or via CLI, upload a file. The first browser tab shows a toast notification about the new upload in real-time (without refreshing).
result: pass

## Summary

total: 8
passed: 6
issues: 2
pending: 0
skipped: 0

## Gaps

- truth: "Upload a file through relay — appears in listing"
  status: resolved
  reason: "User reported: Uploading large files fails with 500 Internal Server Error. FrameTooLargeError: Payload size 10040506 exceeds maximum 65536 bytes — relay proxy sends entire upload body in a single OPEN frame."
  severity: blocker
  test: 5
  root_cause: "mount_proxy.py:107 reads entire request body with await request.body() and embeds it in OPEN frame metadata as body key. OPEN frame is serialized as single frame, hitting MAX_PAYLOAD_BYTES=65536 limit. Response direction already streams via DATA frames (agent/proxy.py:77), but request direction never implemented streaming."
  artifacts:
    - path: "relay/app/routers/mount_proxy.py"
      issue: "Embeds full request body in OPEN frame metadata instead of streaming as DATA frames"
    - path: "agent/proxy.py"
      issue: "Extracts body from OPEN metadata instead of reading from DATA frame stream"
  missing:
    - "Remove body from OPEN frame metadata; stream request body as chunked DATA frames after send_open()"
    - "Agent side: read DATA frames to reconstruct request body before forwarding to ASGI app"
    - "Add end-of-body signaling (zero-length DATA frame or content-length in metadata)"
  debug_session: ".planning/debug/upload-frame-too-large.md"
- truth: "Clipboard scratchpad provides easy copy-to-clipboard action; relay is accessible from other devices on the network"
  status: resolved
  reason: "User reported: Sync works between tabs, but no copy-to-clipboard button — needed for mobile. Also relay only accessible via localhost, can't connect from another device."
  severity: minor
  test: 7
  root_cause: "Two gaps: (1) SnippetCard.tsx has no copy button — navigator.clipboard API never used in scratchpad feature. (2) Relay has no CLI entry point; started via bare uvicorn which defaults to 127.0.0.1. Main server already defaults to 0.0.0.0 but relay has no equivalent."
  artifacts:
    - path: "client/src/components/SnippetCard.tsx"
      issue: "No copy-to-clipboard button; only has collapse/expand and delete actions"
    - path: "relay startup"
      issue: "No CLI entry point; uvicorn defaults to 127.0.0.1 without --host 0.0.0.0"
  missing:
    - "Add Copy icon button to SnippetCard using navigator.clipboard.writeText()"
    - "Create relay CLI entry point or update docs to include --host 0.0.0.0"
  debug_session: ".planning/debug/clipboard-and-binding.md"
