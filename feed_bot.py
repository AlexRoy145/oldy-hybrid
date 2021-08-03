import time
from macro import Macro

PROFILE_DIR = "C:/Users/AKurt/Documents/crm_saved_profiles"
MACRO_PROFILE = "feed_macro.dat"

SPIN_INTERVAL = 9
SLEEP_SECONDS = 50


def main():
    macro = Macro(PROFILE_DIR)
    if not macro.load_profile(MACRO_PROFILE):
        macro.set_screen_condition(green=True)
        macro.record_macro()
        macro.save_profile(MACRO_PROFILE)

    spins_seen = 0
    try:
        while True:
            if macro.is_screen_condition_true(green=True):
                print(f"Seen {spins_seen} spins so far.")
                if spins_seen >= SPIN_INTERVAL:
                    print("Betting now.")
                    macro.execute_macro()
                    spins_seen = 0
                time.sleep(SLEEP_SECONDS)
                spins_seen += 1

    except KeyboardInterrupt:
        exit()


main()
