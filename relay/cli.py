"""CLI entry point for the relay server."""
import argparse
import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="WiFi File Server relay")
    parser.add_argument("--host", type=str, help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, help="Port number (default: 8001)")
    args = parser.parse_args()

    # Explicit None checks — argparse returns None when flags are omitted
    host: str = args.host if args.host is not None else "0.0.0.0"
    port: int = args.port if args.port is not None else 8001

    uvicorn.run("relay.app.main:app", host=host, port=port)


if __name__ == "__main__":
    main()
