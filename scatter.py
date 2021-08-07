import matplotlib.pyplot as plt
import pickle
import os
import os.path
import datetime

EUROPEAN_WHEEL = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31,
                  9, 22, 18, 29, 7, 28, 12, 35, 3, 26]


class Datapoint:
    def __init__(self, direction=None, raw=None, winning=None, rotor_speed=None, timestamp=None, fall_zone=None,
                 ball_revs=None):
        self.direction = direction
        self.raw = raw
        self.winning = winning
        self.rotor_speed = rotor_speed
        self.fall_zone = fall_zone
        self.ball_revs = ball_revs
        self.timestamp = timestamp


class Scatter:

    def __init__(self, profile_dir, csv_filename):
        self.profile_dir = profile_dir
        self.data = []  # list of DataPoint's
        self.csv_filename = csv_filename
        if not os.path.isdir(self.profile_dir):
            os.mkdir(self.profile_dir)

    def load_profile(self, data_file):
        path = os.path.join(self.profile_dir, data_file)
        if os.path.isfile(path):
            with open(path, "rb") as f:
                self.__dict__.update(pickle.load(f))
            return True
        else:
            return False

    def save_profile(self, data_file):
        path = os.path.join(self.profile_dir, data_file)
        with open(path, "wb") as f:
            pickle.dump(self.__dict__, f)

    def add_data(self, direction, raw, winning, rotor_speed, fall_zone, ball_revs):
        timestamp = datetime.datetime.now()
        data_point = Datapoint(direction=direction, raw=raw, winning=winning, rotor_speed=rotor_speed,
                               timestamp=timestamp, fall_zone=fall_zone, ball_revs=ball_revs)
        self.data.append(data_point)
        path = os.path.join(self.profile_dir, self.csv_filename)

        # translate fall zone (0 to 359) to a diamond hit
        diamond_hit = Scatter.convert_fall_point_to_diamond_hit(fall_zone, direction)

        with open(path, "a") as f:
            f.write(f"{raw},{winning},{direction},unknown,{ball_revs},{rotor_speed},{diamond_hit}\n")

    @staticmethod
    def convert_fall_point_to_diamond_hit(fall_zone, direction):
        diamond_order = [12, 1.5, 3, 4.5, 6, 7.5, 9, 10.5]

        def get_previous_diamond(direction_of_spin, diamond_hit_arg):
            diamond_idx = diamond_order.index(diamond_hit_arg)
            if "a" not in direction_of_spin:
                diamond_hit_idx = (diamond_idx + 1) % len(diamond_order)
                return diamond_order[diamond_hit_idx]
            else:
                diamond_hit_idx = diamond_idx - 1
                return diamond_order[diamond_hit_idx]

        diamonds = {3: 0,
                    1.5: 45,
                    12: 90,
                    10.5: 135,
                    9: 180,
                    7.5: 225,
                    6: 270,
                    4.5: 315}

        least_difference = 360
        diamond_hit = 3
        for diamond, diamond_degrees in diamonds.items():
            difference = abs(fall_zone - diamond_degrees)
            if difference < least_difference:
                least_difference = difference
                diamond_hit = diamond

        # if the ball fell BEFORE the associated diamond and if it fell greater than 1 pocket away
        # from it, associate with previous diamond
        if least_difference > (45 / 4):
            if "a" in direction:
                if diamond_hit == 3:
                    if fall_zone > 0:
                        diamond_hit = get_previous_diamond(direction, diamond_hit)
                elif fall_zone > diamonds[diamond_hit]:
                    diamond_hit = get_previous_diamond(direction, diamond_hit)
            else:
                if diamond_hit == 3:
                    if fall_zone > 315:
                        diamond_hit = get_previous_diamond(direction, diamond_hit)
                elif fall_zone < diamonds[diamond_hit]:
                    diamond_hit = get_previous_diamond(direction, diamond_hit)

        diamond_to_letters = {12: "A",
                              1.5: "B",
                              3: "C",
                              4.5: "D",
                              6: "E",
                              7.5: "F",
                              9: "G",
                              10.5: "H"}

        diamond_hit_formatted = diamond_to_letters[diamond_hit]
        # print(f"Associated fall zone {fall_zone} to diamond {diamond_hit}, which is also diamond {
        # diamond_hit_formatted}")
        return diamond_hit_formatted

    @staticmethod
    def calculate_jump(raw, winning):
        raw_idx = EUROPEAN_WHEEL.index(int(raw))
        win_idx = EUROPEAN_WHEEL.index(int(winning))
        jump = win_idx - raw_idx
        if jump > 18:
            jump = -(37 - jump)
        elif jump < -18:
            jump = (37 + jump)
        return jump

    def graph(self, direction=None, rotor_speed_range=None, date_range=None, fall_point_range=None):
        x = []
        if rotor_speed_range:
            split = rotor_speed_range.split("-")
            rotor_speed_start = int(split[0])
            rotor_speed_end = int(split[1])
        else:
            rotor_speed_start = 0
            rotor_speed_end = 100000

        if date_range:
            split = date_range.split(" to ")
            date_start = split[0]
            date_end = split[1]
        else:
            date_start = "1-1-1970"
            date_end = "1-1-2170"

        if fall_point_range:
            split = fall_point_range.split("-")
            fall_point_start = int(split[0])
            fall_point_end = int(split[1])
        else:
            fall_point_start = 0
            fall_point_end = 360

        for datapoint in self.data:
            if datapoint.direction == direction and rotor_speed_start <= datapoint.rotor_speed < rotor_speed_end and \
                    fall_point_start < datapoint.fall_zone < fall_point_end:
                x.append(self.calculate_jump(datapoint.raw, datapoint.winning))

        print(f"Number of spins: {len(x)}")

        plt.hist(x, bins=37, range=(-18, 18), ec='black')
        plt.xticks(list(range(0, 19)) + list(range(-1, -19, -1))[::-1])
        plt.show()
