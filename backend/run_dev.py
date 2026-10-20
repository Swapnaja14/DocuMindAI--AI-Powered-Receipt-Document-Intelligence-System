"""
DocuMind AI - Resilient Development Server Launcher
Guarantees clean socket binding, port conflict resolution, and environment isolation.
"""

import os
import sys
import socket
import subprocess
import time
import uvicorn

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.settimeout(0.5)
            s.bind((host, port))
            return False
        except OSError:
            return True

def kill_process_on_port(port: int):
    """If port is occupied by a lingering/zombie process, kill it gracefully on Windows/Linux."""
    if sys.platform == "win32":
        try:
            # Query owning PID using netstat
            cmd = f'netstat -ano | findstr :{port}'
            output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
            for line in output.strip().splitlines():
                if "LISTENING" in line:
                    parts = line.strip().split()
                    pid = int(parts[-1])
                    if pid != os.getpid():
                        print(f"[Launcher] Port {port} is occupied by PID {pid}. Terminating orphan process...")
                        subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        time.sleep(1)
        except Exception:
            pass

def main():
    HOST = "127.0.0.1"
    PORT = 8000

    print("==================================================")
    print("  DocuMind AI Development Server Launcher")
    print("==================================================")
    print(f"Python interpreter: {sys.executable}")
    print(f"Target address:    http://{HOST}:{PORT}")

    if is_port_in_use(PORT, HOST):
        print(f"[Launcher] Port {PORT} is currently in use. Cleaning up...")
        kill_process_on_port(PORT)
        time.sleep(1)

    print("[Launcher] Starting Uvicorn with reload support...")
    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level="info",
    )

if __name__ == "__main__":
    main()
