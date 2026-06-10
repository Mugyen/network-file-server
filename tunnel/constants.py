"""Protocol constants for the tunnel binary frame format."""

import struct

# Wire format: big-endian, 1 byte type + 16 bytes UUID + 4 bytes uint32 payload length
HEADER_FORMAT: str = ">B16sI"
HEADER_SIZE: int = struct.calcsize(HEADER_FORMAT)  # Must equal 21

# Maximum payload bytes per frame (64 KB)
MAX_PAYLOAD_BYTES: int = 65536

# Maximum concurrent streams per agent connection
MAX_STREAMS: int = 100

# Per-stream inbound queue depth (frames)
QUEUE_DEPTH: int = 64

# Heartbeat ping interval in seconds
HEARTBEAT_INTERVAL_S: int = 15

# Number of missed heartbeat pings before connection is considered dead
HEARTBEAT_MISSED_LIMIT: int = 3

# Seconds before the first data byte is expected on a new stream
FIRST_BYTE_TIMEOUT_S: int = 30

# Protocol version exchanged in the agent_auth handshake. The relay rejects
# agents with a different version BEFORE registering a mount, so a frame
# format / frame type change bumps this and old agents fail loudly at
# connect time instead of dropping frames silently.
PROTOCOL_VERSION: int = 1

# Agent-side heartbeat interval (the relay pings every HEARTBEAT_INTERVAL_S;
# the agent pings less aggressively — it only needs to detect a half-dead
# relay socket, where the agent believes it is mounted but the relay is gone).
AGENT_HEARTBEAT_INTERVAL_S: int = 30
