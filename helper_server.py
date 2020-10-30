import argparse
import sys
import select
import time
import threading
import pickle
import msvcrt
from pynput.keyboard import Key, Controller
from pytessy import PyTessy
from clickbot import Clickbot
from message import Message
from server import Server
from ocr import OCR
from macro import Macro

PROFILE_DIR = "../../../Documents/crm_saved_profiles"
CLICKBOT_PROFILE = "profile.dat"
OCR_PROFILE = "ocr.dat"

REFRESH_MACRO_DIR = "refresh_macros"
SIGNIN_MACRO_DIR = "signin_macros"

MAX_MACRO_COUNT = 3

class CRMServer:

    def __init__(self, server_ip, server_port, use_green_swap, no_bet, site_name):
        self.server_ip = server_ip
        self.server_port = server_port
        self.use_green_swap = use_green_swap
        self.no_bet = no_bet
        self.site = site_name

        self.clickbot = Clickbot(PROFILE_DIR)
        self.green_swap = 1
        self.is_running = True 

        if not self.clickbot.load_profile(CLICKBOT_PROFILE):
            print("Could not find clickbot data. Setting up from scratch.")
            self.clickbot.set_clicks()
            self.clickbot.set_jump_values()
            self.clickbot.save_profile(CLICKBOT_PROFILE)

        self.ocr = OCR(PROFILE_DIR)
        if not self.ocr.load_profile(OCR_PROFILE):
            print("Could not find ocr data. Setting up from scratch.")
            self.ocr.set_wheel_detection_zone()
            self.ocr.set_raw_detection_zone()
            self.ocr.set_tuned_detection_zone()
            self.ocr.save_profile(OCR_PROFILE) 

        if not self.no_bet:
            self.refresh_macro_name = f"refresh_{self.site}.dat"
            self.refresh_macro = Macro(REFRESH_MACRO_DIR)
            if not self.refresh_macro.load_profile(self.refresh_macro_name):
                self.refresh_macro.set_screen_condition()
                self.refresh_macro.save_profile(self.refresh_macro_name)

        if self.site:
            self.signin_macro_name = f"signin_{self.site}.dat"
            self.signin_macro = Macro(SIGNIN_MACRO_DIR)
            if not self.signin_macro.load_profile(self.signin_macro_name):
                self.signin_macro.set_screen_condition()
                self.signin_macro.record_macro()
                self.signin_macro.save_profile(self.signin_macro_name)


        self.server = Server(self.server_ip, self.server_port)
        self.server.accept_connections()

   
    def run(self):
        self.app_thread = threading.Thread(target=self.start_app, args=())
        self.app_thread.daemon = True
        self.app_thread.start()

        while True: 
            choice = input(f"""
IMPORTANT: The following commands can only be run if the direction detection loop is stopped: D, DW, T
Q: Quit the direction detection loop.
R: Run the direction detection loop.
D: Change raw detection zone.
DW: Change wheel detection zone.
DT: Change tuned detection zone.
SJ: Show jump values.
J: Change jump values.
SC: Show connected clients.
T: Test raw prediction reading and send test message to clients.
1, 2, 3 or 4: Choices for green swap.
Enter your choice: """).lower()
            if choice == "q":   
                if not self.is_running and not self.ocr.is_running:
                    print("Direction detection already stopped.")
                    continue
                self.ocr.is_running = False
                self.is_running = False
                print("Waiting for direction detection thread to stop...")
                self.app_thread.join()
                print("Direction detection thread stopped.")
                continue
            elif choice == "r":
                if self.is_running and self.ocr.is_running:
                    print("Direction detection already running.")
                    continue
                self.ocr.is_running = True
                self.is_running = True
                self.app_thread = threading.Thread(target=self.start_app, args=())
                self.app_thread.daemon = True
                self.app_thread.start()
                print("Direction detection started.")
                continue
            if choice == "d":
                self.ocr.set_raw_detection_zone()
                self.ocr.save_profile(OCR_PROFILE)
                continue
            elif choice == "dw":
                self.ocr.set_wheel_detection_zone()
                self.ocr.save_profile(OCR_PROFILE)
                continue
            elif choice == "dt":
                self.ocr.set_tuned_detection_zone()
                self.ocr.save_profile(OCR_PROFILE)
                continue
            elif choice == "sj":
                print(f"Anticlockwise jump values: {self.clickbot.jump_anti}")
                print(f"Clockwise jump values: {self.clickbot.jump_clock}")
                continue
            elif choice == "j":
                self.clickbot.set_jump_values()
                self.clickbot.save_profile(CLICKBOT_PROFILE)
                continue
            elif choice == "sc":
                for addr in self.server.clients.keys():
                    print(addr)
                continue
            elif choice == "t":
                msg = Message()
                msg.test_mode = True
                raw_prediction = self.ocr.read()
                tuned_prediction = self.ocr.read(zone=self.ocr.tuned_detection_zone)
                if self.ocr.is_valid_prediction(raw_prediction):
                    raw_prediction = int(raw_prediction.strip())
                    tuned = self.clickbot.get_tuned_from_raw("a", raw_prediction)
                    msg.raw_prediction = raw_prediction
                    msg.tuned_predictions = tuned
                else:
                    msg.error = True

                self.server.send_message(msg)
                print(f"OCR thinks raw is: {raw_prediction}")
                print(f"OCR thinks tuned is: {tuned_prediction}")
                continue
            elif choice == "1":
                # native 3 to 9
                self.green_swap = 1
                continue
            elif choice == "2":
                # 12 to 6
                self.green_swap = 2
                continue
            elif choice == "3":
                # 1.5 to 7.5
                self.green_swap = 3
                continue
            elif choice == "4":
                # 4.5 to 10.5
                self.green_swap = 4
                continue
            else:
                continue
    

    def start_app(self):
        k = Controller()
        while self.is_running:
            msg = Message()

            print("Waiting for change in direction...")
            stuff = self.ocr.start_capture()
            if stuff:
                direction, raw_prediction = stuff
            else:
                continue

            print(f"Direction: {direction}, Raw Prediction: {raw_prediction}")
            if not direction:
                continue
            direction = direction[0]

            tuned_predictions = self.clickbot.get_tuned_from_raw(direction, raw_prediction)
            print(f"TUNED PREDICTIONS: {tuned_predictions}")

            if self.use_green_swap:
                raw_prediction = self.clickbot.adjust_raw_for_green_swap(raw_prediction, self.green_swap)
                tuned_predictions = self.clickbot.get_tuned_from_raw(direction, raw_prediction)
                print(f"GREEN ADJUSTED RAW PREDICTION: {raw_prediction}")
                print(f"GREEN ADJUSTED TUNED PREDICTIONS: {tuned_predictions}")

            if direction != "t" and not self.no_bet:
                self.clickbot.make_clicks_given_tuned(direction, tuned_predictions)
            
            if not "m" in direction:
                msg.direction = direction
                msg.raw_prediction = raw_prediction
                msg.tuned_predictions = tuned_predictions
                self.server.send_message(msg)

            if not self.no_bet:
                macro_count = 0
                time.sleep(4)
                if self.refresh_macro.is_screen_condition_true():
                    while True:
                        if macro_count > MAX_MACRO_COUNT:
                            print("Used macro too many times. State unknown. Quitting...")
                            exit()
                        k.press(Key.f5)
                        k.release(Key.f5)
                        time.sleep(5)
                        macro_count += 1
                        if self.refresh_macro.is_screen_condition_true():
                            if self.site:
                                self.signin_macro.execute_macro()
                                if not self.signin_macro.is_screen_condition_true():
                                    break
                                macro_count += 1
                        else:
                            break


def main():
    parser = argparse.ArgumentParser(description="Run the server betting program.")
    parser.add_argument("server_ip", type=str, help="The server's IP address.")
    parser.add_argument("server_port", type=int, help="The server's port.")
    parser.add_argument("--no-bet", action="store_true")
    parser.add_argument("--use-green-swap", action="store_true")
    parser.add_argument("--site_name", type=str, help="The casino site NAME (do NOT include www or .com/.ag/.eu) to use with the site macro")

    args = parser.parse_args()
    app = CRMServer(args.server_ip, args.server_port, args.use_green_swap, args.no_bet, args.site_name)
    try:
        app.run()
    except KeyboardInterrupt:
        exit()

main()
