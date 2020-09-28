import sys
import socket
import time
import pickle
from pynput import mouse
from pynput.mouse import Button, Controller
from message import Message
import msvcrt
import numpy as np

# index is raw prediction, value is (x,y) pixel coordinates of the clickbot numbers
coords = []
MAX_MSG_LEN = 90
BUF_SIZ = 4096

def set_clickbot_num_coords(x, y, button, pressed):
    global coords
    if pressed:
        coords.append((x, y))
        length = len(coords)
        if length == 37:
            print(f"Clicked 36, finished setting up clickbot macro.")
        else:
            print(f"Clicked {length-1}, now click {length}.")
        #debug
        print(f"{length-1} is at {x},{y}")

def connect_to_server(ip, port):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"Attempting to connect to {ip}:{port}...")
    ret = 1
    while ret != 0:
        start = time.perf_counter()
        ret = client.connect_ex((ip, port))
        latency = (time.perf_counter() - start)*1000
        if ret == 0:
            print(f"Connected successfully with latency {latency}ms")
            return client
        else:
            print("Failed to connect. Trying again in 5 seconds.") 
            time.sleep(5)

def main():
    global coords

    if len(sys.argv) > 2:
        server_ip = sys.argv[1]
        server_port = int(sys.argv[2])
    else:
        print("Usage: py helper_client.py server_ip_address server_port")
        exit()

    
    print("Click the clickbot's buttons in order from 0-36 to set the coordinates. Start at 0, end at 36.")
    listener = mouse.Listener(on_click=set_clickbot_num_coords)
    listener.start()
    while True:
        if len(coords) == 37:
            break
        time.sleep(.3)

    listener.stop()            
    listener.join()
    
    m = Controller()

    client = connect_to_server(server_ip, server_port)

    print("Listening for commands...")
    while True:
        msg = client.recv(BUF_SIZ)
        if not msg:
            print("Connection closed, attempting to reconnect...")
            client.close()
            client = connect_to_server(server_ip, server_port)
            continue

        try:
            msg = pickle.loads(msg)
        except pickle.UnpicklingError as e:
            print(f"Error receiving message from server: {e}")
            continue

        print("Received message:\n", msg)

        if msg.test_mode:
            print("TEST MODE, NOT CLICKING.")
        else:
            if msg.error:
                print("Error detecting raw prediction. Skipping this spin.")
                continue
            m.position = coords[msg.prediction]
            if msg.direction == "c":
                m.press(Button.left)
                m.release(Button.left)
            else:
                m.press(Button.right)
                m.release(Button.right)


main()
