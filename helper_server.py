import sys
import socket
import select
import time
import pickle
from pynput import mouse
from pynput.mouse import Button, Controller
from PIL import Image
from message import Message
import ctypes
import ctypes.util
import cv2
import os.path
import mss
import msvcrt
import numpy as np
from pytessy import PyTessy

SOCKET_TIMEOUT = 30
CLICKBOT_PROFILE = "profile.dat"

# index is raw prediction, value is (x,y) pixel coordinates of the clickbot numbers
coords = []
seq_num = 0

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

def set_detection_zone(m):
    bbox = []
    input("Hover the mouse over the upper left corner of the detection zone for the raw prediction number, then hit ENTER.")
    x_top,y_top = m.position
    bbox.append(x_top)
    bbox.append(y_top)

    input("Hover the mouse over the bottom right corner of the detection zone, then hit ENTER.")
    x_bot,y_bot = m.position
    bbox.append(x_bot)
    bbox.append(y_bot)

    print(f"Bounding box: {bbox}")
    return bbox

def accept_new_connections(server_ip, server_port):
    while True:
        try:
            num_connections = int(input("Enter how many connections you are expecting. The program will continue only after receiving that many connections: "))
            break
        except ValueError:
            print("Invalid number.")
            continue
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
    s.bind((server_ip, server_port)) 
    clients = {}
    s.listen(0)
    while len(clients) != num_connections: 
        # establish connection with client 
        c, addr = s.accept() 
        clients[addr] = c
        print(f"Accepted new connection from {addr}")

    s.close()
    return clients

def send_message(clients, msg):
    global seq_num
    msg.seq_num = seq_num
    seq_num += 1
    for addr, c in clients.items():
        print(f"Sending command to {addr}...")
        try:
            ret = c.send(pickle.dumps(msg))
            print(f"Sent {ret} byte message: {msg}")
        except OSError:
            print(f"***ERROR*** Failed to send because {addr} is disconnected. If you want this client to be able to receive commands, select menu option N to reset and reconnect all clients.")

    

def main():
    global coords

    if len(sys.argv) > 2:
        server_ip = sys.argv[1]
        server_port = int(sys.argv[2])
    else:
        print("Usage: py helper_server.py server_ip_address server_port")
        exit()

    sct = mss.mss()
   
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
    p = PyTessy()

    bbox = set_detection_zone(m)
      
    clients = accept_new_connections(server_ip, server_port)
      
    while True:
        msg = Message()
        print("""\nA: Anticlockwise, click for yourself and send click command to clients.
C: Clockwise, click for yourself and send click command to clients.
D: Change the detection zone.
T: Test mode (do NOT make clicks, but send TEST send commands to clients to test connectivity).
N: Close all current connections with clients, and listen/accept new connections. Use this to refresh the state of connections (for example, clients dying and wanting to reconnect, or adding a new client.)
AM: Anticlockwise Me Only, click for yourself and DON'T send click commands to clients.
CM: Clockwise Me Only, click for yourself and DON'T send click commands to clients.\n""")
        direction = input("Enter menu option: ").lower()
        if not direction:
            continue
        if direction == "n":
            for addr, c in clients.items():
                c.shutdown(socket.SHUT_RDWR)
                c.close()
                print(f"Closed connection to {addr}")
            clients = accept_new_connections(server_ip, server_port)
            continue
        if direction == "d":
            bbox = set_detection_zone(m)
            continue
        if direction == "t":
            print ("TEST MODE: Press SPACE when the raw prediction appears, and will print what OCR thinks the raw is.") 
            msg.test_mode = True
        else:
            print("Press SPACE when the raw prediction appears, and it will automatically click the correct clickbot number. Press CTRL+C to exit.")
        try:
            while True:
                if msvcrt.kbhit():
                    if ord(msvcrt.getch()) == 32:
                        break
        except KeyboardInterrupt:
            continue
            
        now = time.time()
        width = bbox[2]-bbox[0]
        height = bbox[3]-bbox[1]
        sct_img = sct.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon":0})
        pil_image = Image.frombytes('RGB', sct_img.size, sct_img.rgb)
        open_cv_image = np.array(pil_image)
        open_cv_image = open_cv_image[:, :, ::-1].copy() 


        finalimage = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        ret,thresholded = cv2.threshold(finalimage, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)

        '''
        cv2.imshow('before binarization', finalimage)
        cv2.waitKey(0)
        cv2.imshow('after binarization', thresholded)
        cv2.waitKey(0)
        '''

        finalimage = thresholded
        end = time.time()

        now_2 = time.time()
        prediction = p.read(finalimage.ctypes, finalimage.shape[1], finalimage.shape[0], 1) 
        end_2 = time.time()

        # post processing of prediction
        prediction = post_process(prediction)
        msg.direction = direction

        print(f"Image grab took {end-now:.5f} seconds")
        print(f"OCR took {end_2-now_2:.5f} seconds")
        print(f"RAW PREDICTION: {prediction}")
        try:
            prediction = int(prediction)
        except (ValueError, TypeError) as e:
            print("ERROR: Incorrectly detected raw prediction, could not click.")
            msg.error = True
            if not "m" in direction:
                send_message(clients, msg)
            continue

        if prediction < 0 or prediction > 36:
            print("ERROR: Incorrectly detected raw prediction, could not click.")
            msg.error = True
            if not "m" in direction:
                send_message(clients, err)
            continue

        '''
        if direction != "t": 
            m.position = coords[prediction]
            if direction == "c":
                m.press(Button.left)
                m.release(Button.left)
            else:
                m.press(Button.right)
                m.release(Button.right)
            print(f"Clicked at {coords[prediction]}")
        '''

        if not "m" in direction:
            msg.prediction = prediction
            send_message(clients, msg)

def post_process(prediction):
    if prediction:
        prediction = prediction.replace("s", "5")
        prediction = prediction.replace("S", "5")

        prediction = prediction.replace("Z", "2")
        prediction = prediction.replace("z", "2")

        prediction = prediction.replace("l", "1")
        prediction = prediction.replace("L", "1")
        prediction = prediction.replace("i", "1")

        prediction = prediction.replace("g", "9")
        prediction = prediction.replace("G", "9")

        prediction = prediction.replace("A", "4")

        prediction = prediction.replace("O", "0")
        prediction = prediction.replace("o", "0")
        prediction = prediction.replace("Q", "0")

        prediction = prediction.replace("B", "8")

    return prediction


main()
