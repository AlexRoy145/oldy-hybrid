import sys
import time
from pynput import mouse
from pynput.mouse import Button, Controller
from PIL import Image
import mss
import pytesseract

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

def set_ocr_for_raw_prediction(x, y, button, pressed):
    global bbox
    if pressed:
        bbox.append(x)
        bbox.append(y)
        length = len(bbox)
        if length == 4:
            print(f"Bounding box set. Program can now begin.")
        else:
            print(f"Clicked top left corner, now click bottom right corner.")
            print(f"x: {x}, y: {y}")


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

    print("Click the upper left corner of the detection zone for the raw prediction number, then click the bottom right corner.")
    listener = mouse.Listener(on_click=set_ocr_for_raw_prediction)
    listener.start()
    while True:
        if len(bbox) == 4:
            break
        time.sleep(1)

    listener.stop()
    listener.join()

    m = Controller()

    while True:
        input("Press ENTER when the raw prediction appears, and it will automatically click the correct clickbot number.")
        now = time.time()
        sct_img = sct.grab({"left": bbox[0], "top": bbox[1], "width": bbox[2]-bbox[0], "height": bbox[3]-bbox[1], "mon":0})
        image = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        end = time.time()

        now_2 = time.time()
        prediction = pytesseract.image_to_string(image)
        end_2 = time.time()

        print(f"Image grab took {end-now}")
        print(f"OCR took {end_2-now_2}")
        try:
            prediction = int(prediction)
        except ValueError:
            print("ERROR: Incorrectly detected raw prediction, could not click.")
            continue

        if prediction < 0 or prediction > 36:
            print("ERROR: Incorrectly detected raw prediction, could not click.")
            continue

        print(f"RAW PREDICTION: {prediction}")
        
        m.position = coords[prediction]
        m.press(Button.left)
        m.release(Button.left)
        print(f"Clicked at {coords[prediction]}")


main()
