import tkinter as tk
from tkinter import scrolledtext
import threading
import time
from datetime import datetime
import queue

from network.tcp_client import TCPClient


class ChatWindow:
    def __init__(self, parent, current_user, target_user,
                 incoming_connection=None):
        self.current_user = current_user
        self.target_user = target_user

        self.tcp_client = None
        self.incoming_connection = incoming_connection

        self.message_queue = queue.Queue()

        self.window = tk.Toplevel(parent)
        self.window.title(f"Чат с {target_user.username}")
        self.window.geometry("500x400")

        self.create_widgets()

        if self.incoming_connection:
            self.add_message("Система",
                             f"Принято подключение от {target_user.username}")
            threading.Thread(target=self.receive_messages_server,
                             daemon=True).start()
        else:
            self.connect_to_target()

        self.window.after(100, self.check_message_queue)

    def create_widgets(self):
        self.chat_frame = tk.Frame(self.window)
        self.chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.chat_text = scrolledtext.ScrolledText(
            self.chat_frame,
            font=("Arial", 11),
            state=tk.DISABLED,
            wrap=tk.WORD
        )
        self.chat_text.pack(fill=tk.BOTH, expand=True)

        input_frame = tk.Frame(self.window)
        input_frame.pack(fill=tk.X, padx=10, pady=10)

        self.message_var = tk.StringVar()
        self.message_entry = tk.Entry(
            input_frame,
            textvariable=self.message_var,
            font=("Arial", 12)
        )
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.message_entry.bind("<Return>", self.send_message)
        self.message_entry.focus()

        self.send_button = tk.Button(
            input_frame,
            text="Отправить",
            command=self.send_message,
            font=("Arial", 10),
            bg="lightblue"
        )
        self.send_button.pack(side=tk.RIGHT, padx=(5, 0))

    def connect_to_target(self):
        try:
            self.tcp_client = TCPClient(self.target_user.addr,
                                        self.target_user.port)
            self.tcp_client.send_message(self.current_user.username)

            self.add_message("Система", "Подключение установлено!")
            threading.Thread(target=self.receive_messages_client,
                             daemon=True).start()
        except Exception as e:
            self.add_message("Система", f"Ошибка подключения: {e}")
            self.message_entry.config(state=tk.DISABLED)
            self.send_button.config(state=tk.DISABLED)

    def send_message(self, event=None):
        message = self.message_var.get().strip()
        if not message:
            return

        try:
            if self.tcp_client:
                self.tcp_client.send_message(message)
            elif self.incoming_connection:
                self.incoming_connection.sendall(message.encode('utf-8'))
            else:
                self.add_message("Система", "Нет подключения.")
                return

            self.add_message("Я", message)
            self.message_var.set("")
        except Exception as e:
            self.add_message("Система", f"Ошибка отправки: {e}")
            self.disconnect()

    def receive_messages_client(self):
        while True:
            try:
                if self.tcp_client:
                    message = self.tcp_client.recv_message()
                    self.message_queue.put(message)
                    if not message:
                        break
                else:
                    time.sleep(0.1)
            except Exception as e:
                print(f"Ошибка приема (клиент): {e}")
                self.message_queue.put(None)
                break

    def receive_messages_server(self):
        while True:
            try:
                data = self.incoming_connection.recv(1024)
                if not data:
                    self.message_queue.put(None)
                    break

                message = data.decode('utf-8')
                self.message_queue.put(message)

            except Exception as e:
                print(f"Ошибка приема (сервер): {e}")
                self.message_queue.put(None)
                break
        self.incoming_connection.close()

    def check_message_queue(self):
        try:
            while not self.message_queue.empty():
                message = self.message_queue.get_nowait()

                if message is None:
                    self.add_message("Система", "Соединение потеряно.")
                    self.disconnect()
                else:
                    self.add_message(self.target_user.username, message)

            self.window.after(100, self.check_message_queue)

        except queue.Empty:
            pass
        except Exception as e:
            print(f"Ошибка обработки очереди: {e}")

    def add_message(self, sender, message):
        try:
            self.chat_text.configure(state=tk.NORMAL)
            timestamp = datetime.now().strftime("%H:%M")
            self.chat_text.insert(tk.END,
                                  f"[{timestamp}] {sender}: {message}\n")
            self.chat_text.see(tk.END)
            self.chat_text.configure(state=tk.DISABLED)
        except tk.TclError:
            pass

    def disconnect(self):
        self.message_entry.config(state=tk.DISABLED)
        self.send_button.config(state=tk.DISABLED)
        if self.tcp_client:
            self.tcp_client.close()
            self.tcp_client = None
        if self.incoming_connection:
            self.incoming_connection.close()
            self.incoming_connection = None

    def close(self):
        self.disconnect()
        self.window.destroy()