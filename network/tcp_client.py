import socket
from network.protocol import send_json, recv_json

class TCPClient:
    def __init__(self, host, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

    def send_data(self, payload):
        send_json(self.sock, payload)

    def recv_data(self):
        return recv_json(self.sock)

    def close(self):
        try:
            self.sock.close()
        except:
            pass