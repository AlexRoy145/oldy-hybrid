import pickle
import os
import os.path

class Datapoint:
    def __init__(self, direction=None, raw=None, winning=None, rotor_speed=None):
        self.direction = direction
        self.raw = raw
        self.winning = winning
        self.rotor_speed = rotor_speed


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
        datapoint = Datapoint(direction=direction, raw=raw, winning=winning, rotor_speed=rotor_speed)
        self.data.append(datapoint)
        path = os.path.join(self.profile_dir, self.csv_filename)
        with open(path, "a") as f:
            f.write(f"{raw},{winning},{direction},unknown,unknown,{rotor_speed},unknown\n")

