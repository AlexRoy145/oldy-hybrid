import argparse
import discord
import time
import os
from ocr import OCR
from dotenv import load_dotenv
from datetime import datetime
from macro import Macro

PROFILE_DIR = "../../../Documents/crm_saved_profiles"
MACRO_PROFILE = "dealer_bot.dat"
OCR_PROFILE = "dealer_ocr.dat"

def main():

    parser = argparse.ArgumentParser(description="Run the dealer bot that logs in and checks what dealer is playing in 30 mins")
    parser.add_argument("--site-url", type=str, help="The url of the site (do NOT include www, but include the .com or .ag or .eu) for use with signin macros")
    parser.add_argument("--username", type=str, help="The username to use for the website for the signin macro.")
    parser.add_argument("--password", type=str, help="The password to use for the website for the signin macro.")
    args = parser.parse_args()

    macro = Macro(PROFILE_DIR)
    if not macro.load_profile(MACRO_PROFILE):
        macro.record_signin_macro()
        macro.save_profile(MACRO_PROFILE)

    ocr = OCR(PROFILE_DIR)
    if not ocr.load_profile(OCR_PROFILE):
        print("Could not find ocr data. Setting up from scratch.")
        ocr.set_dealer_name_zone()
        ocr.save_profile(OCR_PROFILE)

    load_dotenv()
    WEBHOOK_ID = os.getenv("WEBHOOK_ID")
    WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN")
    webhook = discord.Webhook.partial(WEBHOOK_ID, WEBHOOK_TOKEN, adapter=discord.RequestsWebhookAdapter())


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
