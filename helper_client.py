import argparse
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

    parser = argparse.ArgumentParser(description="Run the client betting program.")
    parser.add_argument("server_ip", type=str, help="The server's IP address.")
    parser.add_argument("server_port", type=int, help="The server's port.")
    parser.add_argument("--use-refresh-macro", action="store_true")
    parser.add_argument("--use-signin-macro", action="store_true")
    args = parser.parse_args()

    use_macro = args.use_refresh_macro or args.use_signin_macro

    clickbot = Clickbot()
    if not clickbot.load_profile(CLICKBOT_PROFILE):
        print("Could not find profile. Setting up from scratch.")
        clickbot.set_clicks()
        clickbot.save_profile(CLICKBOT_PROFILE)

    if use_macro:
        macro = Macro()
        if not macro.load_profile(MACRO_PROFILE):
            macro.set_screen_condition()
            if args.use_refresh_macro:
                macro.record_macro(REFRESH_BET_MACRO)
            if args.use_signin_macro:
                macro.record_macro(RESIGNIN_MACRO)
            macro.save_profile(MACRO_PROFILE)

    input("Press ENTER when ready to connect to server:")
    client = Client(args.server_ip, args.server_port)
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
            clickbot.make_clicks_given_tuned(msg.direction, msg.tuned_predictions)

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
