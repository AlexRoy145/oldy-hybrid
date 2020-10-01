import sys
import socket
import time
import pickle
import os.path
import mss
from pynput import mouse
from pynput.mouse import Button, Controller
from pynput import keyboard
from message import Message
import msvcrt
import numpy as np
from clickbot import Clickbot

BUF_SIZ = 4096
CLICKBOT_PROFILE = "profile.dat"
RED_THRESH = 150

def connect_to_server(ip, port):
    print(f"Attempting to connect to {ip}:{port} with timeout of 5 seconds...")
    ret = 1
    while ret != 0:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(5)
        start = time.perf_counter()
        ret = client.connect_ex((ip, port))
        latency = (time.perf_counter() - start)*1000
        if ret == 0:
            print(f"Connected successfully with latency {latency}ms")
            client.settimeout(None)
            return client
        else:
            print("Failed to connect. Trying again..") 
            time.sleep(2)

def main():
    sct = mss.mss()

    #TODO remove this once macro controls are separated from main driver
    m = Controller()
    
    if len(sys.argv) > 2:
        server_ip = sys.argv[1]
        server_port = int(sys.argv[2])
    else:
        print("Usage: py helper_client.py server_ip_address server_port")
        exit()

    clickbot = Clickbot()
    if not clickbot.load_profile(CLICKBOT_PROFILE):
        print("Could not find profile. Setting up from scratch.")
        clickbot.set_clicks()
        clickbot.set_jump_values()
        clickbot.save_profile(CLICKBOT_PROFILE)
   
    # TODO remove this once macro controls are separated from main driver
    bbox = []
    input("Hover the mouse over RED outside bet, then press ENTER:")
    x,y = m.position
    bbox.append(x)
    bbox.append(y)

    input("Press ENTER when ready to connect to server:")
    client = connect_to_server(server_ip, server_port)

    while True:

        print("Listening for commands...")
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
            clickbot.make_clicks(msg.direction, msg.prediction)

        # TODO separate macro functions from driver program
        time.sleep(4)
        sct_img = sct.grab({"left": bbox[0], "top": bbox[1], "width": 1, "height": 1, "mon":0})
        pixel = sct_img.pixel(0, 0)
        if pixel[0] < RED_THRESH:
            k = keyboard.Controller()
            m.position = (bbox[0],bbox[1])
            m.press(Button.left)
            m.release(Button.left)
            k.press(keyboard.Key.f5)
            k.release(keyboard.Key.f5)


main()
