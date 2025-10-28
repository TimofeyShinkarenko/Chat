import socket
import threading
import time
import json
from utils.constans import BROADCAST_PORT


class BroadcastDiscovery:
    def __init__(self, broadcast_port=BROADCAST_PORT):
        self.port = broadcast_port
        self.known_users = {}
        self.is_running = True
        self.username = ""
        self.local_ip = ""
        self.tcp_port = 0

        self.users_lock = threading.Lock()

    def start_discovery(self, username, local_ip, tcp_port):
        self.username = username
        self.local_ip = local_ip
        self.tcp_port = tcp_port

        threading.Thread(target=self._announce_worker, daemon=True).start()

        threading.Thread(target=self._listen_worker, daemon=True).start()

        print(f"Broadcast discovery started for {username}")

    def _announce_worker(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        announcement = {
            'type': 'chat_user',
            'username': self.username,
            'ip': self.local_ip,
            'tcp_port': self.tcp_port,
            'timestamp': time.time()
        }

        while self.is_running:
            try:
                message = json.dumps(announcement).encode('utf-8')
                sock.sendto(message, ('255.255.255.255', self.port))
            except Exception as e:
                print(f"Broadcast send error: {e}")

            time.sleep(3)
            announcement['timestamp'] = time.time()

        sock.close()

    def _listen_worker(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        try:
            sock.bind(('', self.port))
        except OSError:
            sock.bind(('0.0.0.0', self.port))

        sock.settimeout(1.0)
        print(f"Broadcast listener started on port {self.port}")

        while self.is_running:
            try:
                data, _ = sock.recvfrom(1024)

                try:
                    message = json.loads(data.decode('utf-8'))
                    if message.get('type') != 'chat_user':
                        continue
                    if message['username'] == self.username:
                        continue

                    user_key = f"{message['username']}_{message['ip']}"

                    with self.users_lock:
                        self.known_users[user_key] = {
                            'username': message['username'],
                            'ip': message['ip'],
                            'tcp_port': message['tcp_port'],
                            'last_seen': message['timestamp']
                        }

                except (json.JSONDecodeError, KeyError):
                    continue

            except socket.timeout:
                continue
            except Exception as e:
                if self.is_running:
                    print(f"Broadcast receive error: {e}")

        sock.close()

    def get_online_users(self):
        with self.users_lock:
            current_time = time.time()
            expired_users = []

            for key, user in self.known_users.items():
                if current_time - user['last_seen'] > 120:
                    expired_users.append(key)
                    print(f"User {user['username']} expired")

            for key in expired_users:
                if key in self.known_users:
                    del self.known_users[key]

            return list(self.known_users.values())

    def stop(self):
        self.is_running = False