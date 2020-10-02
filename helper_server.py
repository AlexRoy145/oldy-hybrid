import sys
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

    if len(sys.argv) > 3:
        server_ip = sys.argv[1]
        server_port = int(sys.argv[2])
        use_green_swap = bool(sys.argv[3])
    else:
        print("Usage: py helper_server.py server_ip_address server_port use_green_swap(True or False)")
        exit()

    clickbot = Clickbot()
    if not clickbot.load_profile(CLICKBOT_PROFILE):
        print("Could not find profile. Setting up from scratch.")
        clickbot.set_clicks()
        clickbot.set_jump_values()
        clickbot.set_detection_zone()
        clickbot.save_profile(CLICKBOT_PROFILE)

    server = Server(server_ip, server_port)
    server.accept_new_connections()

    ocr = OCR(clickbot.detection_zone)
      
    while True:
        msg = Message()
        print("""\nA: Anticlockwise, click for yourself and send click command to clients.
C: Clockwise, click for yourself and send click command to clients.
D: Change the detection zone.
T: Test mode (do NOT make clicks, but send TEST send commands to clients to test connectivity).
J: Change jump values.
N: Close all current connections with clients, and listen/accept new connections. Use this to refresh the state of connections (for example, clients dying and wanting to reconnect, or adding a new client.)
AM: Anticlockwise Me Only, click for yourself and DON'T send click commands to clients.
CM: Clockwise Me Only, click for yourself and DON'T send click commands to clients.\n""")
        direction = input("Enter menu option: ").lower()
        if not direction:
            continue
        if direction == "n":
            server.close_and_reaccept_connections()
            continue
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
            msg.test_mode = True
        else:
            if use_green_swap:
                # Do Green Swapping
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

        prediction = ocr.read_prediction()
            
        try:
            prediction = int(prediction)
        except (ValueError, TypeError) as e:
            print("ERROR: Incorrectly detected raw prediction, could not click.")
            msg.error = True
            if not "m" in direction:
                server.send_message(msg)
            continue

        if prediction < 0 or prediction > 36:
            print("ERROR: Incorrectly detected raw prediction, could not click.")
            msg.error = True
            if not "m" in direction:
                server.send_message(msg)
            continue

        if not use_green_swap:
            green_swap = None
        clickbot.make_clicks_given_raw(direction, prediction, green_swap=green_swap)
        
        if not "m" in direction:
            msg.raw_prediction = prediction
            msg.tuned_predictions = clickbot.get_tuned_from_raw(direction, prediction, green_swap=green_swap)
            server.send_message(msg)

main()
