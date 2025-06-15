import subprocess
import sys
import os
from pathlib import Path
import http.server
import socketserver 
import webbrowser

def run_backend():
    print("Starting backend server...")
    subprocess.Popen([
        sys.executable, "-m", "uvicorn",
        "email_summarizer.api:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ])

def run_frontend():
    print("Starting frontend server...")
    os.chdir("frontend") 
    
    # Create a simple HTTP server
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("", 3000), handler)
    
    print("Frontend server is running at http://localhost:3000")
    webbrowser.open("http://localhost:3000")
    httpd.serve_forever()

def main():
    frontend_dir = Path("frontend")
    if not frontend_dir.exists():
        frontend_dir.mkdir()

    # Run both servers
    run_backend()
    run_frontend()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nShutting down servers...")
        sys.exit(0) 