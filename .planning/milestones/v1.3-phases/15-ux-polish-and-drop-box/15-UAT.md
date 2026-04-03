---
status: complete
phase: 15-ux-polish-and-drop-box
source: 15-01-PLAN.md, 15-02-PLAN.md, 15-03-PLAN.md, 15-04-PLAN.md
started: 2026-04-03T00:00:00Z
updated: 2026-04-03T01:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Landing Page Hero Section
expected: Visit relay root (/). Page shows hero heading, tagline, how-it-works strip with 3 steps, mount code form, GitHub link, and Drop Box link.
result: pass

### 2. Mount Code Form Redirect
expected: Enter a mount code in the form and submit. Browser redirects to /m/{code}/.
result: pass

### 3. OG Meta Tags Present
expected: View page source of /. HTML head contains og:title, og:description, og:image with absolute URL.
result: pass

### 4. Static OG Image Served
expected: Visit /static/og-image.png. A PNG image loads.
result: pass

### 5. Host Offline Overlay
expected: Stop the agent. Amber "Host Offline" banner appears, file list greys out. Restart agent — banner disappears.
result: pass

### 6. Mount Expired Overlay
expected: Mount with --ttl 1m. After TTL elapses, red "Mount Expired" banner with "Back to home" link. Terminal state.
result: pass

### 7. Drop Box File Browser
expected: Visit /m/dropbox/. Full file browser SPA loads without any agent running.
result: pass

### 8. Drop Box File Upload
expected: Upload a file in the drop box. File appears in listing immediately.
result: pass

### 9. Reserved Code Protection
expected: Agent trying to register reserved "dropbox" code is rejected.
result: skipped
reason: CLI doesn't expose --code flag; covered by unit test test_reserved_code_rejected_via_ws

### 10. TTL Picker in Upload UI
expected: Dropdown next to Upload button with 1h/6h/1d/7d/Never options, default 1 day.
result: pass

### 11. File Expiry Badge
expected: File uploaded with 1h TTL shows countdown badge (e.g. "59m left") in orange. Files with Never show no badge.
result: pass

### 12. Expired File Auto-Deletion
expected: After TTL elapses and sweep runs, file is deleted and toast notification appears.
result: skipped
reason: Requires waiting for 60s sweep interval; covered by automated tests test_sweep_deletes_expired_file and test_sweep_broadcasts_toast

## Summary

total: 12
passed: 10
issues: 0
pending: 0
skipped: 2

## Gaps

[none]
