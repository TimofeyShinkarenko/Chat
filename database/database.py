import sqlite3
import os


def get_db_path():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    data_dir = os.path.join(project_root, 'data')

    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    return os.path.join(data_dir, 'users_table.db')


def get_connection():
    db_path = get_db_path()
    return sqlite3.connect(db_path)


def create_table():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            id_key INTEGER PRIMARY KEY AUTOINCREMENT,
            id INTEGER,
            username TEXT,
            addr TEXT,
            port INTEGER)
        ''')

    connection.commit()
    connection.close()


def add_user(id, username, addr, port):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        'INSERT INTO Users (id, username, addr, port) VALUES (?, ?, ?, ?)',
        (id, username, addr, port))
    connection.commit()
    connection.close()


def get_all_users():
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute('SELECT * FROM Users')
    users = cursor.fetchall()

    users_list = []
    for user in users:
        from models.user import User
        users_list.append(User(user[2], user[4], user[3], user[1]))

    connection.close()
    return users_list