from tkinter import messagebox
import tkinter as tk
import threading
import socket

from network.tcp_srv import TCPServer
from network.broadcast_discovery import BroadcastDiscovery
from models.user import User
from gui.chat_window import ChatWindow
from utils.constans import BROADCAST_PORT, TCP_PORT


class ChatApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Chat App - Broadcast")
        self.root.geometry("400x300")

        self.current_user = None
        self.tcp_server = None
        self.broadcast_discovery = None
        self.is_running = True

        self.open_chats = {}
        self.show_nickname_screen()

    def show_nickname_screen(self):
        self.clear_screen()

        if self.broadcast_discovery:
            self.broadcast_discovery.stop()
        if self.tcp_server:
            self.tcp_server.close()

        tk.Label(self.root, text="Введите ваш ник:", font=("Arial", 14)).pack(
            pady=20)

        self.nickname_var = tk.StringVar()
        nickname_entry = tk.Entry(self.root, textvariable=self.nickname_var,
                                  font=("Arial", 12))
        nickname_entry.pack(pady=10)
        nickname_entry.focus()

        tk.Button(self.root, text="Подключиться",
                  command=self.process_nickname,
                  font=("Arial", 12), bg="lightblue").pack(pady=20)

        nickname_entry.bind("<Return>", lambda event: self.process_nickname())

    def process_nickname(self):
        nickname = self.nickname_var.get().strip()
        if not nickname:
            messagebox.showerror("Ошибка", "Введите ник!")
            return

        self.current_user = User("", 0, nickname, 0)
        self.clear_screen()
        tk.Label(self.root, text="Запуск сетевых служб...",
                 font=("Arial", 12)).pack(expand=True)
        self.root.update()

        try:
            self.start_tcp_server()

            threading.Thread(target=self.accept_connections_loop,
                             daemon=True).start()

            self.start_broadcast_discovery()
            self.show_users_list()

        except Exception as e:
            messagebox.showerror("Ошибка",
                                 f"Не удалось запустить сетевые службы: {e}")
            self.show_nickname_screen()

    def start_tcp_server(self):
        try:
            self.tcp_server = TCPServer(port=TCP_PORT)
            print(f"TCP сервер запущен на порту {self.tcp_server.port}")
        except Exception as e:
            print(f"Ошибка TCP сервера: {e}")

    def accept_connections_loop(self):
        if not self.tcp_server:
            return

        print(f"Сервер ожидает подключения на {self.tcp_server.port}...")
        while self.is_running:
            try:
                connection, address = self.tcp_server.sock.accept()
                print(f"Новое подключение от {address}")

                threading.Thread(target=self.handle_incoming_client,
                                 args=(connection, address),
                                 daemon=True).start()
            except Exception as e:
                if self.is_running:
                    print(f"Ошибка приема подключения: {e}")
                break

    def handle_incoming_client(self, connection, address):
        try:
            data = connection.recv(1024)
            if not data:
                connection.close()
                return

            username = data.decode('utf-8').strip()
            print(f"Подключившийся пользователь: {username} c {address}")

            target_user = None
            if self.broadcast_discovery:
                all_users = self.broadcast_discovery.get_online_users()
                for u in all_users:
                    if u['username'] == username and u['ip'] == address[0]:
                        target_user = User(u['ip'], u['tcp_port'],
                                           u['username'], 0)
                        break

            if not target_user:
                target_user = User(address[0], 0, username, 0)

            self.root.after(0, lambda: self.open_chat_window(
                target_user, incoming_connection=connection))

        except Exception as e:
            print(f"Ошибка обработки клиента {address}: {e}")
            connection.close()

    def start_broadcast_discovery(self):
        try:
            local_ip = self.get_local_ip()
            tcp_port = self.tcp_server.port

            self.broadcast_discovery = BroadcastDiscovery(
                broadcast_port=BROADCAST_PORT
            )
            self.broadcast_discovery.start_discovery(
                self.current_user.username,
                local_ip,
                tcp_port
            )
            print("Broadcast discovery started")

        except Exception as e:
            print(f"Ошибка запуска обнаружения: {e}")
            raise

    @staticmethod
    def get_local_ip():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip

    def show_users_list(self):
        self.clear_screen()

        title_frame = tk.Frame(self.root)
        title_frame.pack(fill=tk.X, padx=20, pady=10)

        tk.Label(title_frame, text="Обнаруженные пользователи:",
                 font=("Arial", 14)).pack(side=tk.LEFT)

        tk.Label(title_frame, text=f"Ваш ник: {self.current_user.username}",
                 font=("Arial", 10), fg="gray").pack(side=tk.RIGHT)

        list_frame = tk.Frame(self.root)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.users_listbox = tk.Listbox(list_frame, font=("Arial", 12),
                                        yscrollcommand=scrollbar.set)
        self.users_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.users_listbox.yview)

        self.users_listbox.bind("<Double-Button-1>",
                                lambda event: self.start_chat())

        self.update_users_list()

        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)

        tk.Button(button_frame, text="🔄 Обновить",
                  command=self.update_users_list_manual,
                  font=("Arial", 10)).pack(side=tk.LEFT, padx=5)

        tk.Button(button_frame, text="💬 Начать чат", command=self.start_chat,
                  font=("Arial", 10), bg="lightgreen").pack(side=tk.LEFT,
                                                            padx=5)

        tk.Button(button_frame, text="✏️ Сменить ник",
                  command=self.show_nickname_screen,
                  font=("Arial", 10), bg="lightcoral").pack(side=tk.LEFT,
                                                            padx=5)

    def update_users_list_manual(self):
        try:
            self.root.after_cancel(self.update_timer)
        except AttributeError:
            pass
        self.update_users_list()

    def update_users_list(self):
        try:
            self.users_listbox.delete(0, tk.END)

            if not self.broadcast_discovery:
                self.users_listbox.insert(tk.END, "Обнаружение не запущено")
                return

            users = self.broadcast_discovery.get_online_users()

            if not users:
                self.users_listbox.insert(tk.END,
                                          "Пользователи не обнаружены")
                self.users_listbox.config(fg="gray")
            else:
                self.users_listbox.config(fg="black")
                for user in users:
                    self.users_listbox.insert(tk.END,
                                              f"{user['username']} ({user['ip']}:{user['tcp_port']})")

            if self.is_running:
                self.update_timer = self.root.after(3000,
                                                    self.update_users_list)

        except Exception as e:
            if 'invalid command name ".!listbox"' not in str(e):
                print(f"Ошибка обновления списка: {e}")

    def start_chat(self):
        selection = self.users_listbox.curselection()
        if not selection:
            messagebox.showerror("Ошибка", "Выберите пользователя!")
            return

        selected_text = self.users_listbox.get(selection[0])
        if "не обнаружены" in selected_text.lower():
            return

        try:
            username = selected_text.split(" ")[0]
            ip_port = selected_text.split("(")[1].split(")")[0]
            ip, port = ip_port.split(":")

            target_user = User(ip, int(port), username, 0)
            self.open_chat_window(target_user)

        except Exception as e:
            messagebox.showerror("Ошибка",
                                 f"Неверный формат пользователя: {e}")

    def open_chat_window(self, target_user, incoming_connection=None):
        if target_user.username in self.open_chats:
            try:
                chat_win = self.open_chats[target_user.username]
                chat_win.window.deiconify()
                chat_win.window.lift()
                chat_win.window.focus_force()

                if incoming_connection:
                    print(f"Чат с {target_user.username} уже открыт.")
                    incoming_connection.close()
                return
            except tk.TclError:
                del self.open_chats[target_user.username]

        try:
            chat_win = ChatWindow(self.root,
                                  self.current_user,
                                  target_user,
                                  incoming_connection=incoming_connection)

            self.open_chats[target_user.username] = chat_win

            chat_win.window.protocol("WM_DELETE_WINDOW",
                                     lambda
                                         u=target_user.username: self.on_chat_window_close(
                                         u))

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть чат: {e}")
            if incoming_connection:
                incoming_connection.close()

    def on_chat_window_close(self, username):
        if username in self.open_chats:
            try:
                self.open_chats[
                    username].close()
            except Exception as e:
                print(f"Ошибка при закрытии окна чата: {e}")

            if username in self.open_chats:
                del self.open_chats[username]
        print(f"Чат с {username} закрыт.")

    def clear_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def on_closing(self):
        self.is_running = False

        for username in list(self.open_chats.keys()):
            self.on_chat_window_close(username)

        if self.broadcast_discovery:
            self.broadcast_discovery.stop()
        if self.tcp_server:
            self.tcp_server.close()

        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
