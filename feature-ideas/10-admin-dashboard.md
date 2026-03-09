# Admin Dashboard & Access Control

## Summary
User roles, per-folder permissions, transfer logs, bandwidth monitoring, and a management UI. The enterprise unlock for small offices and teams.

## Why This Matters
Small businesses, schools, and coworking spaces need shared file servers with access control. Without it, anyone on the network can do anything. This is the feature that justifies a recurring subscription for teams.

## Implementation
- Admin account with setup wizard on first run
- User management: create users with username/password
- Role-based access: admin, editor (upload+download), viewer (download only)
- Per-folder permissions (read, write, admin)
- Transfer audit log: who uploaded/downloaded what, when, from which IP
- Real-time bandwidth monitoring dashboard
- Storage usage visualization (per user, per folder)
- Session management: see connected devices, force disconnect
- Configurable upload size limits per user/role
- Activity notifications (email or webhook)

## Scope
Large — 15-20 hours. Auth system and permission checks throughout the app.

## Monetization
Team tier ($4.99/user/mo). This is the B2B revenue driver.
