# Research Summary: WiFi File Server v1.1

**Domain:** LAN file sharing -- access control, sharing modes, device discovery, server UX
**Researched:** 2026-03-10
**Overall confidence:** HIGH (libraries verified via web search, codebase fully analyzed, patterns confirmed against official docs)

## Executive Summary

The v1.1 milestone adds access control (password protection, read-only mode), sharing modes (receive-only dropbox, expiring share links), network features (mDNS device discovery), and server-side UX (rich terminal UI, speed test) to the existing WiFi File Server. The existing v1.0 stack (React 19, FastAPI, WebSocket, Tailwind v4) is unchanged and validated.

The stack additions are minimal: 4 new Python packages (bcrypt, itsdangerous, zeroconf, rich), zero new frontend packages. Three of the seven features (read-only mode, receive mode, speed test) need no new dependencies at all -- they use existing FastAPI middleware patterns and stdlib capabilities. This is a deliberately conservative expansion that avoids dependency bloat.

The most architecturally significant change is introducing a middleware layer for access control. The `PasswordAuthMiddleware` and `AccessModeMiddleware` sit between CORS and routing, gating all requests. This is the one area where the wrong initial decision (headers vs cookies, per-route vs middleware) creates expensive retrofitting. Cookie-based auth is the only correct choice because browsers automatically send cookies with anchor tag navigations, media element source loads, and WebSocket upgrades -- all of which exist in the v1.0 codebase and would bypass header-based auth.

The biggest risks are: (1) incomplete write-path blocking in read-only mode (the codebase has 8 distinct write surfaces across 3 routers and WebSocket), (2) auth bypass via direct URL access to downloads/previews, and (3) Rich terminal UI fighting uvicorn for stdout. All three are well-understood with clear prevention strategies documented in PITFALLS.md.

## Key Findings

**Stack:** 4 new Python deps (bcrypt >=4.2.0, itsdangerous >=2.2.0, zeroconf >=0.146.0, rich >=13.9.0). Zero new frontend deps. Three features need no deps at all.

**Architecture:** Two new middleware classes (PasswordAuthMiddleware, AccessModeMiddleware). ServerConfig expands with password_hash, server_mode enum, tui_enabled. FastAPI lifespan context manager for zeroconf registration/cleanup. 10 new files (4 routers, 5 services, 1 middleware module), 6 modified files.

**Critical pitfall:** Cookie-based auth (not header-based) is mandatory. The existing frontend uses `<a href>` tags for downloads and `<img src>` for previews -- these bypass custom HTTP headers but carry cookies automatically.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Access Control** - Establishes middleware pattern, config expansion, and auth flow
   - Addresses: Password protection, read-only mode, receive mode
   - Avoids: Auth bypass (Pitfall 2), incomplete write-path blocking (Pitfall 1)
   - Dependencies: None (builds on existing config/middleware patterns)
   - Rationale: All three features share the same middleware pattern. Build the framework once, plug in each mode.

2. **Sharing & Discovery** - Standalone features using patterns from Phase 1
   - Addresses: Expiring share links, device discovery (mDNS)
   - Avoids: Token leaks in logs (Pitfall 4), mDNS silent failure (Pitfall 6)
   - Dependencies: itsdangerous pattern already established by auth in Phase 1
   - Rationale: Share links reuse the itsdangerous serializer pattern from session tokens. Discovery is fully independent.

3. **Server UX** - Server-side polish, no API changes
   - Addresses: Rich terminal UI, network speed test
   - Avoids: Terminal UI + uvicorn stdout conflict (Pitfall 5), speed test bandwidth saturation (Pitfall 7)
   - Dependencies: Benefits from device tracking data from Phase 2
   - Rationale: Terminal UI is purely cosmetic (no API changes). Speed test is standalone. Both can be deferred without affecting users.

**Phase ordering rationale:**
- Phase 1 must be first because the middleware pattern is reused by share links (public path exemptions) and the config expansion (ServerMode enum) drives frontend conditional rendering.
- Phase 2 can be built independently of Phase 1's features, but the patterns (itsdangerous, lifespan context) are established there.
- Phase 3 is last because it has no downstream dependents and only improves the server operator's experience.

**Research flags for phases:**
- Phase 1: No deeper research needed. Cookie auth, middleware, and bcrypt patterns are well-documented. The key decision (cookies vs headers) is already made.
- Phase 2: mDNS may need deeper investigation on specific platforms (macOS firewall, Windows Defender). Document graceful fallback behavior.
- Phase 3: Rich + uvicorn coexistence needs hands-on prototyping. The daemon thread approach should be validated before committing to the full dashboard design.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All 4 new packages verified via web search -- latest versions confirmed, Python 3.11+ compatibility confirmed. |
| Features | HIGH | Feature scope is clear and well-bounded. Each feature maps to specific endpoints and components. |
| Architecture | HIGH | Middleware pattern, lifespan context, and token architecture are all from official FastAPI/itsdangerous documentation. |
| Pitfalls | HIGH | Pitfalls identified from direct codebase analysis (all 40+ source files) and verified against security patterns (OWASP, auth best practices). |

## Gaps to Address

- **Rich + uvicorn coexistence:** The daemon thread approach for the terminal UI needs hands-on validation. Rich's Live display and uvicorn's logging may interact differently than expected on different terminal emulators.
- **mDNS on restricted networks:** zeroconf will silently fail on networks with client isolation (hotels, corporate WiFi). The graceful fallback UX needs design attention.
- **CORS + credentials interaction:** When password protection is enabled, the development setup (Vite on :5173, FastAPI on :8000) requires `allow_credentials=True` with explicit origin, not wildcard. This dev-mode CORS config needs careful handling.
- **bcrypt v4.x vs v5.x:** bcrypt 5.0.0 raises ValueError for passwords >72 bytes. Staying on 4.x is recommended but should be validated if uv resolves to 5.x by default.
