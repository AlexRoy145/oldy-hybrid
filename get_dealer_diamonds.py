import argparse
import datetime 
import pickle
from scatter import Scatter
from collections import Counter

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

    for dealer in dealers_to_data:

        diamond_counts_anti = Counter()
        diamond_counts_clock = Counter()
        
        for data in dealers_to_data[dealer]:
            diamond_hit = Scatter.convert_fall_point_to_diamond_hit(data.fall_zone, data.direction)
            if "a" in data.direction:
                diamond_counts_anti[diamond_hit] += 1
            else:
                diamond_counts_clock[diamond_hit] += 1

        c_proportion_anti = diamond_counts_anti["C"] / sum(diamond_counts_anti.values())
        c_proportion_clock = diamond_counts_clock["C"] / sum(diamond_counts_clock.values())
        c_proportion_anti = "{0:.0%}".format(c_proportion_anti)
        c_proportion_clock = "{0:.0%}".format(c_proportion_clock)
        print(f"{dealer}'s ANTI diamond counts: {diamond_counts_anti}. C Proportion: {c_proportion_anti}")
        print(f"{dealer}'s CLOCK diamond counts: {diamond_counts_clock}. C Proportion: {c_proportion_clock}")
        print()

main()
