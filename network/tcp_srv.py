import socket
import time
from utils.constans import TCP_PORT


class TCPServer:
    def __init__(self, host="", port=TCP_PORT, max_retries=3):
        self.port = port
        self.host = host
        self.sock = None

        for attempt in range(max_retries):
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,
                                     1)
                self.sock.bind((self.host, self.port))
                self.sock.listen(5)
                print(f"TCP Server successfully started on port {self.port}")
                return
            except OSError as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if self.sock:
                    self.sock.close()

                if attempt < max_retries - 1:
                    self.port += 1
                    print(f"Trying port {self.port}...")
                    time.sleep(1)
                else:
                    raise Exception(
                        f"Failed to start TCP server after {max_retries} attempts")

    def close(self):
        if self.sock:
            self.sock.close()
        print("TCP Server closed")