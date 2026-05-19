---
status: awaiting_human_verify
trigger: "Large file uploads through relay fail with FrameTooLargeError"
created: 2026-03-16T00:00:00Z
updated: 2026-03-30T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED - relay proxy stuffs entire HTTP request body into OPEN frame metadata, exceeding 64KB frame limit
test: Fix applied and all 278 tests pass including 3 new agent-side body reconstruction tests
expecting: Large file uploads through relay now succeed
next_action: Await human verification of the fix in real workflow

## Symptoms

expected: Large file uploads (>64KB) through the relay proxy should succeed
actual: 500 Internal Server Error with FrameTooLargeError when uploading files >64KB
errors: "Payload size 10040506 exceeds maximum 65536 bytes" at tunnel/frames.py:28 via relay/app/routers/mount_proxy.py:112
reproduction: Upload any file larger than ~64KB through a remote mount
started: Always broken for large uploads; small uploads (<64KB) work fine

## Eliminated

(none needed - root cause identified on first hypothesis)

## Evidence

- timestamp: 2026-03-16T00:01:00Z
  checked: relay/app/routers/mount_proxy.py lines 93-112
  found: |
    Line 93: `body = await request.body()` reads the ENTIRE request body into memory.
    Lines 102-108: The body is embedded directly into the metadata dict as `"body": body.decode("latin-1")`.
    Line 112: `await conn.send_open(request_id, metadata)` sends metadata (including full body) as a single OPEN frame.
  implication: Any upload body > ~64KB will blow the MAX_PAYLOAD_BYTES limit in serialize_frame.

- timestamp: 2026-03-16T00:02:00Z
  checked: tunnel/frames.py serialize_frame and tunnel/constants.py
  found: |
    MAX_PAYLOAD_BYTES = 65536 (64KB). serialize_frame raises FrameTooLargeError when payload exceeds this.
    The OPEN frame payload is JSON-encoded metadata, so the limit applies to the entire JSON string
    including the body field.
  implication: The protocol enforces a hard 64KB per-frame limit, which is correct for flow control. The bug is in the caller, not the protocol.

- timestamp: 2026-03-16T00:03:00Z
  checked: tunnel/connection.py send_open and send_data
  found: |
    send_open (line 168): serializes metadata dict as JSON, sends as single OPEN frame.
    send_data (line 158): sends arbitrary bytes as DATA frames.
    The protocol already has a DATA frame type (FrameType.DATA = 0x02) designed for streaming body content in chunks.
  implication: The infrastructure for chunked body streaming already exists. It is simply not used for request bodies.

- timestamp: 2026-03-16T00:04:00Z
  checked: agent/proxy.py handle_open_frame (the receiving side)
  found: |
    Lines 49-53: Agent extracts body from metadata dict: `body_str = metadata.get("body", "")`.
    Line 61: Decodes it back from latin-1: `content = body_str.encode("latin-1")`.
    Lines 77-83: Response body IS correctly streamed as chunked DATA frames (chunk_size=MAX_PAYLOAD_BYTES).
    The response path is properly chunked; the request path is not.
  implication: The response direction (agent->relay) already implements correct chunking. The request direction (relay->agent) needs the same treatment.

## Resolution

root_cause: |
  In `relay/app/routers/mount_proxy.py`, the `proxy_request` function reads the entire HTTP
  request body (line 93: `body = await request.body()`) and embeds it into the OPEN frame
  metadata dict (line 107: `"body": body.decode("latin-1")`). This metadata dict is then
  JSON-serialized and sent as a single OPEN frame payload via `conn.send_open()`.

  The tunnel protocol enforces a 64KB (MAX_PAYLOAD_BYTES = 65536) limit per frame in
  `tunnel/frames.py:serialize_frame`. When the upload body exceeds ~64KB, the JSON-encoded
  metadata payload exceeds this limit, raising FrameTooLargeError.

  The irony is that the response direction already handles this correctly: `agent/proxy.py`
  streams response bodies as chunked DATA frames (line 77: `aiter_bytes(chunk_size=MAX_PAYLOAD_BYTES)`).
  The request direction simply never implemented the same pattern.

fix: |
  Applied in two places:

  1. **relay/app/routers/mount_proxy.py** (sender side):
     - Removed "body" from OPEN frame metadata; body no longer in OPEN frame.
     - After send_open(), streams request body as chunked DATA frames using
       request.stream() (no full-body buffering) with MAX_PAYLOAD_BYTES chunks.
     - Sends zero-length DATA frame as end-of-body sentinel.
     - OPEN metadata now includes content_length for informational purposes.

  2. **agent/proxy.py** (receiver side):
     - Removed body extraction from metadata.
     - Reads DATA frames from stream queue until zero-length sentinel.
     - Calls conn.remove_stream() after body is fully received to clean up
       the inbound stream before sending the response.
     - Passes reconstructed body as content to httpx request.

  3. **agent/connection.py** (dispatch):
     - open_stream() called BEFORE spawning handle_open_frame task so DATA
       frames arriving in subsequent receive loop iterations land in the queue.

verification: |
  All 278 tests pass (0 failures):
  - 3 new agent-side tests verify POST body reconstruction from DATA frames:
    - test_handle_open_frame_post_small_body_reconstructed (single chunk)
    - test_handle_open_frame_post_large_body_multi_chunk (>64KB, multiple chunks)
    - test_handle_open_frame_removes_stream_after_body_read (cleanup)
  - 3 existing relay-side tests verify DATA frame streaming:
    - test_proxy_post_body (body as DATA frames, not in OPEN metadata)
    - test_proxy_large_upload_streams_body (>64KB, multiple frames)
    - test_proxy_get_no_body_sends_sentinel (GET sends only sentinel)
files_changed:
  - relay/app/routers/mount_proxy.py
  - agent/proxy.py
  - agent/connection.py
  - tests/agent/test_proxy.py
  - tests/relay/test_mount_proxy.py
  - tests/relay/conftest.py
