from tkinter import messagebox
import tkinter as tk
import threading
import socket

from network.tcp_srv import TCPServer
from network.broadcast_discovery import BroadcastDiscovery
from network.protocol import recv_json
from models.user import User
from gui.chat_window import ChatWindow
from utils.constans import BROADCAST_PORT, TCP_PORT


class ChatApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Chat App - Secure")
        self.root.geometry("400x500")

        self.current_user = None
        self.tcp_server = None
        self.broadcast_discovery = None
        self.is_running = True

        self.open_chats = {}
        self.show_nickname_screen()

    def show_nickname_screen(self):
        self.clear_screen()
        if self.broadcast_discovery: self.broadcast_discovery.stop()
        if self.tcp_server: self.tcp_server.close()

        tk.Label(self.root, text="Введите ваш ник:", font=("Arial", 14)).pack(
            pady=40)
        self.nickname_var = tk.StringVar()
        entry = tk.Entry(self.root, textvariable=self.nickname_var,
                         font=("Arial", 12))
        entry.pack(pady=10)
        entry.focus()
        tk.Button(self.root, text="Подключиться",
                  command=self.process_nickname,
                  font=("Arial", 12), bg="lightblue").pack(pady=20)
        entry.bind("<Return>", lambda event: self.process_nickname())

    def process_nickname(self):
        nickname = self.nickname_var.get().strip()
        if not nickname: return
        self.current_user = User("", 0, nickname, 0)
        self.clear_screen()
        tk.Label(self.root, text="Запуск служб...", font=("Arial", 12)).pack(
            expand=True)
        self.root.update()

        try:
            self.start_tcp_server()
            threading.Thread(target=self.accept_connections_loop,
                             daemon=True).start()
            self.start_broadcast_discovery()
            self.show_users_list()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Сбой: {e}")
            self.show_nickname_screen()

    def start_tcp_server(self):
        self.tcp_server = TCPServer(port=TCP_PORT)

    def accept_connections_loop(self):
        if not self.tcp_server: return
        while self.is_running:
            try:
                conn, addr = self.tcp_server.sock.accept()
                threading.Thread(target=self.handle_incoming_client,
                                 args=(conn, addr), daemon=True).start()
            except:
                break

    def handle_incoming_client(self, connection, address):
        try:
            data = recv_json(connection)
            if not data or data.get('type') != 'handshake':
                connection.close()
                return

            username = data.get('username', 'Unknown')

            target_user = User(address[0], 0, username, 0)
            if self.broadcast_discovery:
                for u in self.broadcast_discovery.get_online_users():
                    if u['username'] == username and u['ip'] == address[0]:
                        target_user = User(u['ip'], u['tcp_port'],
                                           u['username'], 0)
                        break

            self.root.after(0, lambda: self.open_chat_window(target_user,
                                                             connection))
        except Exception as e:
            print(f"Ошибка рукопожатия: {e}")
            connection.close()

    def start_broadcast_discovery(self):
        self.broadcast_discovery = BroadcastDiscovery(BROADCAST_PORT)
        self.broadcast_discovery.start_discovery(self.current_user.username,
                                                 self.get_local_ip(),
                                                 self.tcp_server.port)

    @staticmethod
    def get_local_ip():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 1))
            ip = s.getsockname()[0]
        except:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip

    def show_users_list(self):
        self.clear_screen()

        title_frame = tk.Frame(self.root)
        title_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(title_frame, text="Онлайн:",
                 font=("Arial", 12, "bold")).pack(side=tk.LEFT)
        tk.Label(title_frame, text=f"Вы: {self.current_user.username}",
                 fg="blue").pack(side=tk.RIGHT)

        button_frame = tk.Frame(self.root)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10, padx=10)

        tk.Button(button_frame, text="Обновить",
                  command=self.update_users_list_manual).pack(side=tk.LEFT,
                                                              fill=tk.X,
                                                              expand=True,
                                                              padx=2)
        tk.Button(button_frame, text="Чат", command=self.start_chat,
                  bg="#90EE90").pack(side=tk.LEFT, fill=tk.X, expand=True,
                                     padx=2)
        tk.Button(button_frame, text="Выход",
                  command=self.show_nickname_screen, bg="#FFB6C1").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        list_frame = tk.Frame(self.root)
        list_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10,
                        pady=5)

        sb = tk.Scrollbar(list_frame)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.users_listbox = tk.Listbox(list_frame, font=("Arial", 11),
                                        yscrollcommand=sb.set)
        self.users_listbox.pack(fill=tk.BOTH, expand=True)
        sb.config(command=self.users_listbox.yview)
        self.users_listbox.bind("<Double-Button-1>",
                                lambda e: self.start_chat())

        self.update_users_list()

    def update_users_list_manual(self):
        if hasattr(self, 'update_timer'): self.root.after_cancel(
            self.update_timer)
        self.update_users_list()

    def update_users_list(self):
        try:
            self.users_listbox.delete(0, tk.END)
            users = self.broadcast_discovery.get_online_users() if self.broadcast_discovery else []

            if not users:
                self.users_listbox.insert(tk.END, "Нет пользователей")
            else:
                for user in users:
                    display = f"{user['username']} [{user['ip']}]"
                    self.users_listbox.insert(tk.END, display)

            if self.is_running:
                self.update_timer = self.root.after(3000,
                                                    self.update_users_list)
        except Exception:
            pass

    def start_chat(self):
        sel = self.users_listbox.curselection()
        if not sel: return
        text = self.users_listbox.get(sel[0])
        if "Нет пользователей" in text: return

        try:
            username = text.split(" [")[0]
            full_data = next(
                (u for u in self.broadcast_discovery.get_online_users()
                 if u['username'] == username), None)
            if full_data:
                target = User(full_data['ip'], full_data['tcp_port'],
                              username, 0)
                self.open_chat_window(target)
        except Exception as e:
            print(f"Err parsing user: {e}")

    def open_chat_window(self, target_user, incoming_connection=None):
        if target_user.username in self.open_chats:
            try:
                self.open_chats[target_user.username].window.deiconify()
                self.open_chats[target_user.username].window.lift()
                return
            except:
                del self.open_chats[target_user.username]

        cw = ChatWindow(self.root, self.current_user, target_user,
                        incoming_connection)
        self.open_chats[target_user.username] = cw
        cw.window.protocol("WM_DELETE_WINDOW",
                           lambda: self.on_chat_window_close(
                               target_user.username))

    def on_chat_window_close(self, username):
        if username in self.open_chats:
            self.open_chats[username].close()
            del self.open_chats[username]

    def clear_screen(self):
        for w in self.root.winfo_children(): w.destroy()

    def on_closing(self):
        self.is_running = False
        if self.broadcast_discovery: self.broadcast_discovery.stop()
        if self.tcp_server: self.tcp_server.close()
        self.root.destroy()
        import os;
        os._exit(0)  # Принудительное завершение потоков

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()