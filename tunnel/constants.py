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
