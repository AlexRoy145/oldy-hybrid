import argparse
import discord
import os
import requests
import time
import threading
import pickle
import msvcrt
import mss
import win32gui
from socket import gethostname
from dotenv import load_dotenv
from clickbot import Clickbot
from message import Message
from macro import Macro
from client import Client
from ocr import OCR

PROFILE_DIR = "crm_saved_profiles"
CLICKBOT_PROFILE = "profile.dat"
OCR_PROFILE = "ocr.dat"
SCREENSHOT_FILE = os.path.join(PROFILE_DIR, ".temp_screenshot.jpg")

REFRESH_MACRO_DIR = "refresh_macros"
SIGNIN_MACRO_DIR = "signin_macros"

MAX_MACRO_COUNT = 2

# in minutes
CHECK_INTERVAL = 15

class CRMClient:

    def alert(self, msg):
        self.webhook.send(f"{self.hostname}: {msg}")

    def send_screenshot(self, seq_num):
        self.webhook.send(f"{self.hostname}, Spin #: {seq_num}", file=discord.File(SCREENSHOT_FILE))

    def __init__(self, server_ip, server_port, use_refresh_macro, use_signin_macro, site):

        self.server_ip = server_ip
        self.server_port = server_port
        self.site = site
        self.use_refresh_macro = use_refresh_macro
        self.use_signin_macro = use_signin_macro
        load_dotenv()
        WEBHOOK_ID = os.getenv("WEBHOOK_ID")
        WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN")
        self.webhook = discord.Webhook.partial(WEBHOOK_ID, WEBHOOK_TOKEN, adapter=discord.RequestsWebhookAdapter())
        self.hostname = gethostname()

        self.resize_cmd_window()
        self.resize_betting_window()

        # error metrics
        self.refreshes_used = 0
        self.error_count = 0
        self.time_received_last_msg = time.time()

        self.use_macro = self.use_refresh_macro or self.use_signin_macro
        
        self.clickbot = Clickbot(PROFILE_DIR)
        if not self.clickbot.load_profile(CLICKBOT_PROFILE):
            print("Could not find profile. Setting up from scratch.")
            self.clickbot.set_clicks()
            self.clickbot.save_profile(CLICKBOT_PROFILE)

        
        self.ocr = OCR(PROFILE_DIR)
        if not self.ocr.load_profile(OCR_PROFILE):
            print("Could not find ocr data. Setting up from scratch.")
            self.ocr.set_screenshot_zone()
            self.ocr.save_profile(OCR_PROFILE)

        if self.use_refresh_macro:
            self.refresh_macro_name = f"refresh_{self.site}.dat"
            self.refresh_macro = Macro(REFRESH_MACRO_DIR)
            if not self.refresh_macro.load_profile(self.refresh_macro_name):
                self.refresh_macro.set_screen_condition()
                self.refresh_macro.record_macro()
                self.refresh_macro.save_profile(self.refresh_macro_name)

        if self.use_signin_macro:
            self.signin_macro_name = f"signin_{self.site}.dat"
            self.signin_macro = Macro(SIGNIN_MACRO_DIR)
            if not self.signin_macro.load_profile(self.signin_macro_name):
                self.signin_macro.set_screen_condition()
                self.signin_macro.record_macro()
                self.signin_macro.save_profile(self.signin_macro_name)


        self.resize_betting_window()

        input("Press ENTER when ready to connect to server and to resize the betting window:")
        self.resize_betting_window()
        self.client = Client(self.server_ip, self.server_port)
        self.client.connect_to_server()


    def run(self):
        self.app_thread = threading.Thread(target=self.start_app, args=())
        self.app_thread.daemon = True
        self.app_thread.start()
        duration = 0
        while self.app_thread.is_alive():
            time.sleep(1)
            '''
            duration += 1
            if duration >= 60 * CHECK_INTERVAL:
                if self.refreshes_used > 8:
                    self.alert(f"WARNING: Used {self.refreshes_used} refreshes in the past {CHECK_INTERVAL} minutes.")

                if self.error_count > 5:
                    self.alert(f"WARNING: Received {self.error_count} misdetected predictions in the past {CHECK_INTERVAL} minutes.")

                time_since_last_msg = int((time.time() - self.time_received_last_msg) / 60)
                if time_since_last_msg >= CHECK_INTERVAL:
                    self.alert(f"WARNING: It has been {time_since_last_msg} minutes since receiving the last command.")

                self.refreshes_used = 0
                self.error_count = 0
                duration = 0
            '''


    def start_app(self):
        while True:

            print("Listening for commands...")
            msg = self.client.recv_msg()
            self.time_received_last_msg = time.time()

            if not msg:
                continue

            if msg.test_mode:
                print("TEST MODE, NOT CLICKING.")
            else:
                if msg.error:
                    print("Error detecting raw prediction. Skipping this spin.")
                    self.error_count += 1
                    continue
                self.clickbot.make_clicks_given_tuned(msg.direction, msg.tuned_predictions)

            if self.use_macro and not msg.test_mode:
                macro_count = 0
                time.sleep(4)
                if self.refresh_macro.is_screen_condition_true():
                    while True:
                        if macro_count > MAX_MACRO_COUNT:
                            err = f"CRITICAL: Used macro {macro_count} times in a row and CRM Client still can't see the betting board. CRM Client had to quit because it doesn't know what to do. Log in and fix."
                            print(err)
                            self.alert(err)
                            self.client.close()
                            exit()
                        if self.use_refresh_macro:
                            self.refresh_macro.execute_macro()
                            self.resize_betting_window()
                            self.refreshes_used += 1
                            time.sleep(10)
                        if self.refresh_macro.is_screen_condition_true():
                            if self.use_signin_macro:
                                self.signin_macro.execute_macro()
                                self.resize_betting_window()
                                if not self.signin_macro.is_screen_condition_true():
                                    break
                                macro_count += 1
                        else:
                            break

            # take screenshot
            self.ocr.take_screenshot(SCREENSHOT_FILE)
            self.send_screenshot(msg.seq_num)


    def resize_betting_window(self):
        def callback(handle, data):
            title = win32gui.GetWindowText(handle).lower()
            # try to also size the other browser windows
            if not "notepad" in title and not "expressvpn" in title:
                handles.append(handle)

        handles = []
        win32gui.EnumWindows(callback, None)
        if handles:
            for handle in handles:
                win32gui.MoveWindow(handle, 0, 0, 1200, 1040, True)
        else:
            print("Could not find appropriate window to resize.")


    def resize_cmd_window(self):
        def callback(handle, data):
            title = win32gui.GetWindowText(handle)
            if "client" in title.lower():
                handles.append(handle)

        handles = []
        win32gui.EnumWindows(callback, None)
        if handles:
            win32gui.MoveWindow(handles[0], 1300, 500, 600, 500, True)
        else:
            print("Could not find appropriate window to resize.")



def main():
    parser = argparse.ArgumentParser(description="Run the client betting program.")
    parser.add_argument("server_ip", type=str, help="The server's IP address.")
    parser.add_argument("server_port", type=int, help="The server's port.")
    parser.add_argument("--site-name", type=str, help="The casino site NAME (do NOT include www or .com/.ag/.eu) to use with the refresh macro")
    parser.add_argument("--use-refresh-macro", action="store_true")
    parser.add_argument("--use-signin-macro", action="store_true")
    args = parser.parse_args()

    app = CRMClient(args.server_ip, args.server_port, args.use_refresh_macro, args.use_signin_macro, args.site_name)
    try:
        app.run()
    except KeyboardInterrupt:
        exit()

main()
