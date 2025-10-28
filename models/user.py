class User:
    def __init__(self, addr: str, port: int, username: str, id: int):
        self.id = id
        self.username = username
        self.addr = addr
        self.port = port

    def __str__(self):
        return f"User({self.username}, {self.addr}:{self.port})"