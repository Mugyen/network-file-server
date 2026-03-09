#!/bin/bash

# WiFi File Server Startup Script

echo "🚀 WiFi File Server"
echo "=================="

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed or not in PATH"
    exit 1
fi

# Check if folder argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <folder_path> [port]"
    echo "Example: $0 ~/Documents"
    echo "Example: $0 . 8080"
    exit 1
fi

FOLDER_PATH="$1"
PORT="${2:-6969}"

# Check if folder exists
if [ ! -d "$FOLDER_PATH" ]; then
    echo "❌ Error: Folder '$FOLDER_PATH' does not exist"
    exit 1
fi

# Check if folder is readable
if [ ! -r "$FOLDER_PATH" ]; then
    echo "❌ Error: No read permission for folder '$FOLDER_PATH'"
    exit 1
fi

echo "📁 Sharing folder: $FOLDER_PATH"
echo "🌐 Port: $PORT"
echo ""

# Install dependencies if needed
if [ ! -f "requirements.txt" ]; then
    echo "❌ requirements.txt not found"
    exit 1
fi

echo "📦 Checking dependencies..."
python3 -c "import flask" 2>/dev/null || {
    echo "📥 Installing dependencies..."
    pip3 install -r requirements.txt
}

echo "🚀 Starting server..."
echo "📱 Access from any device on your network!"
echo "🔗 Local URL: http://localhost:$PORT"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server
python3 wifi_file_server.py "$FOLDER_PATH" --port "$PORT"
