import argparse
import datetime 
import pickle
from scatter import Scatter
from collections import Counter

BEST_DEALER_FILE = "best_dealers.txt"
BEST_DEALER_DAT = "best_dealers.dat"
ALL_DEALERS_FILE = "all_dealers.dat"

MIN_BALL_REVS = 12
MAX_BALL_REVS = 17
MIN_ROTOR = 3500
MAX_ROTOR = 6500
MIN_C = .65

def normalize_timestamp(timestamp):
    if timestamp.minute < 30:
        minute = 0
    else:
        minute = 30

    second = 0
    microsecond = 0

    return timestamp.replace(minute=minute, second=second, microsecond=microsecond)


def main():
    parser = argparse.ArgumentParser(description="Get the proportion of diamond hits for each dealer")
    parser.add_argument("scatter_file", type=str, help="The .dat file containing the scatter")
    parser.add_argument("dealer_file", type=str, help="The .dat file containing dealer times.")
    parser.add_argument("--get-best", action="store_true", help="Print the best dealers and store to file")
    args = parser.parse_args()

    with open(args.scatter_file, "rb") as f:
        scatter = pickle.load(f)

    with open(args.dealer_file, "rb") as f:
        timestamp_to_dealers = pickle.load(f)

    dealers_to_data = {}
    for datapoint in scatter['data']:
        # convert timestamp to EST
        timestamp_est = datapoint.timestamp + datetime.timedelta(hours=3)
        timestamp_est = normalize_timestamp(timestamp_est) 

        # get the corresponding dealer
        if not timestamp_est in timestamp_to_dealers:
            # skip if data doesnt have corresponding dealer
            continue
        dealer = timestamp_to_dealers[timestamp_est]
        if not dealer in dealers_to_data:
            dealers_to_data[dealer] = [datapoint]
        else:
            dealers_to_data[dealer].append(datapoint)

    #with open("dealer_info.csv^ 
    best_dealers = {}
    all_dealers = {}

    for dealer in dealers_to_data:

        dealer_clean = dealer.replace("‘", "").replace(".", "").replace(",", "")

        diamond_counts_anti = Counter()
        diamond_counts_clock = Counter()

        ball_revs_anti = 0
        ball_revs_clock = 0

        rotor_speed_anti = 0
        rotor_speed_clock = 0

        spins_anti = 0
        spins_clock = 0
        
        for data in dealers_to_data[dealer]:
            diamond_hit = Scatter.convert_fall_point_to_diamond_hit(data.fall_zone, data.direction)
            if "a" in data.direction:
                diamond_counts_anti[diamond_hit] += 1
                ball_revs_anti += data.ball_revs
                rotor_speed_anti += data.rotor_speed
                spins_anti += 1
            else:
                diamond_counts_clock[diamond_hit] += 1
                ball_revs_clock += data.ball_revs
                rotor_speed_clock += data.rotor_speed
                spins_clock += 1

        if spins_anti > 0:
            avg_revs_anti = int(round(ball_revs_anti / spins_anti))
            avg_rotor_anti = int(round(rotor_speed_anti / spins_anti))
            c_proportion_anti = diamond_counts_anti["C"] / sum(diamond_counts_anti.values())
            c_proportion_anti_str = "{0:.0%}".format(c_proportion_anti)
            if args.get_best:
                if (avg_revs_anti >= MIN_BALL_REVS and 
                    avg_revs_anti <= MAX_BALL_REVS and 
                    avg_rotor_anti >= MIN_ROTOR and 
                    avg_rotor_anti <= MAX_ROTOR and
                    c_proportion_anti >= MIN_C):
                    
                    dealer_str = f"{dealer_clean}'s ANTI diamond counts: {diamond_counts_anti}. C Proportion: {c_proportion_anti_str}. Avg Ball Revs: {avg_revs_anti}. Avg Rotor: {avg_rotor_anti}"
                    best_dealers[dealer_clean] = dealer_str
                    print(dealer_str)
                    print()
            else:
                dealer_str = f"{dealer_clean}'s ANTI diamond counts: {diamond_counts_anti}. C Proportion: {c_proportion_anti_str}. Avg Ball Revs: {avg_revs_anti}. Avg Rotor: {avg_rotor_anti}"
                print(dealer_str)
                all_dealers[dealer_clean] = dealer_str

        if not args.get_best:
            if spins_clock > 0:
                avg_revs_clock = int(round(ball_revs_clock / spins_clock))
                avg_rotor_clock = int(round(rotor_speed_clock / spins_anti))
                c_proportion_clock = diamond_counts_clock["C"] / sum(diamond_counts_clock.values())
                c_proportion_clock = "{0:.0%}".format(c_proportion_clock)
                print(f"{dealer}'s CLOCK diamond counts: {diamond_counts_clock}. C Proportion: {c_proportion_clock}. Avg Ball Revs: {avg_revs_clock}. Avg Rotor: {avg_rotor_clock}")


    with open(ALL_DEALERS_FILE, "wb") as f:
        pickle.dump(all_dealers, f)

    if args.get_best:
        with open(BEST_DEALER_FILE, "w") as f:
            for dealer in best_dealers:
                f.write(best_dealers[dealer] + "\n")

        with open(BEST_DEALER_DAT, "wb") as f:
            pickle.dump(best_dealers, f)

main()
