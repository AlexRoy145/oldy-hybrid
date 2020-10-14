import os
import os.path
import pickle
from pynput import mouse
from pynput.mouse import Button, Controller

class Clickbot:

    def __init__(self, profile_dir):
        self.m = Controller()
        self.number_coords = []
        self.jump_anti = []
        self.jump_clock = []
        self.detection_zone = []
        self.european_wheel = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]
        self.profile_dir = profile_dir
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


    def get_jump_values(self):
        return self.jump_anti, self.jump_clock


    def set_detection_zone(self, for_what="raw prediction"):
        self.detection_zone = []

        input(f"Hover the mouse over the upper left corner of the detection zone for the {for_what}, then hit ENTER.")
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

    
    def adjust_raw_for_green_swap(self, raw_prediction, green_swap):
        if green_swap == 1:
            # For green at 3-9 diamonds, BASE CASE, NO SCATTER CHANGE
            shift = 0
        elif green_swap == 2:
            # For green at 12-6 diamonds
            shift = 9
        elif green_swap == 3:
            # For green at 1.5-7.5 diamonds
            shift = 4
        elif green_swap == 4:
            # For green at 4.5-10.5 diamonds
            shift = -4
        else:
            return None

        length = len(self.european_wheel)
        raw_idx = self.european_wheel.index(raw_prediction)
        new_raw_idx = raw_idx + shift
        if new_raw_idx > (length - 1):
            return self.european_wheel[new_raw_idx % length]
        else:
            return self.european_wheel[new_raw_idx]


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
            self.make_clicks_given_tuned(direction, self.get_tuned_from_raw(direction, raw_prediction))
        

    def make_clicks_given_tuned(self, direction, tuned_predictions):
        if direction != "t":
            for tuned_prediction in tuned_predictions:
                self.m.position = self.number_coords[tuned_prediction]
                self.m.click(Button.left)
            
