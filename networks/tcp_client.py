import socket
from utils.constans import BUFFER_SIZE

class TCPClient:
    def __init__(self, host, port, buffer_size=BUFFER_SIZE):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self.buffer_size = buffer_size

    def send_message(self, message):
        self.sock.sendall(message.encode('utf-8'))

    def recv_message(self):
        data = self.sock.recv(self.buffer_size)
        if not data:
            return None
        return data.decode('utf-8')

    def close(self):
        self.sock.close()