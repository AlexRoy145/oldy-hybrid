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

GREEN_MACRO_DELAY = 0.025 # IN SECONDS

class CRMServer:

    def __init__(self, server_ip, server_port):
        self.server_ip = server_ip
        self.server_port = server_port

        self.clickbot = Clickbot(PROFILE_DIR)
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
            self.ocr.set_ball_detection_zone()
            self.ocr.save_profile(OCR_PROFILE) 


        self.server = Server(self.server_ip, self.server_port)
        self.server.accept_connections()

   
    def run(self):
        self.app_thread = threading.Thread(target=self.start_app, args=())
        self.app_thread.daemon = True
        self.app_thread.start()

        while True: 
            choice = input(f"""
IMPORTANT: The following commands can only be run if the direction detection loop is stopped: D, DW, DT, T
Q: Quit the direction detection loop.
R: Run the direction detection loop.
E: Set end difference.
B: Start ball timings.
V: Change VPS.
SS: Show samples.
CS: Clear sample by sample number.
AS: Add sample manually.
DW: Change wheel detection zone (DO THIS BEFORE BALL DETECTION).
DB: Change ball detection zone.
SJ: Show jump values.
J: Change jump values.
SC: Show connected clients.
K: Execute signin macro on all machines.
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
            elif choice == "e":
                while True:
                    try:
                        self.ocr.ball.end_difference = int(input("Enter the new end difference: "))
                        break
                    except ValueError:
                        print("Invalid value.")
                continue    
            elif choice == "b":
                self.ocr.start_ball_timings = True
                continue
            elif choice == "v":
                while True:
                    try:
                        self.ocr.ball.vps = int(input("Enter the new VPS: "))
                        break
                    except ValueError:
                        print("Invalid value.")
                continue    
            elif choice == "ss":
                for i, sample in enumerate(self.ocr.ball.samples):
                    print(f"Sample #{i}: {sample}")
                continue
            elif choice == "cs":
                for i, sample in enumerate(self.ocr.ball.samples):
                    print(f"Sample #{i}: {sample}")
                while True:
                    try:
                        sample_idx = int(input("Enter sample number to delete: "))
                        break
                    except ValueError:
                        print("Invalid value.")
                try:
                    del self.ocr.ball.samples[sample_idx]
                except IndexError:
                    print("That sample doesn't exist.")
                continue
            elif choice == "as":
                sample_to_add = []
                print("Begin entering the sample, pressing ENTER after each rev. Press CTRL+C when you're done.")
                while True:
                    try:
                        rev = int(input("Enter rev: "))
                        sample_to_add.append(rev)
                    except KeyboardInterrupt:
                        break

                self.ocr.ball.update_sample(sample_to_add)
                continue
            elif choice == "dw":
                self.ocr.set_wheel_detection_zone()
                self.ocr.save_profile(OCR_PROFILE)
                continue
            elif choice == "db":
                self.ocr.set_ball_detection_zone()
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
            elif choice == "k":
                yesorno = input(f"Are you sure you want to execute signin macro on all machines? (Y/N): ").lower()
                if yesorno == "y":
                    msg = Message()
                    msg.do_signin = True
                    self.server.send_message(msg)
                continue
            else:
                continue
    

    def start_app(self):
        k = Controller()
        while self.is_running:
            msg = Message()

            raw_prediction = -1
            direction = ""
            self.ocr.quit = False
            self.ocr.raw = -1
            self.ocr.direction = ""

            print("Waiting for change in direction...")
            ocr_thread = threading.Thread(target=self.ocr.start_capture, args=())
            ocr_thread.daemon = True
            ocr_thread.start()

            while self.is_running:
                time.sleep(.05)
                if self.ocr.quit:
                    break
                elif self.ocr.raw != -1:
                    raw_prediction = self.ocr.raw
                    direction = self.ocr.direction
                    break

            if raw_prediction == -1 or direction == "":
                continue

            print(f"Direction: {direction}, Raw Prediction: {raw_prediction}")
            if not direction:
                continue
            direction = direction[0]

            tuned_predictions = self.clickbot.get_tuned_from_raw(direction, raw_prediction)
            print(f"TUNED PREDICTIONS: {tuned_predictions}")

            msg.direction = direction
            msg.raw_prediction = raw_prediction
            msg.tuned_predictions = tuned_predictions
            self.server.send_message(msg)
            
            ocr_thread.join()

            
def main():
    parser = argparse.ArgumentParser(description="Run the server betting program.")
    parser.add_argument("server_ip", type=str, help="The server's IP address.")
    parser.add_argument("server_port", type=int, help="The server's port.")

    args = parser.parse_args()
    app = CRMServer(args.server_ip, args.server_port)
    try:
        app.run()
    except KeyboardInterrupt:
        exit()

def job(ocr_instance, msg_queue):
    ocr_instance.start_capture(msg_queue)
    return
    

main()
