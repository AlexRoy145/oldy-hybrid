import matplotlib.pyplot as plt
import pickle
import os
import os.path
import datetime

EUROPEAN_WHEEL = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]

class Datapoint:
    def __init__(self, direction=None, raw=None, winning=None, rotor_speed=None, timestamp=None):
        self.direction = direction
        self.raw = raw
        self.winning = winning
        self.rotor_speed = rotor_speed
        self.timestamp = timestamp


class Scatter:
    
    def __init__(self, profile_dir, csv_filename):
        self.profile_dir = profile_dir
        self.data = [] # list of DataPoint's
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


    def add_data(self, direction, raw, winning, rotor_speed):
        timestamp = datetime.datetime.now()
        datapoint = Datapoint(direction=direction, raw=raw, winning=winning, rotor_speed=rotor_speed, timestamp=timestamp)
        self.data.append(datapoint)
        path = os.path.join(self.profile_dir, self.csv_filename)
        with open(path, "a") as f:
            f.write(f"{raw},{winning},{direction},unknown,unknown,{rotor_speed},unknown\n")

    def calculate_jump(self, raw, winning):
        raw_idx = EUROPEAN_WHEEL.index(int(raw))
        win_idx = EUROPEAN_WHEEL.index(int(winning))
        jump = win_idx - raw_idx
        if jump > 18:
            jump = -(37 - jump)
        elif jump < -18:
            jump = (37 + jump)
        return jump

    
    def graph(self, direction=None, rotor_speed_range=None, date_range=None):
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

        for datapoint in self.data:
            if datapoint.direction == direction and datapoint.rotor_speed >= rotor_speed_start and datapoint.rotor_speed < rotor_speed_end:
                x.append(self.calculate_jump(datapoint.raw, datapoint.winning))

        plt.hist(x, bins=37, range=(-18,18), ec='black')
        plt.xticks(list(range(0,19)) + list(range(-1,-19,-1))[::-1])
        plt.show()
