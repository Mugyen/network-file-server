# User Accounts & Multi-Tenancy

## Summary

Add persistent user accounts to the server, enabling multi-tenant usage. Each user gets isolated storage, quotas, and the ability to manage their own mounts. Builds on top of the remote mounts infrastructure from v1.2.

## Key Features

- User registration and login (email + password)
- Per-user isolated file storage on the server
- Storage quotas per user
- User-owned mounts (persist mount configs across sessions)
- Device allowlists per mount (owner approves/denies access)
- Role-based permissions per mount (read/write/receive per device)
- Admin dashboard for user management
- API keys for programmatic access

## Prerequisites

- Remote mounts (v1.2) must be complete
- HTTPS/TLS for secure credential handling on public internet

## Complexity

High — requires database for user records, session management rework, storage management, and permission system.

## Status

**Largely delivered in v1.3.** Implemented: relay-hosted user accounts +
nested groups, simple username/password signup/login, per-mount
open/restricted access modes with user/group allowlists and read/write/
receive roles, agent-as-owner handshake, relay-side enforcement with
trusted identity propagation to mounts, per-user relay storage with
quotas, owner/admin access-request approval, and an admin dashboard.

**NOT delivered (still open):**
- API keys for programmatic access (explicitly deferred — no public API yet)
- SSO (out of scope)
- Email verification / password reset

This idea remains open until API keys are implemented.
