import argparse
import time
import pickle
import msvcrt
from pytessy import PyTessy
from clickbot import Clickbot
from message import Message
from server import Server
from ocr import OCR
from macro import Macro

PROFILE_DIR = "../../../Documents/crm_saved_profiles"
CLICKBOT_PROFILE = "profile.dat"
MACRO_PROFILE = "macro.dat"
OCR_PROFILE = "ocr.dat"

REFRESH_BET_MACRO = "Refresh page if kicked for late bets"
RESIGNIN_MACRO = "Resign into the website and pull up betting interface"

MAX_MACRO_COUNT = 3

def main():

    parser = argparse.ArgumentParser(description="Run the server betting program.")
    parser.add_argument("server_ip", type=str, help="The server's IP address.")
    parser.add_argument("server_port", type=int, help="The server's port.")
    parser.add_argument("--change-scatter", action="store_true")
    parser.add_argument("--no-bet", action="store_true")
    parser.add_argument("--use-green-swap", action="store_true")
    parser.add_argument("--use-refresh-macro", action="store_true")
    parser.add_argument("--use-signin-macro", action="store_true")

    args = parser.parse_args()

    use_macro = args.use_refresh_macro or args.use_signin_macro

    clickbot = Clickbot(PROFILE_DIR)

    if not clickbot.load_profile(CLICKBOT_PROFILE):
        print("Could not find clickbot data. Setting up from scratch.")
        clickbot.set_clicks()
        clickbot.set_jump_values()
        clickbot.save_profile(CLICKBOT_PROFILE)

    ocr = OCR(PROFILE_DIR)
    if not ocr.load_profile(OCR_PROFILE):
        print("Could not find ocr data. Setting up from scratch.")
        ocr.set_wheel_detection_zone()
        ocr.set_raw_detection_zone()
        ocr.save_profile(OCR_PROFILE) 

    if args.change_scatter:
        clickbot.set_jump_values()
        clickbot.save_profile(CLICKBOT_PROFILE)
    
    if use_macro:
        macro = Macro(PROFILE_DIR)
        if not macro.load_profile(MACRO_PROFILE):
            macro.set_screen_condition()
            if args.use_refresh_macro:
                macro.record_macro(REFRESH_BET_MACRO)
            if args.use_signin_macro:
                macro.record_macro(RESIGNIN_MACRO)
            macro.save_profile(MACRO_PROFILE)


    server = Server(args.server_ip, args.server_port)
    server.accept_connections()

    while True:
        msg = Message()

        print("Waiting for change in direction...")
        direction, raw_prediction = ocr.start_capture()
        print(f"Direction: {direction}, Raw Prediction: {raw_prediction}")
        if not direction or not raw_prediction:
            continue
        direction = direction[0]

        tuned_predictions = clickbot.get_tuned_from_raw(direction, raw_prediction)
        print(f"TUNED PREDICTIONS: {tuned_predictions}")

        if args.use_green_swap:
            raw_prediction = clickbot.adjust_raw_for_green_swap(raw_prediction, green_swap)
            tuned_predictions = clickbot.get_tuned_from_raw(direction, raw_prediction)
            print(f"GREEN ADJUSTED RAW PREDICTION: {raw_prediction}")
            print(f"GREEN ADJUSTED TUNED PREDICTIONS: {tuned_predictions}")

        if direction != "t" and not args.no_bet:
            clickbot.make_clicks_given_tuned(direction, tuned_predictions)
        
        if not "m" in direction:
            msg.direction = direction
            msg.raw_prediction = raw_prediction
            msg.tuned_predictions = tuned_predictions
            server.send_message(msg)

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
