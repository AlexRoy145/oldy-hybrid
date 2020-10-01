import sys
import time
import ctypes
import ctypes.util
import cv2
import os.path
import pickle
import mss
import msvcrt
import numpy as np
from PIL import Image
from pytessy import PyTessy
from clickbot import Clickbot

# index is raw prediction, value is (x,y) pixel coordinates of the clickbot numbers
CLICKBOT_PROFILE = "profile.dat"

def main():
    sct = mss.mss()
    p = PyTessy()

    clickbot = Clickbot()
    if not clickbot.load_profile(CLICKBOT_PROFILE):
        print("Could not find profile. Setting up from scratch.")
        clickbot.set_clicks()
        clickbot.set_jump_values()
        clickbot.set_detection_zone()
        clickbot.save_profile(CLICKBOT_PROFILE)
             
    while True:
        direction = input("Type A for anticlockwise, C for clockwise, D to change detection zone, J to change jump values, or T for test mode (do NOT make clicks), then hit ENTER: ").lower()
        if direction == "d":
            clickbot.set_detection_zone()
            clickbot.save_profile(CLICKBOT_PROFILE)
            continue
        if direction == "j":
            clickbot.set_jump_values()
            clickbot.save_profile(CLICKBOT_PROFILE)
        if direction == "t":
            print ("TEST MODE: Press SPACE when the raw prediction appears, and will print what OCR thinks the raw is.") 
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
        bbox = clickbot.detection_zone
        width = bbox[2]-bbox[0]
        height = bbox[3]-bbox[1]
        sct_img = sct.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon":0})
        pil_image = Image.frombytes('RGB', sct_img.size, sct_img.rgb)
        open_cv_image = np.array(pil_image)
        open_cv_image = open_cv_image[:, :, ::-1].copy() 

        finalimage = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        ret,thresholded = cv2.threshold(finalimage, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)

        finalimage = thresholded
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

        clickbot.make_clicks(direction, prediction)


def post_process(prediction):
    if prediction:
        prediction = prediction.replace("s", "5")
        prediction = prediction.replace("S", "5")

        prediction = prediction.replace("Z", "2")
        prediction = prediction.replace("z", "2")

        prediction = prediction.replace("l", "1")
        prediction = prediction.replace("L", "1")
        prediciton = prediction.replace("i", "1")

        prediction = prediction.replace("g", "9")
        prediction = prediction.replace("G", "9")

        prediction = prediction.replace("A", "4")

        prediction = prediction.replace("O", "0")
        prediction = prediction.replace("o", "0")
        prediction = prediction.replace("Q", "0")

        prediction = prediction.replace("B", "8")

    return prediction


main()
