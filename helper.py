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

def main():
    global coords
    sct = mss.mss()
    
    '''
    print("Click the clickbot's buttons in order from 0-36 to set the coordinates. Start at 0, end at 36.")
    listener = mouse.Listener(on_click=set_clickbot_num_coords)
    listener.start()
    while True:
        if len(coords) == 37:
            break
        time.sleep(.3)

    listener.stop()            
    listener.join()
    '''
    
    m = Controller()
    p = PyTessy()

    bbox = set_detection_zone(m)

    while True:
        direction = input("Type A for anticlockwise, C for clockwise, or D to change detection zone, then hit ENTER: ").lower()
        if direction == "d":
            bbox = set_detection_zone(m)
            continue
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
        cv2.imshow("before", finalimage)
        cv2.waitKey(0)
        end = time.time()

        now_2 = time.time()
        prediction = p.read(finalimage.ctypes, finalimage.shape[1], finalimage.shape[0], 1) 
        end_2 = time.time()

        # post processing of prediction
        prediction = post_process(prediction)

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

        
        '''
        m.position = coords[prediction]
        if direction == "a":
            m.press(Button.left)
            m.release(Button.left)
        else:
            m.press(Button.right)
            m.release(Button.right)
        print(f"Clicked at {coords[prediction]}")
        '''

def post_process(prediction):
    if prediction:
        prediction = prediction.replace("s", "5")
        prediction = prediction.replace("S", "5")

        prediction = prediction.replace("Z", "2")
        prediction = prediction.replace("z", "2")

        prediction = prediction.replace("l", "1")

        prediction = prediction.replace("A", "4")

        prediction = prediction.replace("O", "0")
        prediction = prediction.replace("o", "0")

        prediction = prediction.replace("B", "8")

    return prediction


main()
