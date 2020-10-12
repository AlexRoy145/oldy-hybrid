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

REFRESH_BET_MACRO = "Refresh page if kicked for late bets"
RESIGNIN_MACRO = "Resign into the website and pull up betting interface"

MAX_MACRO_COUNT = 3

def main():

    parser = argparse.ArgumentParser(description="Run the server betting program.")
    parser.add_argument("server_ip", type=str, help="The server's IP address.")
    parser.add_argument("server_port", type=int, help="The server's port.")
    parser.add_argument("--no-bet", action="store_true")
    parser.add_argument("--use-green-swap", action="store_true")
    parser.add_argument("--use-refresh-macro", action="store_true")
    parser.add_argument("--use-signin-macro", action="store_true")

    args = parser.parse_args()

    use_macro = args.use_refresh_macro or args.use_signin_macro

    clickbot = Clickbot(PROFILE_DIR)
    if not clickbot.load_profile(CLICKBOT_PROFILE):
        print("Could not find profile. Setting up from scratch.")
        clickbot.set_clicks()
        clickbot.set_jump_values()
        clickbot.set_detection_zone("raw prediction number")
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

    ocr = OCR(clickbot.detection_zone)
      
    while True:
        msg = Message()
        print("""\nA: Anticlockwise, click for yourself and send click command to clients.
C: Clockwise, click for yourself and send click command to clients.
D: Change the detection zone.
T: Test mode (do NOT make clicks, but send TEST send commands to clients to test connectivity).
SJ: Show jump values.
J: Change jump values.
SC: Show connected clients.
AM: Anticlockwise Me Only, click for yourself and DON'T send click commands to clients.
CM: Clockwise Me Only, click for yourself and DON'T send click commands to clients.\n""")
        direction = input("Enter menu option: ").lower()
        if not direction:
            continue
        elif direction == "d":
            clickbot.set_detection_zone()
            ocr.detection_zone = clickbot.detection_zone
            clickbot.save_profile(CLICKBOT_PROFILE)
            continue
        elif direction == "sc":
            for addr in server.clients.keys():
                print(addr)
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
            msg.test_mode = True
        elif not "a" in direction and not "c" in direction:
            print("Invalid menu option.")
            continue
        if args.use_green_swap:
            while True:
                try:
                    green_swap = int(input("Enter 1: 3-9 green, 2: 12-6 green, 3: 1.5-7.5 green, 4: 4.5-10.5 green : "))
                    if green_swap < 1 or green_swap > 4:
                        print("Invalid number.")
                        continue
                    else:
                        break
                except ValueError:
                    print("Invalid number.")
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
        if raw_prediction != None:
            raw_prediction = raw_prediction.strip()
        print(f"RAW PREDICTION: {raw_prediction}")
            
        try:
            raw_prediction = int(raw_prediction)
        except (ValueError, TypeError) as e:
            print("ERROR: Incorrectly detected raw prediction, could not click.")
            msg.error = True
            if not "m" in direction:
                server.send_message(msg)
            continue

        if raw_prediction < 0 or raw_prediction > 36:
            print("ERROR: Incorrectly detected raw prediction, could not click.")
            msg.error = True
            if not "m" in direction:
                server.send_message(msg)
            continue

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
