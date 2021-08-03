import socket
import time
import pickle
from message import Message

# 60s
KEEPALIVE_TIMEOUT_MS = 60000

# 3s
KEEPALIVE_INTERVAL_MS = 3000


class Client:
    BUF_SIZ = 512

    def __init__(self, server_ips, server_port):
        self.server_ips = server_ips
        self.server_port = server_port
        self.client = None

    def connect_to_server(self):
        ret = 1
        server_idx = 0
        while ret != 0:
            server_ip = self.server_ips[server_idx % len(self.server_ips)]
            print(f"Attempting to connect to {server_ip}:{self.server_port} with timeout of 3 seconds...")
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.settimeout(3)
            start = time.perf_counter()
            ret = self.client.connect_ex((server_ip, self.server_port))
            latency = (time.perf_counter() - start) * 1000
            if ret == 0:
                print(f"Connected successfully with latency {latency}ms")
                self.client.settimeout(None)

                self.client.ioctl(socket.SIO_KEEPALIVE_VALS, (1, KEEPALIVE_TIMEOUT_MS, KEEPALIVE_INTERVAL_MS))
            else:
                print("Failed to connect.")
                time.sleep(1)

            server_idx += 1

    def recv_msg(self):
        try:
            msg = self.client.recv(Client.BUF_SIZ)
        except (ConnectionResetError, TimeoutError) as e:
            msg = None

        if not msg:
            print("Connection closed, attempting to reconnect...")
            self.client.close()
            self.connect_to_server()
            return None

        try:
            msg = pickle.loads(msg)
        except pickle.UnpicklingError as e:
            print(f"Error receiving message from server: {e}")
            return None

        print("Received message:\n", msg)
        return msg

    def close(self):
        self.client.close()
