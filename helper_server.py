import autoit
import sys
import select
import time
import threading
import pickle
import msvcrt
from collections import deque
from pynput.keyboard import Key, Controller
from pytessy import PyTessy
from clickbot import Clickbot
from message import Message
from server import Server
from ocr import OCR
from macro import Macro
from scatter import Scatter
from util import SpinData

PROFILE_DIR = "../../../Documents/crm_saved_profiles"
CLICKBOT_PROFILE = "profile.dat"
ROTOR_ISOLATION_PROFILE = "rotor_isolation.json"
OCR_PROFILE = "ocr.dat"

SCATTER_DATA_FILE = "scatter.dat"
CSV_SCATTER = "scatter.csv"


REFRESH_MACRO_DIR = "refresh_macros"
SIGNIN_MACRO_DIR = "signin_macros"

MAX_MACRO_COUNT = 3

GREEN_MACRO_DELAY = 0.025 # IN SECONDS

IP = "0.0.0.0"
PORT = 34453

MOST_RECENT_SPIN_COUNT = 10

class CRMServer:

    def __init__(self, server_ip, server_port):
        self.server_ip = server_ip
        self.server_port = server_port

        self.clickbot = Clickbot(PROFILE_DIR)
        self.is_running = True 
        self.test_mode = True
        self.databot_mode = False

        self.scatter = Scatter(PROFILE_DIR, CSV_SCATTER)
        self.scatter.load_profile(SCATTER_DATA_FILE)
        self.scatter.save_profile(SCATTER_DATA_FILE)

        # raw adjustment
        self.raw_adjustment = 0

        if not self.clickbot.load_profile(CLICKBOT_PROFILE):
            print("Could not find clickbot data. Setting up from scratch.")
            self.clickbot.set_clicks()
            self.clickbot.set_jump_values()
            self.clickbot.save_profile(CLICKBOT_PROFILE)

        self.clickbot.load_rotor_isolation_profile(ROTOR_ISOLATION_PROFILE)

        self.ocr = OCR(PROFILE_DIR)
        if not self.ocr.load_profile(OCR_PROFILE):
            print("Could not find ocr data. Setting up from scratch.")
            self.ocr.set_wheel_detection_zone()
            self.ocr.set_ball_detection_zone()
            self.ocr.set_ball_fall_detection_zone()
            self.ocr.set_sample_detection_zone()
            self.ocr.save_profile(OCR_PROFILE) 


        self.server = Server(self.server_ip, self.server_port)
        self.server.accept_connections()

   
    def run(self):
        self.app_thread = threading.Thread(target=self.start_app, args=())
        self.app_thread.daemon = True
        self.app_thread.start()

        while True: 
            menu = f"""
IMPORTANT: The following commands can only be run if the direction detection loop is stopped: D, DW, DT, T
Q: Quit the direction detection loop.
R: Run the direction detection loop.
B: Start ball timings.
V: Change VPS.
T: Toggle test mode. Test mode will let detection run, but WON'T send commands to clients.
D: Toggle data bot mode. QUIT DETECTION FIRST BEFORE TOGGLING.

K: Type out the most recent ball timings to the anydesk window. Delay is 2 seconds, so once you hit enter, you have 2 seconds before it starts typing.

MR: Display most recent spins.
CMR: Clear most recent spins

CR: Change raw adjustment value.

SS: Show samples.
G: Graph samples.
GD: Graph data.
CS: Clear sample by sample number.
AS: Add sample manually.
OS: Scan sample into hybrid.
CM: Change max samples for ball sample.
CA: Change rotor acceleration.
CE: Change ellipse angle.
CRT: Change rev tolerance.

DW: Change wheel detection zone (DO THIS BEFORE BALL DETECTION).
DB: Change ball detection zone.
DF: Change ball fall detection zone.
DN: Change winning number detection zone.
DS: Change sample detection zone.

SJ: Show default jump values.
J: Change default jump values.
SB: Show ball rev ranges for ball rev isolation.
JB: Change ball rev ranges for ball rev isolation.
SC: Show connected clients.
K: Execute signin macro on all machines.
"""
            choice = input("Enter your choice (HELP to show menu): ").lower()
            if choice == "help":
                print(menu)
                continue
            elif choice == "q":   
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
            elif choice == "w":
                winning = input("Enter the winning number: ")
                if self.direction == "anticlockwise":
                    new_direction = "acw"
                else:
                    new_direction = "cw"
                self.scatter.add_data(new_direction, self.raw, winning, self.rotor_speed)
                self.scatter.save_profile(SCATTER_DATA_FILE)
                continue
            elif choice == "e":
                '''
                print(f"Current end difference ANTI: {self.ocr.ball_sample.end_difference_anti}")
                print(f"Current end difference CLOCK: {self.ocr.ball_sample.end_difference_clock}")
                '''
                print(f"Current end difference: {self.ocr.ball_sample.end_difference}")

                while True:
                    try:
                        #direction = input("Enter the direction (anti or clock): ")
                        end_difference = int(input("Enter the new end difference: "))
                        '''
                        if "a" in direction:
                            self.ocr.ball_sample.end_difference_anti = end_difference
                        else:
                            self.ocr.ball_sample.end_difference_clock = end_difference
                        '''
                        self.ocr.ball_sample.end_difference = end_difference

                        self.ocr.save_profile(OCR_PROFILE)
                        break
                    except ValueError:
                        print("Invalid value.")
                continue    
            elif choice == "b":
                self.ocr.start_ball_timings = True
                continue
            elif choice == "v":
                '''
                print(f"Current VPS ANTI: {self.ocr.ball_sample.vps_anti}")
                print(f"Current VPS CLOCK: {self.ocr.ball_sample.vps_clock}")
                '''
                print(f"Current VPS: {self.ocr.ball_sample.vps}")
                while True:
                    try:
                        #direction = input("Enter the direction (anti or clock): ")
                        vps = int(input("Enter the new VPS: "))
                        #self.ocr.change_vps(vps, direction)
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
            elif choice == "d":
                if self.databot_mode:
                    print("Turning databot mode OFF.")
                    self.databot_mode = False
                else:
                    print("Turning databot mode ON.")
                    self.databot_mode = True
                continue
            elif choice == "k":
                if self.ocr.most_recent_timings:
                    print(f"You have 2 seconds to click into the anydesk window before typing happens.")
                    time.sleep(2)
                    for timing in self.ocr.most_recent_timings:
                        string = str(timing) + "{ENTER}"
                        autoit.send(string)
                continue
            elif choice == "mr":
                # NEWEST SPINS ARE ON THE RIGHT OF THE DEQUE, SO REVERSE IT BEFORE FILTERING
                anti_spins = filter(lambda x : x.direction == "a", list(self.ocr.most_recent_spin_data)[::-1])
                clock_spins = filter(lambda x : x.direction == "c", list(self.ocr.most_recent_spin_data)[::-1])

                print("\nMost recent ANTICLOCKWISE spin data (newest spins listed first):")
                for anti_spin in anti_spins:
                    print(f"Diamond hit: {anti_spin.diamond_hit}, Ball revs: {anti_spin.ball_revs}, Rotor speed: {anti_spin.rotor_speed}")

                print("\nMost recent CLOCKWISE spin data (newest spins listed first):")
                for clock_spin in clock_spins:
                    print(f"Diamond hit: {clock_spin.diamond_hit}, Ball revs: {clock_spin.ball_revs}, Rotor speed: {clock_spin.rotor_speed}")

                continue    
            elif choice == "cmr":
                print("Cleared most recent spin data")
                self.ocr.most_recent_spin_data = deque(maxlen=MOST_RECENT_SPIN_COUNT)
                continue
            elif choice == "cr":
                print(f"Current raw adjustment: {self.raw_adjustment}")
                self.raw_adjustment = int(input("Input the new raw adjustment (example, +4 to shift the raw clockwise 4 pockets, -4 to shift the raw anti 4 pockets): "))
                continue
            elif choice == "ss":
                '''
                direction = input("Enter the direction (anti or clock): ")
                self.ocr.show_ball_samples(direction)
                '''
                self.ocr.show_ball_samples()
                continue
            elif choice == "g":
                '''
                direction = input("Enter the direction (anti or clock): ")
                self.ocr.graph_samples(direction)
                '''
                self.ocr.graph_samples()
                continue
            elif choice == "gd":
                direction_data = input("Enter the direction (ex: acw or cw): ")
                rotor_speed_range = input("Enter the rotor speed range (ex: 4000-5000): ")
                fall_point_range = input("Enter the fall point range (ex: 340-20, or 270-300): ")
                self.scatter.graph(direction=direction_data, rotor_speed_range=rotor_speed_range, fall_point_range=fall_point_range)
                continue
            elif choice == "cs":
                '''
                direction = input("Enter the direction (anti or clock): ")
                if "a" in direction:
                    samples = self.ocr.ball_sample.samples_anti
                else:
                    samples = self.ocr.ball_sample.samples_clock
                '''
                samples = self.ocr.ball_sample.samples

                for i, sample in enumerate(samples):
                    print(f"Sample #{i}: {sample}")
                while True:
                    try:
                        sample_idx = int(input("Enter sample number to delete: "))
                        #self.ocr.delete_ball_sample(sample_idx, direction)
                        self.ocr.delete_ball_sample(sample_idx)
                        break
                    except ValueError:
                        print("Invalid value.")

                continue
            elif choice == "as":
                #direction = input("Enter the direction (anti or clock): ")
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

                    #self.ocr.add_ball_sample(sample_to_add, direction)
                    self.ocr.add_ball_sample(sample_to_add)
                else:
                    print("Invalid sample.")

                continue
            elif choice == "os":
                self.ocr.scan_sample()
                continue
            elif choice == "cm":
                '''
                print(f"Current max samples ANTI: {self.ocr.ball_sample.max_samples_anti}")
                print(f"Current max samples CLOCK: {self.ocr.ball_sample.max_samples_clock}")
                '''
                print(f"Current max samples: {self.ocr.ball_sample.max_samples}")

                try:
                    #direction = input("Enter the direction (anti or clock): ")
                    new_max_samples = int(input("Enter the new max samples: "))
                    #self.ocr.change_max_samples(new_max_samples, direction)
                    self.ocr.change_max_samples(new_max_samples)
                except ValueError:
                    print("Invalid value.")
                continue
            elif choice == "ct":
                print(f"Current target time: {self.ocr.ball_sample.target_time}")
                self.ocr.ball_sample.target_time = int(input("Enter the new target time: "))
                continue
            elif choice == "ca":
                print(f"Current rotor acceleration: {self.ocr.rotor_acceleration}")
                self.ocr.rotor_acceleration = float(input("Enter the new rotor acceleration: "))
                self.ocr.save_profile(OCR_PROFILE)
                continue
            elif choice == "ce":
                print(f"Current ellipse angle: {self.ocr.rotor_angle_ellipse}")
                self.ocr.rotor_angle_ellipse = int(input("Enter the new rotor angle ellipse: "))
                self.ocr.save_profile(OCR_PROFILE)
                continue
            elif choice == "crt":
                '''
                direction = input("Enter the direction (anti or clock): ")
                print(f"Current rev tolerance ANTI: {self.ocr.ball_sample.rev_tolerance_anti}")
                print(f"Current rev tolerance CLOCK: {self.ocr.ball_sample.rev_tolerance_clock}")
                '''
                print(f"Current rev tolerance: {self.ocr.ball_sample.rev_tolerance}")
                
                rev_tolerance = int(input("Enter the new ball sample rev tolerance: "))
                '''
                if "a" in direction:
                    self.ocr.ball_sample.rev_tolerance_anti = rev_tolerance
                else:
                    self.ocr.ball_sample.rev_tolerance_clock = rev_tolerance
                '''
                self.ocr.ball_sample.rev_tolerance = rev_tolerance
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
            elif choice == "df":
                self.ocr.set_ball_fall_detection_zone()
                self.ocr.save_profile(OCR_PROFILE)
                continue
            elif choice == "dn":
                self.ocr.set_winning_number_detection_zone()
                self.ocr.save_profile(OCR_PROFILE)
                continue
            elif choice == "ds":
                self.ocr.set_sample_detection_zone()
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
            elif choice == "sb":
                print(f"Anticlockwise ball revs: {self.clickbot.ball_revs_anti}")
                print(f"Clockwise ball revs: {self.clickbot.ball_revs_clock}")
                continue
            elif choice == "jb":
                self.clickbot.set_ball_revs()
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
            self.ocr.databot_mode = self.databot_mode

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
                    rotor_speed = int(self.ocr.rotor_speed)
                    self.raw = raw_prediction
                    self.direction = direction
                    self.rotor_speed = rotor_speed
                    if self.databot_mode:
                        fall_zone = self.ocr.fall_zone
                        winning_number = self.ocr.winning_number
                        ball_revs = self.ocr.ball_revs
                    break

            if raw_prediction == -1 or direction == "":
                continue

            print(f"Direction: {direction}")
            print(f"Rotor Speed: {rotor_speed}")
            print(f"Raw: {raw_prediction}")
            if self.databot_mode:
                print(f"Winning Number: {winning_number}")
                print(f"Fall Zone: {fall_zone}")
                print(f"Ball Revs: {ball_revs}")
                if self.direction == "anticlockwise":
                    new_direction = "acw"
                else:
                    new_direction = "cw"
                self.scatter.add_data(direction=new_direction, raw=self.raw, winning=winning_number, rotor_speed=rotor_speed, fall_zone=fall_zone, ball_revs=ball_revs)
                self.scatter.save_profile(SCATTER_DATA_FILE)
                self.add_data_to_most_recent(direction[0], fall_zone, ball_revs, rotor_speed)
                ocr_thread.join()
                continue

            if not direction:
                continue
            direction = direction[0]

            # do raw adjustment here
            adjusted_raw = self.clickbot.get_adjusted_raw(raw_prediction, self.raw_adjustment)
            print(f"Adjusted raw is: {adjusted_raw}")

            #tuned_predictions = self.clickbot.get_tuned_from_raw_using_rotor_isolation(direction, rotor_speed, raw_prediction)
            tuned_predictions = self.clickbot.get_tuned_from_raw(direction, adjusted_raw)
            print(f"TUNED PREDICTIONS: {tuned_predictions}")

            if not self.test_mode and not self.databot_mode:
                msg.direction = direction
                msg.raw_prediction = adjusted_raw
                msg.tuned_predictions = tuned_predictions
                self.server.send_message(msg)

            if not self.databot_mode:
                # predictions have been sent, now wait for the fall zone and ball rev info to come back if NOT in databot mode
                while self.is_running:
                    time.sleep(.05)
                    if self.ocr.quit:
                        break
                    elif self.ocr.fall_zone != -1:
                        self.add_data_to_most_recent(direction, self.ocr.fall_zone, self.ocr.ball_revs, rotor_speed)
                        self.ocr.quit = True
                        break

            ocr_thread.join()

    def add_data_to_most_recent(self, direction, fall_zone, ball_revs, rotor_speed):
        datapoint = SpinData(direction, self.scatter.convert_fall_point_to_diamond_hit(fall_zone, direction), ball_revs, rotor_speed)
        self.ocr.most_recent_spin_data.append(datapoint)
        print("Added spin data to most recent spins list.")

            
def main():
    app = CRMServer(IP, PORT)
    try:
        app.run()
    except KeyboardInterrupt:
        exit()

    
if __name__ == "__main__":
    main()
