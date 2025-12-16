import struct
import json
import base64
from cryptography.fernet import Fernet
from utils.constans import ENCRYPTION_KEY

cipher = Fernet(ENCRYPTION_KEY)


def send_json(sock, data_dict):
    try:
        json_bytes = json.dumps(data_dict).encode('utf-8')
        encrypted_data = cipher.encrypt(json_bytes)
        length_prefix = struct.pack('>I', len(encrypted_data))

        sock.sendall(length_prefix + encrypted_data)
    except Exception as e:
        print(f"Ошибка протокола (send): {e}")
        raise e


def recv_json(sock):
    try:
        length_data = _recv_all(sock, 4)
        if not length_data:
            return None

        msg_length = struct.unpack('>I', length_data)[0]

        encrypted_data = _recv_all(sock, msg_length)
        if not encrypted_data:
            return None

        decrypted_data = cipher.decrypt(encrypted_data)

        return json.loads(decrypted_data.decode('utf-8'))
    except Exception as e:
        print(f"Ошибка протокола (recv): {e}")
        return None


def _recv_all(sock, n):
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data


def encode_file_data(binary_data):
    return base64.b64encode(binary_data).decode('utf-8')


def decode_file_data(base64_string):
    return base64.b64decode(base64_string)