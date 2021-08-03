import argparse
import discord
import calendar
import time
import os
import os.path
import pickle
from ocr import OCR
from dotenv import load_dotenv
from datetime import datetime, timedelta
from macro import Macro

BEST_DEALER_DAT = "best_dealers.dat"
ALL_DEALERS_DAT = "all_dealers.dat"
PROFILE_DIR = "../../../Documents/crm_saved_profiles"
DEALER_DIR = os.path.join(PROFILE_DIR, "dealers")
MACRO_PROFILE = "dealer_macro.dat"
OCR_PROFILE = "dealer_ocr.dat"
MACRO_PROFILE_ALERT = "dealer_macro.dat.alert"
OCR_PROFILE_ALERT = "dealer_ocr.dat.alert"

DEALER_TIMES_FILE = os.path.join(PROFILE_DIR, "dealer_times.dat")


def serialize(time_dealer_map):
    with open(DEALER_TIMES_FILE, "wb") as f:
        pickle.dump(time_dealer_map, f)


def view(time_dealer_map):
    timestamps = sorted(list(time_dealer_map.keys()))
    for timestamp in timestamps:
        print(f"{calendar.day_name[timestamp.weekday()]},{timestamp},{time_dealer_map[timestamp]}")


def add_dealers_to_dict(time_dealer_map):
    while True:
        try:
            dealer = input("Enter the dealer: ")
            timestamp = input("Enter the timestamp (example: 2021-01-20 16:30): ")
            timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M")
            time_dealer_map[timestamp] = dealer
            print(f"Added {dealer} to the timestamp dict.")
        except KeyboardInterrupt:
            print(f"User quit.")
            serialize(time_dealer_map)
            return


def normalize_timestamp(timestamp):
    if timestamp.minute < 30:
        minute = 0
    else:
        minute = 30

    second = 0
    microsecond = 0

    return timestamp.replace(minute=minute, second=second, microsecond=microsecond)


def main():
    parser = argparse.ArgumentParser(
        description="Run the dealer bot that logs in and checks what dealer is playing in 30 mins"
    )
    parser.add_argument(
        "--site-url", type=str,
        help="The url of the site (do NOT include www, but include the .com or .ag or .eu) for use with signin macros"
    )
    parser.add_argument("--username", type=str, help="The username to use for the website for the signin macro.")
    parser.add_argument("--password", type=str, help="The password to use for the website for the signin macro.")
    parser.add_argument(
        "--record-dealers", action="store_true", help="Specify recording dealers to data file for later analysis"
    )
    parser.add_argument(
        "--add", action="store_true", help="Add dealers to the timestamp dealer dictionary interactively"
    )
    parser.add_argument("--view", action="store_true", help="View the timestamp to dealer dictionary.")
    args = parser.parse_args()

    if args.record_dealers:
        macro_profile = MACRO_PROFILE
        ocr_profile = OCR_PROFILE
    else:
        macro_profile = MACRO_PROFILE_ALERT
        ocr_profile = OCR_PROFILE_ALERT

    macro = Macro(PROFILE_DIR)
    if not macro.load_profile(macro_profile):
        macro.record_signin_macro()
        macro.save_profile(macro_profile)

    ocr = OCR(PROFILE_DIR)
    if not ocr.load_profile(ocr_profile):
        print("Could not find ocr data. Setting up from scratch.")
        ocr.set_dealer_name_zone()
        ocr.screenshot_zone = ocr.dealer_name_zone
        ocr.save_profile(ocr_profile)

    load_dotenv()
    webhook_id = os.getenv("WEBHOOK_ID")
    webhook_token = os.getenv("WEBHOOK_TOKEN")
    webhook = discord.Webhook.partial(webhook_id, webhook_token, adapter=discord.RequestsWebhookAdapter())

    i = 0
    time_dealer_map = {}
    if os.path.isfile(DEALER_TIMES_FILE):
        with open(DEALER_TIMES_FILE, "rb") as f:
            time_dealer_map = pickle.load(f)

    if args.view:
        view(time_dealer_map)
        exit()

    if args.add:
        add_dealers_to_dict(time_dealer_map)
        exit()

    if args.record_dealers:
        while True:
            try:
                now = datetime.now()
                minute = now.minute
                if minute == 3 or minute == 33:
                    # if True:
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
                    dealer_name = dealer_name.replace("‘", "").replace(",", "").replace(".", "")
                    print(f"Dealer {dealer_name} is dealing roulette at {normalized_timestamp}")
                    webhook.send(f"{dealer_name} is dealing roulette right now at {normalized_timestamp}")
                    time_dealer_map[normalized_timestamp] = dealer_name
                    serialize(time_dealer_map)

                time.sleep(30)
            except KeyboardInterrupt:
                exit()
    else:

        with open(BEST_DEALER_DAT, "rb") as f:
            best_dealer_dict = pickle.load(f)

        with open(ALL_DEALERS_DAT, "rb") as f:
            all_dealers_dict = pickle.load(f)

        while True:
            try:
                # execute on the 2nd minute and 32nd minute of each hour
                now = datetime.now()
                minute = now.minute
                future_by_30 = now + timedelta(minutes=30)
                normalized_timestamp_future = normalize_timestamp(future_by_30)

                if minute == 4 or minute == 34:
                    macro.execute_macro(site=args.site_url, username=args.username, password=args.password)

                    # capture dealer name
                    dealer_name = ocr.read(zone=ocr.dealer_name_zone, get_letters=True, pageseg=8, invert=True)
                    dealer_name = dealer_name.replace("‘", "").replace(".", "").replace(",", "").replace("\n", "")
                    print(dealer_name)
                    found = False
                    time_dealer_map[normalized_timestamp_future] = dealer_name
                    serialize(time_dealer_map)
                    for dealer_name_key in best_dealer_dict.keys():
                        if dealer_name.lower() in dealer_name_key.lower():
                            found = True
                            webhook.send(
                                f"""ATTENTION! {dealer_name} 
will be dealing roulette in 30 minutes.\n{best_dealer_dict[dealer_name]}"""
                            )
                    if not found:
                        try:
                            webhook.send(
                                f"{dealer_name} will be dealing roulette in 30\
                                 minutes.\n{all_dealers_dict[dealer_name]"
                            )
                        except KeyError:
                            webhook.send(f"Unknown dealer {dealer_name} will be dealing roulette in 30 minutes.")

                time.sleep(60)
            except KeyboardInterrupt:
                exit()


main()
