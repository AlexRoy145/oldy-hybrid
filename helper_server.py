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
        self.test_mode = False

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
T: Toggle test mode. Test mode will let detection run, but WON'T send commands to clients.
SS: Show samples.
G: Graph samples.
CS: Clear sample by sample number.
AS: Add sample manually.
CM: Change max samples for ball sample.
CA: Change rotor acceleration.
RA: Run rotor acceleration setting loop. QUIT NORMAL DETECTION FIRST USING Q.
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
                print(f"Current end difference: {self.ocr.ball_sample.end_difference}")
                while True:
                    try:
                        self.ocr.ball_sample.end_difference = int(input("Enter the new end difference: "))
                        self.ocr.save_profile(OCR_PROFILE)
                        break
                    except ValueError:
                        print("Invalid value.")
                continue    
            elif choice == "b":
                self.ocr.start_ball_timings = True
                continue
            elif choice == "v":
                print(f"Current VPS: {self.ocr.ball_sample.vps}")
                while True:
                    try:
                        vps = int(input("Enter the new VPS: "))
                        self.ocr.change_vps(vps)
                        break
                    except ValueError:
                        print("Invalid value.")
                continue    
            elif choice == "t":
                if self.test_mode:
                    print("Turning test mode OFF.")
                    self.test_mode = False
                else:
                    print("Turning test mode ON.")
                    self.test_mode = True
                continue
            elif choice == "ss":
                self.ocr.show_ball_samples()
                continue
            elif choice == "g":
                self.ocr.graph_samples()
                continue
            elif choice == "cs":
                for i, sample in enumerate(self.ocr.ball_sample.samples):
                    print(f"Sample #{i}: {sample}")
                while True:
                    try:
                        sample_idx = int(input("Enter sample number to delete: "))
                        self.ocr.delete_ball_sample(sample_idx)
                        break
                    except ValueError:
                        print("Invalid value.")

                continue
            elif choice == "as":
                sample_to_add = []
                new_sample = input("Enter the sample as a comma delimited list of numbers: ")
                new_sample = new_sample.replace(" ", "").split(",")
                if len(new_sample) > 0:
                    for rev in new_sample:
                        try:
                            sample_to_add.append(int(rev))
                        except ValueError:
                            print("Invalid value in sample.")
                            break

                    self.ocr.add_ball_sample(sample_to_add)
                else:
                    print("Invalid sample.")

                continue
            elif choice == "cm":
                print(f"Current max samples: {self.ocr.ball_sample.max_samples}")
                try:
                    new_max_samples = int(input("Enter the new max samples: "))
                    self.ocr.change_max_samples(new_max_samples)
                except ValueError:
                    print("Invalid value.")
                continue
            elif choice == "ca":
                print(f"Current rotor acceleration: {self.ocr.rotor_acceleration}")
                self.ocr.rotor_acceleration = float(input("Enter the new rotor acceleration: "))
                self.ocr.save_profile(OCR_PROFILE)
                continue
            elif choice == "ra":
                self.accel_thread = threading.Thread(target=self.get_rotor_accel, args=())
                self.accel_thread.daemon = True
                self.accel_thread.start()
                print("Rotor acceleration thread started.")
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

    def get_rotor_accel(self):
        ocr_thread = threading.Thread(target=self.ocr.capture_rotor_acceleration, args=())
        ocr_thread.daemon = True
        ocr_thread.start()
        ocr_thread.join()
    

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

            if not self.test_mode:
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

    
if __name__ == "__main__":
    main()
