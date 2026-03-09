# File Request System

## Summary
Request specific files from other connected devices. "I need the quarterly report" sends a notification to all connected devices — anyone can fulfill the request by uploading. Like asking a room "does anyone have this file?"

## Why This Matters
Current file sharing is one-directional: you share what you have. File requests flip this — you ask for what you need. In meetings, classrooms, and collaborative settings, this is natural: "Can someone share the agenda?" becomes a one-click workflow.

## Implementation
- "Request a File" button on main UI
- Request form: description, optional filename pattern, urgency level
- Request appears as notification on all connected devices
- Anyone can fulfill by uploading (with the request linked)
- Request status: pending, fulfilled, expired
- Request dashboard: see all open and completed requests
- Fulfillment notification: requester gets notified when file is uploaded
- Auto-expire requests after configurable timeout
- Request templates for recurring needs ("weekly report", "meeting notes")
- Anonymous requests for drop box scenarios

## Scope
Medium — 5-7 hours. WebSocket notifications + request state management.

## Monetization
Pro tier. Collaboration feature with clear team value.
