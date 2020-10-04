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
        print("""
A: Anticlockwise 
C: Clockwise
D: Change detection zone
J: Change jump values
SJ: Show jump values
T: Test mode (do NOT make clicks)\n""")
        direction = input("Enter menu choice: ")
        if direction == "d":
            clickbot.set_detection_zone()
            ocr.detection_zone = clickbot.detection_zone
            clickbot.save_profile(CLICKBOT_PROFILE)
            continue
        elif direction == "j":
            clickbot.set_jump_values()
            clickbot.save_profile(CLICKBOT_PROFILE)
            continue
        elif direction == "sj":
            jump_anti, jump_clock = clickbot.get_jump_values()
            print(f"Anticlockwise jump values: {jump_anti}")
            print(f"Clockwise jump values: {jump_clock}")
            continue
        elif direction == "t":
            print ("TEST MODE: Press SPACE when the raw prediction appears, and program will print what OCR thinks the raw is. It will also yield tuned predictions for CLOCKWISE.") 
        elif direction != "a" and direction != "c":
            print("Invalid menu option.")
            continue
        print("Press SPACE when the raw prediction appears, and it will automatically click the correct clickbot number. Press CTRL+C to exit.")
        try:
            while True:
                if msvcrt.kbhit():
                    if ord(msvcrt.getch()) == 32:
                        break
        except KeyboardInterrupt:
            continue

        raw_prediction = ocr.read_prediction()
        print(f"RAW PREDICTION: {raw_prediction}")

        try:
            raw_prediction = int(raw_prediction)
        except (ValueError, TypeError) as e:
            print("ERROR: Incorrectly detected raw prediction, could not click.")
            continue

        if raw_prediction < 0 or raw_prediction > 36:
            print("ERROR: Incorrectly detected raw prediction, could not click.")
            continue

        tuned_predictions = clickbot.get_tuned_from_raw(direction, raw_prediction)
        print(f"TUNED PREDICTIONS: {tuned_predictions}")

        clickbot.make_clicks_given_tuned(direction, tuned_predictions)


main()
