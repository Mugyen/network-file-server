#!/usr/bin/env python3
"""
WiFi File Server - A simple file sharing server over local network
Allows users to browse, download, and upload files from a specified folder
"""

import os
import sys
import argparse
import mimetypes
from pathlib import Path
from flask import Flask, render_template, request, send_file, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
import socket

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

# Global variable to store the shared folder path
SHARED_FOLDER = None

def get_local_ip():
    """Get the local IP address of the machine"""
    try:
        # Connect to a remote server to get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def get_file_size(filepath):
    """Get human readable file size"""
    size = os.path.getsize(filepath)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"

def get_file_icon(filename):
    """Get appropriate icon for file type"""
    ext = Path(filename).suffix.lower()
    icon_map = {
        '.txt': '📄', '.pdf': '📕', '.doc': '📘', '.docx': '📘',
        '.xls': '📊', '.xlsx': '📊', '.ppt': '📽️', '.pptx': '📽️',
        '.jpg': '🖼️', '.jpeg': '🖼️', '.png': '🖼️', '.gif': '🖼️',
        '.mp4': '🎬', '.avi': '🎬', '.mov': '🎬', '.mp3': '🎵',
        '.wav': '🎵', '.zip': '📦', '.rar': '📦', '.tar': '📦',
        '.py': '🐍', '.js': '📜', '.html': '🌐', '.css': '🎨',
        '.json': '📋', '.xml': '📋', '.csv': '📊'
    }
    return icon_map.get(ext, '📄')

@app.route('/')
def index():
    """Main page showing file list"""
    if not SHARED_FOLDER or not os.path.exists(SHARED_FOLDER):
        flash("Shared folder not found or not accessible", "error")
        return render_template('index.html', files=[], folder_path="")
    
    files = []
    try:
        for item in os.listdir(SHARED_FOLDER):
            item_path = os.path.join(SHARED_FOLDER, item)
            if os.path.isfile(item_path):
                files.append({
                    'name': item,
                    'size': get_file_size(item_path),
                    'icon': get_file_icon(item),
                    'path': item
                })
    except PermissionError:
        flash("Permission denied to access the shared folder", "error")
        return render_template('index.html', files=[], folder_path=SHARED_FOLDER)
    
    # Sort files by name
    files.sort(key=lambda x: x['name'].lower())
    
    return render_template('index.html', files=files, folder_path=SHARED_FOLDER)

@app.route('/download/<filename>')
def download_file(filename):
    """Download a file"""
    if not SHARED_FOLDER:
        flash("Shared folder not configured", "error")
        return redirect(url_for('index'))
    
    file_path = os.path.join(SHARED_FOLDER, secure_filename(filename))
    
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        flash("File not found", "error")
        return redirect(url_for('index'))
    
    try:
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        flash(f"Error downloading file: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload"""
    if not SHARED_FOLDER:
        flash("Shared folder not configured", "error")
        return redirect(url_for('index'))
    
    if 'file' not in request.files:
        flash("No file selected", "error")
        return redirect(url_for('index'))
    
    file = request.files['file']
    if file.filename == '':
        flash("No file selected", "error")
        return redirect(url_for('index'))
    
    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(SHARED_FOLDER, filename)
        
        # Check if file already exists
        if os.path.exists(file_path):
            flash(f"File '{filename}' already exists", "warning")
            return redirect(url_for('index'))
        
        try:
            file.save(file_path)
            flash(f"File '{filename}' uploaded successfully", "success")
        except Exception as e:
            flash(f"Error uploading file: {str(e)}", "error")
    
    return redirect(url_for('index'))

@app.route('/api/files')
def api_files():
    """API endpoint to get file list as JSON"""
    if not SHARED_FOLDER or not os.path.exists(SHARED_FOLDER):
        return jsonify({'error': 'Shared folder not found'}), 404
    
    files = []
    try:
        for item in os.listdir(SHARED_FOLDER):
            item_path = os.path.join(SHARED_FOLDER, item)
            if os.path.isfile(item_path):
                files.append({
                    'name': item,
                    'size': get_file_size(item_path),
                    'icon': get_file_icon(item),
                    'path': item
                })
    except PermissionError:
        return jsonify({'error': 'Permission denied'}), 403
    
    files.sort(key=lambda x: x['name'].lower())
    return jsonify({'files': files})

def main():
    """Main function to start the server"""
    global SHARED_FOLDER
    
    parser = argparse.ArgumentParser(description='WiFi File Server - Share files over local network')
    parser.add_argument('folder', help='Path to the folder to share')
    parser.add_argument('--port', '-p', type=int, default=5000, help='Port to run the server on (default: 5000)')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    
    args = parser.parse_args()
    
    # Validate folder path
    folder_path = os.path.abspath(args.folder)
    if not os.path.exists(folder_path):
        print(f"Error: Folder '{folder_path}' does not exist")
        sys.exit(1)
    
    if not os.path.isdir(folder_path):
        print(f"Error: '{folder_path}' is not a directory")
        sys.exit(1)
    
    if not os.access(folder_path, os.R_OK):
        print(f"Error: No read permission for folder '{folder_path}'")
        sys.exit(1)
    
    SHARED_FOLDER = folder_path
    
    # Get local IP
    local_ip = get_local_ip()
    
    print(f"\n🚀 WiFi File Server Starting...")
    print(f"📁 Sharing folder: {folder_path}")
    print(f"🌐 Server URL: http://{local_ip}:{args.port}")
    print(f"🔗 Local URL: http://localhost:{args.port}")
    print(f"📱 Access from any device on the same network!")
    print(f"\nPress Ctrl+C to stop the server\n")
    
    try:
        app.run(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
