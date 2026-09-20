import os
import sys
import time
import socket
import webbrowser
import threading
import psutil
import uvicorn
from api.main import app

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0

def kill_port_occupants(port):
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            for conn in proc.connections(kind="inet"):
                if conn.laddr.port == port:
                    proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

def wait_and_open_browser(port):
    url = f"http://127.0.0.1:{port}/"
    for _ in range(30):
        if is_port_in_use(port):
            time.sleep(0.5)
            webbrowser.open(url)
            return
        time.sleep(0.5)

if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        # O app procura o banco de dados em "../data".
        # Para ficar "data" lado a lado com o .exe, rodamos o app em uma subpasta virtual.
        dummy_dir = os.path.join(exe_dir, "app_core")
        os.makedirs(dummy_dir, exist_ok=True)
        os.chdir(dummy_dir)
    
    port = 8000
    if is_port_in_use(port):
        kill_port_occupants(port)
        time.sleep(1)

    threading.Thread(target=wait_and_open_browser, args=(port,), daemon=True).start()

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

