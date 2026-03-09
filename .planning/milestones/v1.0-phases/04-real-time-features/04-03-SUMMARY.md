---
phase: 04-real-time-features
plan: "03"
subsystem: file-requests
tags: [file-requests, real-time, websocket, drag-drop, upload]
dependency_graph:
  requires: [connection_manager, persistence, file_service, useWebSocket]
  provides: [FileRequestService, file_requests_router, useFileRequests, FileRequestBanner, FileRequestForm]
  affects: [App.tsx, Toolbar.tsx, main.py, schemas.py]
tech_stack:
  added: []
  patterns: [XHR upload progress, drag-to-fulfill drop zone, WS broadcast sync]
key_files:
  created:
    - server/app/services/file_request_service.py
    - server/app/routers/file_requests.py
    - server/tests/test_file_request_service.py
    - client/src/types/fileRequests.ts
    - client/src/api/fileRequests.ts
    - client/src/hooks/useFileRequests.ts
    - client/src/components/FileRequestBanner.tsx
    - client/src/components/FileRequestForm.tsx
  modified:
    - server/app/models/schemas.py
    - server/app/main.py
    - client/src/components/Toolbar.tsx
    - client/src/App.tsx
    - docs/project-log.md
decisions:
  - "Device name used as device ID for file request ownership (stable in localStorage)"
  - "SPA catch-all route stripped in REST tests to avoid route shadowing"
  - "Trailing slash on file-requests endpoints for FastAPI compatibility"
metrics:
  duration: 6min
  completed: "2026-03-09"
---

# Phase 4 Plan 3: File Request System Summary

File request CRUD with JSON persistence, REST API, WS broadcast sync, and full client UI with form, banners, drag-to-fulfill, and progress tracking.

## What Was Built

### Backend (Task 1 - TDD)
- **FileRequestService**: async CRUD with create/fulfill/dismiss, JSON persistence via write_json_atomic, asyncio lock for concurrency
- **REST endpoints**: GET /api/file-requests (list), POST /api/file-requests (create, 201), POST /api/file-requests/{id}/fulfill (file upload), DELETE /api/file-requests/{id} (dismiss)
- **WS integration**: REQUEST_CREATED broadcast to others, REQUEST_FULFILLED broadcast to all + targeted toast to requester, REQUEST_DISMISSED broadcast to all
- **Validation**: empty description rejected, only PENDING requests fulfillable, only requester can dismiss
- **Schemas**: FileRequest and CreateFileRequestPayload in schemas.py

### Frontend (Task 2)
- **FileRequestForm**: inline form with auto-focus, Enter to submit, Escape to cancel
- **FileRequestBanner**: pending state (amber, upload button, drag-drop zone, progress bar) and fulfilled state (green, download link, dismiss X for owner only)
- **useFileRequests hook**: REST calls + WS handlers for real-time sync, progress tracking via Map
- **Toolbar**: "Request File" button with FileQuestion icon
- **App.tsx wiring**: form above banners above file list, loadFiles refresh on fulfillment

## Test Results

15 tests passing:
- 11 service unit tests (CRUD, validation, persistence, dismissal rules)
- 4 REST integration tests (list, create, fulfill with upload, dismiss)
- TypeScript: compiles cleanly with --noEmit

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] SPA catch-all route intercepts test REST calls**
- Found during: Task 1 test execution
- Issue: client/dist exists, so SPA catch-all grabs /api/file-requests before router
- Fix: Strip catch-all route from test app instance
- Files: server/tests/test_file_request_service.py

**2. [Rule 3 - Blocking] Service singleton leaks between REST tests**
- Found during: Task 1 REST test isolation
- Issue: Module-level get_file_request_service cached in router module
- Fix: Patch both service module and router module factory in test fixture
- Files: server/tests/test_file_request_service.py

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 051ae00 | Backend service, REST endpoints, 15 tests |
| 2 | e175b6d | Client UI: form, banners, hook, toolbar wiring |
