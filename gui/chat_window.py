import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import threading
import queue
import os
from datetime import datetime

from network.tcp_client import TCPClient
from network.protocol import send_json, recv_json, encode_file_data, \
    decode_file_data


class ChatWindow:
    def __init__(self, parent, current_user, target_user,
                 incoming_connection=None):
        self.current_user = current_user
        self.target_user = target_user
        self.incoming_conn = incoming_connection
        self.tcp_client = None

        self.msg_queue = queue.Queue()
        self.is_alive = True

        self.window = tk.Toplevel(parent)
        self.window.title(f"Чат с {target_user.username} (Encrypted)")
        self.window.geometry("500x450")

        self.create_widgets()

        if self.incoming_conn:
            self.add_sys_msg(
                f"Входящее подключение от {target_user.username}")
            threading.Thread(target=self.rx_loop, args=(self.incoming_conn,),
                             daemon=True).start()
        else:
            self.connect_init()

        self.window.after(100, self.process_queue)

    def create_widgets(self):
        self.chat_area = scrolledtext.ScrolledText(self.window,
                                                   state='disabled',
                                                   wrap=tk.WORD,
                                                   font=("Arial", 10))
        self.chat_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.chat_area.tag_config('me', foreground='blue')
        self.chat_area.tag_config('them', foreground='green')
        self.chat_area.tag_config('sys', foreground='gray',
                                  font=("Arial", 9, "italic"))

        # Зона ввода
        frame = tk.Frame(self.window)
        frame.pack(fill=tk.X, padx=5, pady=5)

        self.entry_var = tk.StringVar()
        entry = tk.Entry(frame, textvariable=self.entry_var,
                         font=("Arial", 11))
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        entry.bind("<Return>", self.send_text)

        btn_send = tk.Button(frame, text="Отпр.", command=self.send_text,
                             bg="#DDDDDD")
        btn_send.pack(side=tk.LEFT, padx=5)

        btn_file = tk.Button(frame, text="📎 Файл", command=self.req_send_file,
                             bg="#FFD700")
        btn_file.pack(side=tk.LEFT)

        self.status_lbl = tk.Label(self.window, text="Готов", bd=1,
                                   relief=tk.SUNKEN, anchor=tk.W)
        self.status_lbl.pack(side=tk.BOTTOM, fill=tk.X)

    def connect_init(self):
        def connector():
            try:
                client = TCPClient(self.target_user.addr,
                                   self.target_user.port)
                client.send_data({'type': 'handshake',
                                  'username': self.current_user.username})

                self.tcp_client = client
                self.msg_queue.put(('sys', "Подключено!"))
                threading.Thread(target=self.rx_loop, args=(client.sock,),
                                 daemon=True).start()
            except Exception as e:
                self.msg_queue.put(('sys', f"Ошибка подключения: {e}"))

        threading.Thread(target=connector, daemon=True).start()

    def send_text(self, event=None):
        text = self.entry_var.get().strip()
        if not text: return

        payload = {'type': 'msg', 'text': text}
        if self._send_packet(payload):
            self.add_msg("Я", text, 'me')
            self.entry_var.set("")

    def req_send_file(self):
        path = filedialog.askopenfilename()
        if not path: return

        size = os.path.getsize(path)
        name = os.path.basename(path)

        payload = {
            'type': 'file_req',
            'name': name,
            'size': size
        }
        if self._send_packet(payload):
            self.add_sys_msg(
                f"Ожидание принятия файла: {name} ({size} байт)...")
            self.pending_file = path

    def _send_packet(self, payload):
        conn = self.incoming_conn or (
            self.tcp_client.sock if self.tcp_client else None)
        if not conn:
            self.add_sys_msg("Нет соединения")
            return False
        try:
            send_json(conn, payload)
            return True
        except Exception as e:
            self.add_sys_msg(f"Ошибка отправки: {e}")
            self.close()
            return False

    def rx_loop(self, sock):
        while self.is_alive:
            try:
                data = recv_json(sock)  # Используем наш secure protocol
                if data is None: break
                self.msg_queue.put(('protocol', data))
            except:
                break
        self.msg_queue.put(('sys', "Собеседник отключился"))
        self.disconnect()

    def process_queue(self):
        if not self.is_alive: return
        try:
            while True:
                kind, content = self.msg_queue.get_nowait()
                if kind == 'sys':
                    self.add_sys_msg(content)
                elif kind == 'protocol':
                    self.handle_packet(content)
        except queue.Empty:
            pass
        self.window.after(100, self.process_queue)

    def handle_packet(self, pkg):
        ptype = pkg.get('type')

        if ptype == 'msg':
            self.add_msg(self.target_user.username, pkg['text'], 'them')

        elif ptype == 'file_req':
            name = pkg['name']
            size = pkg['size']
            msg = f"Вам отправляют файл:\n{name}\nРазмер: {size} байт.\nПринять?"
            if messagebox.askyesno("Входящий файл", msg, parent=self.window):
                save_path = filedialog.asksaveasfilename(initialfile=name)
                if save_path:
                    self._send_packet({'type': 'file_resp', 'status': 'ok'})
                    self.incoming_file_path = save_path
                    self.incoming_file_size = size
                    self.received_bytes = 0
                    self.status_lbl.config(text=f"Прием файла: 0/{size}")
                else:
                    self._send_packet({'type': 'file_resp', 'status': 'no'})
            else:
                self._send_packet({'type': 'file_resp', 'status': 'no'})

        elif ptype == 'file_resp':
            if pkg['status'] == 'ok':
                self.add_sys_msg("Файл принят. Начинаю отправку...")
                threading.Thread(target=self.worker_send_file,
                                 args=(self.pending_file,),
                                 daemon=True).start()
            else:
                self.add_sys_msg("Собеседник отклонил передачу файла.")

        elif ptype == 'file_chunk':
            if hasattr(self, 'incoming_file_path'):
                chunk = decode_file_data(pkg['data'])
                with open(self.incoming_file_path, 'ab') as f:
                    f.write(chunk)

                self.received_bytes += len(chunk)
                percent = int(
                    (self.received_bytes / self.incoming_file_size) * 100)
                self.status_lbl.config(text=f"Загрузка: {percent}%")

                if self.received_bytes >= self.incoming_file_size:
                    self.status_lbl.config(text="Файл получен!")
                    self.add_sys_msg(
                        f"Файл сохранен: {self.incoming_file_path}")
                    del self.incoming_file_path

    def worker_send_file(self, filepath):
        try:
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(
                        4096 * 3)
                    if not chunk: break

                    b64_chunk = encode_file_data(chunk)
                    self._send_packet(
                        {'type': 'file_chunk', 'data': b64_chunk})

            self.msg_queue.put(('sys', "Отправка файла завершена"))
        except Exception as e:
            self.msg_queue.put(('sys', f"Ошибка чтения/отправки файла: {e}"))

    def add_msg(self, sender, text, tag):
        self.chat_area.configure(state='normal')
        t = datetime.now().strftime("%H:%M")
        self.chat_area.insert(tk.END, f"[{t}] {sender}: {text}\n", tag)
        self.chat_area.see(tk.END)
        self.chat_area.configure(state='disabled')

    def add_sys_msg(self, text):
        self.chat_area.configure(state='normal')
        self.chat_area.insert(tk.END, f"SYSTEM: {text}\n", 'sys')
        self.chat_area.see(tk.END)
        self.chat_area.configure(state='disabled')

    def disconnect(self):
        if self.tcp_client: self.tcp_client.close()
        if self.incoming_conn:
            try:
                self.incoming_conn.close()
            except:
                pass
        self.tcp_client = None
        self.incoming_conn = None

    def close(self):
        self.is_alive = False
        self.disconnect()
        self.window.destroy()