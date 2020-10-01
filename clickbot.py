from pynput import mouse
from pynput.mouse import Button, Controller
import os.path
import pickle

class Clickbot:

    def __init__(self):
        self.m = Controller()
        self.number_coords = []
        self.jump_anti = []
        self.jump_clock = []
        self.detection_zone = []
        self.european_wheel = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]


    def load_profile(self, data_file):
        if os.path.isfile(data_file):
            with open(data_file, "rb") as f:
                self.__dict__.update(pickle.load(f))
            return True
        else:
            return False


    def save_profile(self, data_file):
        with open(data_file, "wb") as f:
            pickle.dump(self.__dict__, f)

    def set_jump_helper(self, range_str, jump_list):
        range_split = range_str.split(",")
        for rang in range_split:
            split = rang.split(" to ")
            start = int(split[0].strip())
            if len(split) == 1:
                end = start
            else:
                end = int(split[1].strip())

            if start > 18 or end > 18:
                raise ValueError("Number cannot be greater than 18.")
            if start < -18 or end < -18:
                raise ValueError("Number cannot be less than -18.")
            if start > end:
                temp = start
                start = end
                end = temp
            for jump_value in range(start, end + 1):
                jump_list.append(jump_value)

        print(f"Jump Values: {jump_list}")


    def set_jump_values(self):
        while True:
            try:
                self.jump_anti = []
                anti_range = input("Input range for anticlockwise (example: 1 to 15, -18 to -5): ")
                self.set_jump_helper(anti_range, self.jump_anti)

                self.jump_clock = []
                clock_range = input("Input range for clockwise (example: 1 to 15, -18 to -5, -1): ")
                self.set_jump_helper(clock_range, self.jump_clock)
                break
            except ValueError as e:
                print(f"Invalid format: {e}")


    def set_detection_zone(self):
        self.detection_zone = []

        input("Hover the mouse over the upper left corner of the detection zone for the raw prediction number, then hit ENTER.")
        x_top,y_top = self.m.position
        self.detection_zone.append(x_top)
        self.detection_zone.append(y_top)

        input("Hover the mouse over the bottom right corner of the detection zone, then hit ENTER.")
        x_bot,y_bot = self.m.position
        self.detection_zone.append(x_bot)
        self.detection_zone.append(y_bot)

        print(f"Bounding box: {self.detection_zone}")


    def set_clicks(self):
        for i in range(37):
            input(f"Hover the mouse over number {i} and then press ENTER:")
            x,y = self.m.position
            self.number_coords.append((x,y))
            print(f"Number {i} at ({x},{y}).")


    def get_tuned_from_raw(self, direction, raw_prediction):
        if direction == "a":
            jumps = self.jump_anti
        else:
            jumps = self.jump_clock

        tuned_predictions = []
        for jump in jumps:
            length = len(self.european_wheel)
            raw_idx = self.european_wheel.index(raw_prediction)

            tuned_idx = raw_idx + jump
            if tuned_idx > (length - 1):
                tuned_predictions.append(self.european_wheel[tuned_idx % length])
            else:
                tuned_predictions.append(self.european_wheel[tuned_idx])

        return tuned_predictions


    def make_clicks_given_raw(self, direction, raw_prediction):
        if direction != "t":
            self.make_clicks(direction, self.get_tuned_from_raw(direction, raw_prediction))
        

    def make_clicks(self, direction, tuned_predictions):
        if direction != "t":
            for tuned_prediction in tuned_predictions:
                self.m.position = self.number_coords[tuned_prediction]
                self.m.click(Button.left)
            
