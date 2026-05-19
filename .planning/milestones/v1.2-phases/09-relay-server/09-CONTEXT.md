# Phase 9: Relay Server - Context

**Gathered:** 2026-03-11
**Status:** Ready for planning

<domain>
## Phase Boundary

A public-facing relay server accepts agent WebSocket connections, routes browser HTTP requests through the tunnel to the correct agent by mount code, and provides a landing page and error pages for mount lifecycle. Runs as a separate FastAPI application deployable independently from the LAN server. Agent CLI (Phase 10), access control/TTL (Phase 11), and SPA adaptation (Phase 11) are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Landing page
- Code entry only — simple text input for mount code + submit button, no in-browser QR scanner
- Server-rendered via Jinja2 templates (FastAPI + Jinja2)
- Informational style — brief explanation of Network File Server, how mount codes work, plus the code input
- On valid code submission: 302 redirect to `/m/{code}/`

### Error pages
- Shared `base.html` Jinja2 template — landing page and all error pages extend it for consistent styling
- "Not found" error page includes a code input field so users can try a different code without going back
- Distinct "offline" message — "This mount is currently offline. The owner may reconnect soon." — distinguishes from invalid code
- "Expired" error template created now (ready for Phase 11 TTL) — shows clear expired message
- Three distinct error states: not_found, offline, expired

### Request proxying
- Streaming passthrough — relay streams tunnel frames directly to browser via StreamingResponse async generator from stream queue
- Full bidirectional proxying — all HTTP methods (GET, POST, PUT, DELETE) forwarded through tunnel, including request bodies for uploads
- Minimal header rewriting — strip hop-by-hop headers (Connection, Transfer-Encoding), rewrite Host, preserve cookies for Phase 11 auth pass-through
- Active CANCEL on browser disconnect — relay sends CANCEL frame to agent immediately when browser drops connection
- 30-second first-byte timeout inherited from TunnelConnection (decided in Phase 8)

### Claude's Discretion
- Mount code format (length, characters, generation algorithm)
- Relay app internal structure (routers, services, middleware organization)
- Mount registry data structure and cleanup strategy
- Agent WebSocket endpoint design
- Jinja2 template content and CSS styling details

</decisions>

<specifics>
## Specific Ideas

- Landing page should feel informational — first-time users landing on the relay URL should understand what this is and how to use a mount code
- Error pages keep users in flow — "not found" page includes code re-entry rather than dead-ending
- Offline vs not-found distinction gives users useful signal about whether to retry

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TunnelConnection` in `tunnel/connection.py`: Stream multiplexing, heartbeat, backpressure — relay wraps this for agent WebSocket connections
- `tunnel/frames.py`: serialize_frame/deserialize_frame — relay uses these for proxying data
- `tunnel/enums.py`: FrameType enum with OPEN/DATA/CLOSE/CANCEL/ERROR/PING/PONG
- `tunnel/protocol.py`: WebSocketProtocol interface — FastAPI's WebSocket satisfies this via structural subtyping
- `create_app()` factory in `server/app/main.py`: Established pattern for FastAPI app creation — relay uses same pattern
- `server/app/services/qr_service.py`: QR code generation — may be reusable for mount landing pages

### Established Patterns
- FastAPI router organization in `server/app/routers/` — relay should follow same router pattern
- Service layer in `server/app/services/` — mount registry should be a service
- Enum patterns in `server/app/models/enums.py` — mount status enum should follow same style
- Exception handling with custom exception classes and `@app.exception_handler` decorators

### Integration Points
- `tunnel/` module imported directly by relay for TunnelConnection, frame serialization, and protocol types
- Relay is a separate FastAPI app — does NOT share routers or middleware with the LAN server
- Agent connects via WebSocket to relay; relay creates TunnelConnection wrapping that WebSocket
- Mount registration happens via JSON text control messages (Phase 8 convention)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 09-relay-server*
*Context gathered: 2026-03-11*
