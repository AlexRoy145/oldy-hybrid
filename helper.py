import sys
import time
from pynput import mouse
from pynput.mouse import Button, Controller
from PIL import Image
import ctypes
import ctypes.util
import cv2
import mss
import msvcrt
import numpy as np
from pytessy import PyTessy

# index is raw prediction, value is (x,y) pixel coordinates of the clickbot numbers
coords = []
bbox = []

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

def main():
    global coords
    global bbox
    sct = mss.mss()
    
    print("Click the clickbot's buttons in order from 0-36 to set the coordinates. Start at 0, end at 36.")
    listener = mouse.Listener(on_click=set_clickbot_num_coords)
    listener.start()
    while True:
        if len(coords) == 37:
            break
        time.sleep(1)

    listener.stop()            
    listener.join()

    m = Controller()

    input("Hover the mouse over the upper left corner of the detection zone for the raw prediction number, then hit ENTER.")
    x_top,y_top = m.position
    bbox.append(x_top)
    bbox.append(y_top)

    input("Hover the mouse over the bottom right corner of the detection zone, then hit ENTER.")
    x_bot,y_bot = m.position
    bbox.append(x_bot)
    bbox.append(y_bot)

    print(f"Bounding box: {bbox}")

    m = Controller()
    p = PyTessy()

    while True:
        direction = input("Type A for anticlockwise or C for clockwise, then hit ENTER: ").lower()
        print("Press SPACE when the raw prediction appears, and it will automatically click the correct clickbot number. Press CTRL+C to exit.")
        while True:
            if msvcrt.kbhit():
                if ord(msvcrt.getch()) == 32:
                    break
        now = time.time()
        width = bbox[2]-bbox[0]
        height = bbox[3]-bbox[1]
        sct_img = sct.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon":0})
        pil_image = Image.frombytes('RGB', sct_img.size, sct_img.rgb)
        open_cv_image = np.array(pil_image)
        open_cv_image = open_cv_image[:, :, ::-1].copy() 
        finalimage = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        #image.show()
        end = time.time()

        now_2 = time.time()
        prediction = p.read(finalimage.ctypes, finalimage.shape[1], finalimage.shape[0], 1) 
        end_2 = time.time()

        print(f"Image grab took {end-now:.5f} seconds")
        print(f"OCR took {end_2-now_2:.5f} seconds")
        print(f"RAW PREDICTION: {prediction}")
        try:
            prediction = int(prediction)
        except (ValueError, TypeError) as e:
            print("ERROR: Incorrectly detected raw prediction, could not click.")
            continue

        if prediction < 0 or prediction > 36:
            print("ERROR: Incorrectly detected raw prediction, could not click.")
            continue

        
        m.position = coords[prediction]
        if direction == "a":
            m.press(Button.left)
            m.release(Button.left)
        else:
            m.press(Button.right)
            m.release(Button.right)

        print(f"Clicked at {coords[prediction]}")


main()
