import socket
import pickle
from message import Message

# 60s
KEEPALIVE_TIMEOUT_MS = 60000

# 3s
KEEPALIVE_INTERVAL_MS = 3000

class Server:

    def __init__(self, server_ip, server_port):
        self.server_ip = server_ip
        self.server_port = server_port
        self.clients = {}
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.seq_num = 0


    def accept_new_connections(self):
        while True:
            try:
                num_connections = int(input("Enter how many connections you are expecting. The program will continue only after receiving that many connections: "))
                break
            except ValueError:
                print("Invalid number.")
                continue
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        self.s.bind((self.server_ip, self.server_port)) 
        self.clients = {}
        self.s.listen(0)
        while len(self.clients) != num_connections: 
            # establish connection with client 
            c, addr = self.s.accept() 
            self.clients[addr] = c

            c.ioctl(socket.SIO_KEEPALIVE_VALS, (1, KEEPALIVE_TIMEOUT_MS, KEEPALIVE_INTERVAL_MS))
            print(f"Accepted new connection from {addr}")

        self.s.close()


    def send_message(self, msg):
        msg.seq_num = self.seq_num
        self.seq_num += 1
        for addr, c in self.clients.items():
            #print(f"Sending command to {addr}...")
            try:
                ret = c.send(pickle.dumps(msg))
                #print(f"Sent {ret} byte message: {msg}")
            except OSError:
                print(f"***ERROR*** Failed to send because {addr} is disconnected. If you want this client to be able to receive commands, select menu option N to reset and reconnect all clients.")
                c.shutdown(socket.SHUT_RDWR)
                c.close()
                del self.clients[addr]
        

    def close_and_reaccept_connections(self):
        for addr, c in self.clients.items():
            c.shutdown(socket.SHUT_RDWR)
            c.close()
            print(f"Closed connection to {addr}")
        self.accept_new_connections()

