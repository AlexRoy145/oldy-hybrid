import argparse
import discord
import time
import os
import os.path
import pickle
from ocr import OCR
from dotenv import load_dotenv
from datetime import datetime
from macro import Macro

PROFILE_DIR = "../../../Documents/crm_saved_profiles"
DEALER_DIR = os.path.join(PROFILE_DIR, "dealers")
MACRO_PROFILE = "dealer_macro.dat"
OCR_PROFILE = "dealer_ocr.dat"

DEALER_TIMES_FILE = os.path.join(PROFILE_DIR, "dealer_times.dat")

def normalize_timestamp(timestamp):
    if timestamp.minute < 30:
        minute = 0
    else:
        minute = 30

    second = 0
    microsecond = 0

    return timestamp.replace(minute=minute, second=second, microsecond=microsecond)


def main():

    parser = argparse.ArgumentParser(description="Run the dealer bot that logs in and checks what dealer is playing in 30 mins")
    parser.add_argument("--site-url", type=str, help="The url of the site (do NOT include www, but include the .com or .ag or .eu) for use with signin macros")
    parser.add_argument("--username", type=str, help="The username to use for the website for the signin macro.")
    parser.add_argument("--password", type=str, help="The password to use for the website for the signin macro.")
    parser.add_argument("--record-dealers", action="store_true", help="Specify recording dealers to data file for later analysis")
    args = parser.parse_args()

    macro = Macro(PROFILE_DIR)
    if not macro.load_profile(MACRO_PROFILE):
        macro.record_signin_macro()
        macro.save_profile(MACRO_PROFILE)

    ocr = OCR(PROFILE_DIR)
    if not ocr.load_profile(OCR_PROFILE):
        print("Could not find ocr data. Setting up from scratch.")
        ocr.set_dealer_name_zone()
        ocr.screenshot_zone = ocr.dealer_name_zone
        ocr.save_profile(OCR_PROFILE)

    load_dotenv()
    WEBHOOK_ID = os.getenv("WEBHOOK_ID")
    WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN")
    webhook = discord.Webhook.partial(WEBHOOK_ID, WEBHOOK_TOKEN, adapter=discord.RequestsWebhookAdapter())

    i = 0
    time_dealer_map = {}
    if os.path.isfile(DEALER_TIMES_FILE):
        with open(DEALER_TIMES_FILE, "rb") as f:
            time_dealer_map = pickle.load(f)

    if args.record_dealers:
        while True:
            try:
                now = datetime.now()
                minute = now.minute
                if minute == 3 or minute == 33:
                #if True:
                    macro.execute_macro(site=args.site_url, username=args.username, password=args.password)
                
                    # capture dealer name
                    dealer_name = ocr.read(zone=ocr.dealer_name_zone, get_letters=True, pageseg=8, invert=True)
                    if dealer_name:
                        dealer_name = dealer_name.replace("\n", "")
                    else:
                        dealer_name = f"none_{i}"
                        i += 1
                    dealer_pic_filename = os.path.join(DEALER_DIR, f"{dealer_name}.jpg")
                    try:
                        ocr.take_screenshot(dealer_pic_filename)
                    except OSError as e:
                        print(f"Dealer name {dealer_name} screenshot will be saved as dealer_{i}.jpg")
                        print(e)
                        ocr.take_screenshot(os.path.join(DEALER_DIR, f"dealer_{i}.jpg"))
                        i += 1

                    normalized_timestamp = normalize_timestamp(now)
                    print(f"Dealer {dealer_name} is dealing roulette at {normalized_timestamp}")
                    webhook.send(f"{dealer_name} is dealing roulette right now at {normalized_timestamp}")
                    time_dealer_map[normalized_timestamp] = dealer_name
                    with open(DEALER_TIMES_FILE, "wb") as f:
                        pickle.dump(time_dealer_map, f)

                time.sleep(30)
            except KeyboardInterrupt:
                exit()
    else:

        while True:
            try:
                # execute on the 2nd minute and 32nd minute of each hour
                minute = datetime.now().minute        
                if minute == 2 or minute == 32:
                    macro.execute_macro(site=args.site_url, username=args.username, password=args.password)
                    
                    # capture dealer name
                    dealer_name = ocr.read(zone=ocr.dealer_name_zone, get_letters=True)
                    print(dealer_name)
                    webhook.send(f"{dealer_name} will be dealing roulette in 30 minutes.")

                time.sleep(60)
            except KeyboardInterrupt:
                exit()

main()
