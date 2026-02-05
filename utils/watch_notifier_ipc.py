# utils/watch_notifier_ipc.py
import socket
import json
import os

SOCKET_PATH = "/tmp/watch_notifier.sock"

def send_bt_message(address: str, message: str) -> bool:
    """
    Sends a message to a Bluetooth watch via IPC socket.
    Returns True on success, False on any error.
    """
    if not os.path.exists(SOCKET_PATH):
        return False

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(SOCKET_PATH)
            cmd = {"address": address, "message": message}
            sock.sendall(json.dumps(cmd).encode())
            sock.shutdown(socket.SHUT_WR)
            response = sock.recv(4096)
            if response:
                result = json.loads(response.decode())
                return result.get("status") == "ok"
            else:
                return False
    except (FileNotFoundError, ConnectionRefusedError, OSError, json.JSONDecodeError, KeyError):
        return False
