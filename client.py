import socket
import select
import time
import pickle
from message import Message

class Client:

    BUF_SIZ = 512

    def __init__(self, server_ip, server_port):
        self.server_ip = server_ip
        self.server_port = server_port
        self.client = None


    def connect_to_server(self):
        print(f"Attempting to connect to {self.server_ip}:{self.server_port} with timeout of 5 seconds...")
        ret = 1
        while ret != 0:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.settimeout(5)
            start = time.perf_counter()
            ret = self.client.connect_ex((self.server_ip, self.server_port))
            latency = (time.perf_counter() - start)*1000
            if ret == 0:
                print(f"Connected successfully with latency {latency}ms")
                self.client.settimeout(None)
            else:
                print("Failed to connect. Trying again..") 
                time.sleep(2)

    def recv_msg(self):
        msg = self.client.recv(Client.BUF_SIZ)

        if not msg:
            print("Connection closed, attempting to reconnect...")
            self.client.close()
            self.client = self.connect_to_server(server_ip, server_port)
            return None

        try:
            msg = pickle.loads(msg)
        except pickle.UnpicklingError as e:
            print(f"Error receiving message from server: {e}")
            return None

        print("Received message:\n", msg)
        return msg

