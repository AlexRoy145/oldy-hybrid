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

def main():
    if len(sys.argv) > 2:
        server_ip = sys.argv[1]
        server_port = int(sys.argv[2])
    else:
        print("Usage: py helper_client.py server_ip_address server_port")
        exit()

    clickbot = Clickbot()
    if not clickbot.load_profile(CLICKBOT_PROFILE):
        print("Could not find profile. Setting up from scratch.")
        clickbot.set_clicks()
        clickbot.set_jump_values()
        clickbot.save_profile(CLICKBOT_PROFILE)

    macro = Macro()
    if not macro.load_profile(MACRO_PROFILE):
        macro.set_screen_condition()
        macro.record_macro(REFRESH_BET_MACRO)
        macro.record_macro(RESIGNIN_MACRO)
        macro.save_profile()

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
            clickbot.make_clicks(msg.direction, msg.prediction)

        time.sleep(4)
        if macro.is_screen_condition_true():
            while True:
                macro.execute_macro(REFRESH_BET_MACRO)
                time.sleep(6)
                if macro.is_screen_condition_true():
                    macro.execute_macro(RESIGNIN_MACRO)


main()
