import socket
import pickle
import threading
from os import getcwd
from message import Message

# 60s
KEEPALIVE_TIMEOUT_MS = 60000

# 3s
KEEPALIVE_INTERVAL_MS = 3000

WHITELISTED_IPS = getcwd() + "/whitelist.txt"


class Server:

    def __init__(self, server_ip, server_port):
        self.server_ip = server_ip
        self.server_port = server_port
        self.clients = {}
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.seq_num = 0
        self.is_accepting = True
        self.clients_lock = threading.Lock()
        self.accept_thread = None

        self.allowed_ips = []
        with open(WHITELISTED_IPS, "r") as f:
            for line in f:
                self.allowed_ips.append(line.strip())

    def accept_connections(self):
        self.accept_thread = threading.Thread(target=self.accept_new_connections, args=())
        self.accept_thread.daemon = True
        self.accept_thread.start()

    def accept_new_connections(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.bind((self.server_ip, self.server_port))
        self.s.listen(0)
        self.s.settimeout(2)
        while self.is_accepting:
            # establish connection with client 
            try:
                c, addr = self.s.accept()
                if not addr[0] in self.allowed_ips:
                    print(f"Denied connection from {addr[0]}")
                    print(f"allowed ips: {self.allowed_ips}")
                    c.close()
                    continue
            except socket.timeout:
                continue
            with self.clients_lock:
                if addr in self.clients:
                    self.clients[addr].close()
                self.clients[addr] = c

            c.ioctl(socket.SIO_KEEPALIVE_VALS, (1, KEEPALIVE_TIMEOUT_MS, KEEPALIVE_INTERVAL_MS))
            # print(f"Accepted new connection from {addr}")

    def send_message(self, msg):
        msg.seq_num = self.seq_num
        self.seq_num += 1
        to_delete = []
        for addr, c in self.clients.items():
            # print(f"Sending command to {addr}...")
            try:
                ret = c.send(pickle.dumps(msg))
                # print(f"Sent {ret} byte message: {msg}")
            except OSError:
                # print(f"***ERROR*** Failed to send because {addr} is disconnected. If you want this client to be able
                # to receive commands, select menu option N to reset and reconnect all clients.")
                c.shutdown(socket.SHUT_RDWR)
                c.close()
                to_delete.append(addr)

        with self.clients_lock:
            for addr in to_delete:
                del self.clients[addr]

    def stop_accepting(self):
        self.is_accepting = False
        self.accept_thread.join()

    def close_and_reaccept_connections(self):
        for addr, c in self.clients.items():
            c.shutdown(socket.SHUT_RDWR)
            c.close()
            print(f"Closed connection to {addr}")
        self.accept_new_connections()
