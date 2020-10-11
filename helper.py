import argparse
import msvcrt
import sys
import time
from clickbot import Clickbot
from macro import Macro
from ocr import OCR

# index is raw prediction, value is (x,y) pixel coordinates of the clickbot numbers
CLICKBOT_PROFILE = "profile.dat"
MACRO_PROFILE = "macro.dat"

REFRESH_BET_MACRO = "Refresh page if kicked for late bets"
RESIGNIN_MACRO = "Resign into the website and pull up betting interface"

MAX_MACRO_COUNT = 3

def main():

    parser = argparse.ArgumentParser(description="Run the solo betting program.")
    parser.add_argument("--use-refresh-macro", action="store_true")
    parser.add_argument("--use-signin-macro", action="store_true")
    args = parser.parse_args()

    use_macro = args.use_refresh_macro or args.use_signin_macro

    clickbot = Clickbot()
    if not clickbot.load_profile(CLICKBOT_PROFILE):
        print("Could not find profile. Setting up from scratch.")
        clickbot.set_clicks()
        clickbot.set_jump_values()
        clickbot.set_detection_zone()
        clickbot.save_profile(CLICKBOT_PROFILE)

    if use_macro:
        macro = Macro()
        if not macro.load_profile(MACRO_PROFILE):
            macro.set_screen_condition()
            if args.use_refresh_macro:
                macro.record_macro(REFRESH_BET_MACRO)
            if args.use_signin_macro:
                macro.record_macro(RESIGNIN_MACRO)
            macro.save_profile(MACRO_PROFILE)

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

        raw_prediction = ocr.read()
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

        if use_macro:
            macro_count = 0
            time.sleep(4)
            if macro.is_screen_condition_true():
                while True:
                    if macro_count > MAX_MACRO_COUNT:
                        print("Used macro too many times. State unknown. Quitting...")
                        client.close()
                        exit()
                    if args.use_refresh_macro:
                        macro.execute_macro(REFRESH_BET_MACRO)
                        time.sleep(10)
                    if macro.is_screen_condition_true():
                        if args.use_signin_macro:
                            macro.execute_macro(RESIGNIN_MACRO)
                            if not macro.is_screen_condition_true():
                                break
                            macro_count += 1
                    else:
                        break

main()
