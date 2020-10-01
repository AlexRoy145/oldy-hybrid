import sys
import socket
import time
import pickle
import msvcrt
import mss
from clickbot import Clickbot
from message import Message
from macro import Macro

BUF_SIZ = 4096
CLICKBOT_PROFILE = "profile.dat"
MACRO_PROFILE = "macro.dat"

REFRESH_BET_MACRO = "Refresh page if kicked for late bets"
RESIGNIN_MACRO = "Resign into the website and pull up betting interface"

def connect_to_server(ip, port):
    print(f"Attempting to connect to {ip}:{port} with timeout of 5 seconds...")
    ret = 1
    while ret != 0:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(5)
        start = time.perf_counter()
        ret = client.connect_ex((ip, port))
        latency = (time.perf_counter() - start)*1000
        if ret == 0:
            print(f"Connected successfully with latency {latency}ms")
            client.settimeout(None)
            return client
        else:
            print("Failed to connect. Trying again..") 
            time.sleep(2)

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
    client = connect_to_server(server_ip, server_port)

    while True:

        print("Listening for commands...")
        msg = client.recv(BUF_SIZ)
        if not msg:
            print("Connection closed, attempting to reconnect...")
            client.close()
            client = connect_to_server(server_ip, server_port)
            continue

        try:
            msg = pickle.loads(msg)
        except pickle.UnpicklingError as e:
            print(f"Error receiving message from server: {e}")
            continue

        print("Received message:\n", msg)

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
