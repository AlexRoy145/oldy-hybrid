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

# index is raw prediction, value is (x,y) pixel coordinates of the clickbot numbers
coords = []
BUF_SIZ = 4096
CLICKBOT_PROFILE = "profile.dat"
RED_THRESH = 150

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
    global coords

    sct = mss.mss()
    '''
    # pixel test
    bbox = []
    m = Controller()
    input("Hover the mouse over RED outside bet, then press ENTER:")
    x,y = m.position
    bbox.append(x)
    bbox.append(y)

    sct = mss.mss()
    sct_img = sct.grab({"left": bbox[0], "top": bbox[1], "width": 1, "height": 1, "mon":0})
    pixel = sct_img.pixel(0, 0)
    print(pixel)

    sct_img = sct.grab({"left": bbox[0], "top": bbox[1], "width": 1, "height": 1, "mon":0})
    pixel = sct_img.pixel(0, 0)
    #if pixel[0] < RED_THRESH:
    k = keyboard.Controller()
    m.position = (bbox[0],bbox[1])
    m.press(Button.left)
    m.release(Button.left)
    k.press(keyboard.Key.f5)
    k.release(keyboard.Key.f5)
    exit()
    '''

    if len(sys.argv) > 2:
        server_ip = sys.argv[1]
        server_port = int(sys.argv[2])
    else:
        print("Usage: py helper_client.py server_ip_address server_port")
        exit()

    
    set_coords = False
    if os.path.isfile(CLICKBOT_PROFILE):
        choice = input("Previous clickbot profile found, use this instead? (Y/N): ").lower()
        if choice == "y":
            with open(CLICKBOT_PROFILE, "rb") as f:
                try:
                    coords = pickle.load(f)
                except pickle.UnpicklingError:
                    print("Error loading clickbot profile file, corrupted or not the right file?")
                    exit()
        else:
            set_coords = True

    else:
        set_coords = True
        

    if set_coords:
        print("Click the clickbot's buttons in order from 0-36 to set the coordinates. Start at 0, end at 36.")
        listener = mouse.Listener(on_click=set_clickbot_num_coords)
        listener.start()
        while True:
            if len(coords) == 37:
                listener.stop()            
                listener.join()
                if os.path.isfile(CLICKBOT_PROFILE):
                    choice = input("Found clickbot profile: overwrite it? (Y/N): ").lower()
                    if choice == "y":
                        with open(CLICKBOT_PROFILE, "wb") as f:
                            pickle.dump(coords, f)
                            print(f"Wrote profile to {CLICKBOT_PROFILE}.")
                else:
                    print("Writing coordinates to profile file.")
                    with open(CLICKBOT_PROFILE, "wb") as f:
                        pickle.dump(coords, f)

                break
            time.sleep(.3)


    m = Controller()

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
            m.position = coords[msg.prediction]
            if msg.direction == "c":
                m.press(Button.left)
                m.release(Button.left)
            else:
                m.press(Button.right)
                m.release(Button.right)

        time.sleep(3)
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
