import os
import sys
import time
import socket
import webbrowser
import threading
import psutil
import uvicorn
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
        
        with open(os.path.join(exe_dir, "debug.txt"), "w") as f:
            f.write("Started launcher.py\n")
        
        # Corrige erro do uvicorn (sys.stdout is None) em modo --windowed
        log_path = os.path.join(exe_dir, "launcher_logs.txt")
        log_file = open(log_path, "a", encoding="utf-8", buffering=1) # line buffered
        if sys.stdout is None:
            sys.stdout = log_file
        if sys.stderr is None:
            sys.stderr = log_file
            
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            import traceback
            log_file.write("Uncaught exception:\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=log_file)
            log_file.flush()
            
        sys.excepthook = handle_exception
    
    port = 8234
    if is_port_in_use(8000):
        kill_port_occupants(8000)
    if is_port_in_use(port):
        kill_port_occupants(port)
        time.sleep(1)

    threading.Thread(target=wait_and_open_browser, args=(port,), daemon=True).start()

    from api.main import app
    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    except BaseException as e:
        if getattr(sys, "frozen", False):
            import traceback
            with open(os.path.join(os.path.dirname(sys.executable), "launcher_crash.txt"), "a") as f:
                f.write(f"Crash: {type(e).__name__}: {str(e)}\n")
                traceback.print_exc(file=f)
        raise

