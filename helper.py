import msvcrt
import sys
import time
from clickbot import Clickbot
from ocr import OCR

# index is raw prediction, value is (x,y) pixel coordinates of the clickbot numbers
CLICKBOT_PROFILE = "profile.dat"

def main():

    clickbot = Clickbot()
    if not clickbot.load_profile(CLICKBOT_PROFILE):
        print("Could not find profile. Setting up from scratch.")
        clickbot.set_clicks()
        clickbot.set_jump_values()
        clickbot.set_detection_zone()
        clickbot.save_profile(CLICKBOT_PROFILE)

    ocr = OCR(clickbot.detection_zone)
             
    while True:
        direction = input("Type A for anticlockwise, C for clockwise, D to change detection zone, J to change jump values, or T for test mode (do NOT make clicks), then hit ENTER: ").lower()
        if direction == "d":
            clickbot.set_detection_zone()
            ocr.detection_zone = clickbot.detection_zone
            clickbot.save_profile(CLICKBOT_PROFILE)
            continue
        if direction == "j":
            clickbot.set_jump_values()
            clickbot.save_profile(CLICKBOT_PROFILE)
            continue
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

        prediction = ocr.read_prediction()

        try:
            prediction = int(prediction)
        except (ValueError, TypeError) as e:
            print("ERROR: Incorrectly detected raw prediction, could not click.")
            continue

        if prediction < 0 or prediction > 36:
            print("ERROR: Incorrectly detected raw prediction, could not click.")
            continue

        clickbot.make_clicks_given_raw(direction, prediction)


main()
