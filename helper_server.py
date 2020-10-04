import argparse
import time
import pickle
import msvcrt
from pytessy import PyTessy
from clickbot import Clickbot
from message import Message
from server import Server
from ocr import OCR

CLICKBOT_PROFILE = "profile.dat"

def main():

    parser = argparse.ArgumentParser(description="Run the server betting program.")
    parser.add_argument("server_ip", type=str, help="The server's IP address.")
    parser.add_argument("server_port", type=int, help="The server's port.")
    parser.add_argument("--use-green-swap", action="store_true")
    args = parser.parse_args()

    clickbot = Clickbot()
    if not clickbot.load_profile(CLICKBOT_PROFILE):
        print("Could not find profile. Setting up from scratch.")
        clickbot.set_clicks()
        clickbot.set_jump_values()
        clickbot.set_detection_zone()
        clickbot.save_profile(CLICKBOT_PROFILE)

    server = Server(args.server_ip, args.server_port)
    server.accept_new_connections()

    ocr = OCR(clickbot.detection_zone)
      
    while True:
        msg = Message()
        print("""\nA: Anticlockwise, click for yourself and send click command to clients.
C: Clockwise, click for yourself and send click command to clients.
D: Change the detection zone.
T: Test mode (do NOT make clicks, but send TEST send commands to clients to test connectivity).
SJ: Show jump values.
J: Change jump values.
N: Close all current connections with clients, and listen/accept new connections. Use this to refresh the state of connections (for example, clients dying and wanting to reconnect, or adding a new client.)
AM: Anticlockwise Me Only, click for yourself and DON'T send click commands to clients.
CM: Clockwise Me Only, click for yourself and DON'T send click commands to clients.\n""")
        direction = input("Enter menu option: ").lower()
        if not direction:
            continue
        elif direction == "n":
            server.close_and_reaccept_connections()
            continue
        elif direction == "d":
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

        raw_prediction = ocr.read_prediction()
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

        if direction != "t":
            clickbot.make_clicks_given_tuned(direction, tuned_predictions)
        
        if not "m" in direction:
            msg.raw_prediction = raw_prediction
            msg.tuned_predictions = tuned_predictions
            server.send_message(msg)

main()
