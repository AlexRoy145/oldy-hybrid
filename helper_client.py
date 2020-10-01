import sys
import time
import pickle
import msvcrt
import mss
from clickbot import Clickbot
from message import Message
from macro import Macro
from client import Client

CLICKBOT_PROFILE = "profile.dat"
MACRO_PROFILE = "macro.dat"

REFRESH_BET_MACRO = "Refresh page if kicked for late bets"
RESIGNIN_MACRO = "Resign into the website and pull up betting interface"

MAX_MACRO_COUNT = 3

def main():
    if len(sys.argv) > 3:
        server_ip = sys.argv[1]
        server_port = int(sys.argv[2])
        use_macro = bool(sys.argv[3])
    else:
        print("Usage: py helper_client.py server_ip_address server_port use_macro(True or False)")
        exit()

    clickbot = Clickbot()
    if not clickbot.load_profile(CLICKBOT_PROFILE):
        print("Could not find profile. Setting up from scratch.")
        clickbot.set_clicks()
        clickbot.save_profile(CLICKBOT_PROFILE)

    if use_macro:
        macro = Macro()
        if not macro.load_profile(MACRO_PROFILE):
            macro.set_screen_condition()
            macro.record_macro(REFRESH_BET_MACRO)
            macro.record_macro(RESIGNIN_MACRO)
            macro.save_profile(MACRO_PROFILE)

    input("Press ENTER when ready to connect to server:")
    client = Client(server_ip, server_port)
    client.connect_to_server()

    while True:

        print("Listening for commands...")
        msg = client.recv_msg()
        if not msg:
            continue
        
        if msg.test_mode:
            print("TEST MODE, NOT CLICKING.")
        else:
            if msg.error:
                print("Error detecting raw prediction. Skipping this spin.")
                continue
            clickbot.make_clicks(msg.direction, msg.tuned_predictions)

        if use_macro:
            macro_count = 0
            time.sleep(4)
            if macro.is_screen_condition_true():
                while True:
                    if macro_count > MAX_MACRO_COUNT:
                        print("Used macro too many times. State unknown. Quitting...")
                        client.close()
                        exit()
                    macro.execute_macro(REFRESH_BET_MACRO)
                    time.sleep(6)
                    if macro.is_screen_condition_true():
                        macro.execute_macro(RESIGNIN_MACRO)
                        macro_count += 1
                    else:
                        break


main()
