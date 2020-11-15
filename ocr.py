import ctypes
import ctypes.util
import cv2
import math
import mss
import multiprocessing as mp
import os.path
import pickle
import numpy as np
import time
from pynput import mouse
from collections import deque
from PIL import Image
from pytessy import PyTessy
from ball_sample import BallSample
from ball import Ball 
from rotor import Rotor

class OCR:

    def __init__(self, profile_dir):
        self.wheel_detection_zone = []
        self.wheel_center_point = None
        self.reference_diamond_point = None
        self.ball_detection_zone = []
        self.relative_ball_detection_zone = []
        self.screenshot_zone = []
        self.diff_thresh = 0
        self.wheel_detection_area = 0
        self.rotor_acceleration = -.127 # degrees per second per second
        
        self.m = mouse.Controller()
        self.profile_dir = profile_dir

        self.ball_sample = BallSample()

        self.is_running = True
        self.set_rotor_acceleration = False
        self.start_ball_timings = False
        self.p = PyTessy()

        self.european_wheel = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]


    def load_profile(self, data_file):
        path = os.path.join(self.profile_dir, data_file)
        self.rotor_acceleration = -.127
        if os.path.isfile(path):
            with open(path, "rb") as f:
                self.__dict__.update(pickle.load(f))
            return True
        else:
            return False


    def save_profile(self, data_file):
        path = os.path.join(self.profile_dir, data_file)
        with open(path, "wb") as f:
            d = {"wheel_detection_zone" : self.wheel_detection_zone,
                 "wheel_center_point" : self.wheel_center_point,
                 "reference_diamond_point" : self.reference_diamond_point,
                 "ball_detection_zone" : self.ball_detection_zone,
                 "relative_ball_detection_zone" : self.relative_ball_detection_zone,
                 "screenshot_zone" : self.screenshot_zone,
                 "diff_thresh" : self.diff_thresh,
                 "wheel_detection_area" : self.wheel_detection_area,
                 "rotor_acceleration" : self.rotor_acceleration,
                 "ball_sample" : self.ball_sample}
            pickle.dump(d, f)

    
    def set_ball_detection_zone(self):
        self.ball_detection_zone = []
        zone = self.ball_detection_zone
        input(f"Hover the mouse over the upper left corner of the detection zone for the BALL, then hit ENTER.")
        x_top,y_top = self.m.position
        zone.append(x_top)
        zone.append(y_top)

        input("Hover the mouse over the bottom right corner of the detection zone, then hit ENTER.")
        x_bot,y_bot = self.m.position
        zone.append(x_bot)
        zone.append(y_bot)

        print(f"Bounding box: {zone}")

        # get the coords for within the context of wheel detection zone
        new_ball_leftupper_x = self.ball_detection_zone[0] - self.wheel_detection_zone[0]
        new_ball_leftupper_y = self.ball_detection_zone[1] - self.wheel_detection_zone[1]
        new_ball_rightbottom_x = self.ball_detection_zone[2] - self.wheel_detection_zone[0]
        new_ball_rightbottom_y = self.ball_detection_zone[3] - self.wheel_detection_zone[1]

        self.relative_ball_detection_zone = [new_ball_leftupper_x, new_ball_leftupper_y, new_ball_rightbottom_x, new_ball_rightbottom_y]


    def set_wheel_detection_zone(self):
        self.wheel_detection_zone = []
        zone = self.wheel_detection_zone
        input(f"Hover the mouse over the upper left corner of the detection zone for the WHEEL, then hit ENTER.")
        x_top,y_top = self.m.position
        zone.append(x_top)
        zone.append(y_top)

        input("Hover the mouse over the bottom right corner of the detection zone, then hit ENTER.")
        x_bot,y_bot = self.m.position
        zone.append(x_bot)
        zone.append(y_bot)

        print(f"Bounding box: {zone}")

        input(f"Hover the mouse over the EXACT CENTER of the wheel, then hit ENTER.")
        x_center,y_center = self.m.position
        x_center -= self.wheel_detection_zone[0]
        y_center -= self.wheel_detection_zone[1]
        self.wheel_center_point = x_center,y_center


        input(f"Hover the mouse over the the center of the pocket RIGHT UNDER the REFERENCE DIAMOND, then hit ENTER.")
        x_ref,y_ref = self.m.position
        x_ref -= self.wheel_detection_zone[0]
        y_ref -= self.wheel_detection_zone[1]
        self.reference_diamond_point = x_ref, y_ref



        self.diff_thresh = int((self.wheel_detection_zone[2] - self.wheel_detection_zone[0]) / OCR.DIFF_RATIO)
        print(f"diff_thresh: {self.diff_thresh}")
        bbox = self.wheel_detection_zone
        width = bbox[2]-bbox[0]
        height = bbox[3]-bbox[1]

        self.wheel_detection_area = width * height


    def set_screenshot_zone(self):
        self.screenshot_zone = []
        zone = self.screenshot_zone
        input(f"Hover the mouse over the upper left corner for where to take a screenshot (betting board + acct balance), then hit ENTER.")
        x_top,y_top = self.m.position
        zone.append(x_top)
        zone.append(y_top)

        input("Hover the mouse over the bottom right corner of the screenshot area, then hit ENTER.")
        x_bot,y_bot = self.m.position
        zone.append(x_bot)
        zone.append(y_bot)

        print(f"Bounding box: {zone}")


    def start_capture(self):
        try:
            rotor_out_queue = mp.Queue()
            rotor_in_queue = mp.Queue()
            ball_out_queue = mp.Queue()
            ball_in_queue = mp.Queue()
            rotor_proc = mp.Process(target=Rotor.start_capture, args=(rotor_in_queue, rotor_out_queue, self.wheel_detection_zone, self.wheel_detection_area, self.wheel_center_point, self.reference_diamond_point, self.diff_thresh))
            rotor_proc.start()
            ball_proc = None

            direction = ""
            spin_start_time = 0
            rotor_done = False
            ball_done = False
            raw_calculated = False
            self.start_ball_timings = False
            self.raw = -1
            self.direction = ""

            bbox = self.wheel_detection_zone
            width = bbox[2]-bbox[0]
            height = bbox[3]-bbox[1]

            with mss.mss() as sct:

                # wait until we get the direction change stable state
                while self.is_running:
                    frame = sct.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon":0})
                    
                    rotor_in_queue.put({"state" : "", "frame" : frame})

                    if not rotor_out_queue.empty():
                        out_msg = rotor_out_queue.get()
                        if out_msg["state"] == "direction_change_stable":
                            direction = out_msg["direction"]
                            break

                if not self.is_running:
                    rotor_in_queue.put({"state" : "quit"})
                    ball_in_queue.put({"state" : "quit"})
                    rotor_proc.join()
                    if ball_proc:
                        ball_proc.join()
                    rotor_proc.close()
                    self.quit = True
                    return


                # start the ball process and wait until calculations are done
                while self.is_running:
                    frame = sct.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon":0})

                    rotor_in_queue.put({"state" : "", "frame" : frame})
                    
                    # start the ball process now
                    if self.start_ball_timings and spin_start_time == 0:
                        spin_start_time = time.time()
                        ball_proc = mp.Process(target=Ball.start_capture, args=(ball_in_queue, ball_out_queue, self.relative_ball_detection_zone, self.ball_sample, spin_start_time))
                        ball_proc.start()
                        ball_in_queue.put({"state" : "", "frame" : frame})
                    elif self.start_ball_timings:
                        ball_in_queue.put({"state" : "", "frame" : frame})

                    # now wait until rotor calculation and ball fall calculations are complete
                    
                    if not rotor_out_queue.empty():
                        rotor_out_msg = rotor_out_queue.get()
                        rotor_done = True
                    
                    if not ball_out_queue.empty():
                        ball_out_msg = ball_out_queue.get()
                        ball_done = True

                    if rotor_done and ball_done:
                        break

                if not self.is_running:
                    rotor_in_queue.put({"state" : "quit"})
                    ball_in_queue.put({"state" : "quit"})
                    rotor_proc.join()
                    if ball_proc:
                        ball_proc.join()
                    self.quit = True
                    return


                while self.is_running:
                    frame = sct.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon":0})
                    ball_in_queue.put({"state" : "", "frame" : frame})

                    if not raw_calculated:
                        # all information is present so we can now calculate raw
                        rotor_start_point = rotor_out_msg["rotor_start_point"]
                        rotor_end_point = rotor_out_msg["rotor_end_point"]
                        rotor_measure_complete_timestamp = rotor_out_msg["rotor_measure_complete_timestamp"]
                        rotor_measure_duration = rotor_out_msg["rotor_measure_duration"]
                        degrees = rotor_out_msg["degrees"]

                        if ball_out_msg["state"] == "false_detections":
                            # destroy everything
                            rotor_in_queue.put({"state" : "quit"})
                            ball_in_queue.put({"state" : "quit"})
                            self.quit = True
                            return

                        fall_time = ball_out_msg["fall_time"]
                        fall_time_timestamp = ball_out_msg["fall_time_timestamp"]

                        diff_between_fall_timestamp_and_rotor_timestamp = fall_time_timestamp - rotor_measure_complete_timestamp
                        # converting fall time mS to seconds
                        fall_time_from_now = fall_time / 1000 + diff_between_fall_timestamp_and_rotor_timestamp

                        raw = self.calculate_rotor(direction, rotor_end_point, degrees, rotor_measure_duration, fall_time_from_now)
                        self.raw = raw
                        self.direction = direction
                        raw_calculated = True

                    if not ball_out_queue.empty():
                        ball_out_msg = ball_out_queue.get()
                        if ball_out_msg["state"] == "ball_update":
                            current_ball_sample = ball_out_msg["current_ball_sample"]
                            self.ball_sample.update_sample(current_ball_sample)

                            # at this point, everything is officially over
                            rotor_in_queue.put({"state" : "quit"})
                            ball_in_queue.put({"state" : "quit"})
                            self.quit = True
                            rotor_proc.join()
                            if ball_proc:
                                ball_proc.join()
                            return

                if not self.is_running:
                    rotor_in_queue.put({"state" : "quit"})
                    ball_in_queue.put({"state" : "quit"})
                    rotor_proc.join()
                    if ball_proc:
                        ball_proc.join()
                    self.quit = True
                    return


                    
        except mss.exception.ScreenShotError:
            print(f"THREADING ERROR!! You need to quit the detection loop!")

        cv2.destroyAllWindows()


    def capture_rotor_acceleration(self):
        try:
            rotor_out_queue = mp.Queue()
            rotor_in_queue = mp.Queue()
            rotor_proc = mp.Process(target=Rotor.measure_rotor_acceleration, args=(rotor_in_queue, rotor_out_queue, self.wheel_detection_zone, self.wheel_detection_area, self.wheel_center_point, self.reference_diamond_point, self.diff_thresh))
            rotor_proc.start()

            bbox = self.wheel_detection_zone
            width = bbox[2]-bbox[0]
            height = bbox[3]-bbox[1]

            with mss.mss() as sct:

                while True:
                    frame = sct.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon":0})
                    
                    rotor_in_queue.put({"state" : "", "frame" : frame})

                    if not rotor_out_queue.empty():
                        out_msg = rotor_out_queue.get()
                        if out_msg["state"] == "done":
                            self.rotor_acceleration = out_msg["acceleration"]
                            print(f"Set rotor acceleration to {self.rotor_acceleration}.")
                            return

        except mss.exception.ScreenShotError:
            print(f"THREADING ERROR!! You need to quit the detection loop!")

        cv2.destroyAllWindows()



    def read(self, test=False, capture=None, zone=None):
        if not zone:
            zone = self.raw_detection_zone
        now = time.time()
        bbox = zone
        width = bbox[2]-bbox[0]
        height = bbox[3]-bbox[1]
        if capture:
            sct_img = capture.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon":0})
        else:
            try:
                with mss.mss() as sct:
                    sct_img = sct.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon":0})
            except mss.exception.ScreenShotError:
                print("Threading issue!!! Close detection thread?")
                return None
        pil_image = Image.frombytes('RGB', sct_img.size, sct_img.rgb)
        open_cv_image = np.array(pil_image)
        open_cv_image = open_cv_image[:, :, ::-1].copy() 
        finalimage = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        ret,thresholded = cv2.threshold(finalimage, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
        if test:
            cv2.imshow("captured image", thresholded)
            cv2.waitKey(0)



        finalimage = thresholded
        end = time.time()

        now_2 = time.time()
        prediction = self.p.read(finalimage.ctypes, finalimage.shape[1], finalimage.shape[0], 1) 
        end_2 = time.time()

        prediction = self.post_process(prediction)

        return prediction

    
    def take_screenshot(self, filename):
        bbox = self.screenshot_zone
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        with mss.mss() as sct:
            sct_img = sct.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon":0})

        pil_image = Image.frombytes('RGB', sct_img.size, sct_img.rgb)
        pil_image.save(filename)


    def post_process(self, prediction):
        if prediction:
            prediction = prediction.replace("s", "5")
            prediction = prediction.replace("S", "5")

            prediction = prediction.replace("Z", "2")
            prediction = prediction.replace("z", "2")

            prediction = prediction.replace("l", "1")
            prediction = prediction.replace("L", "1")
            prediciton = prediction.replace("i", "1")

            prediction = prediction.replace("¢", "7")
            prediction = prediction.replace("?", "7")

            prediction = prediction.replace("g", "9")
            prediction = prediction.replace("G", "9")

            prediction = prediction.replace("A", "4")

            prediction = prediction.replace("O", "0")
            prediction = prediction.replace("o", "0")
            prediction = prediction.replace("Q", "0")

            prediction = prediction.replace("a", "8")
            prediction = prediction.replace("B", "8")
            prediction = prediction.replace("&", "8")

        return prediction

    def get_angle(self, a, b, c):
        ang = math.degrees(math.atan2(c[1]-b[1], c[0]-b[0]) - math.atan2(a[1]-b[1], a[0]-b[0]))
        return (ang + 360) if ang < 0 else ang


    def is_valid_prediction(self, raw_prediction):
        try:
            raw_prediction = int(raw_prediction)
        except (ValueError, TypeError) as e:
            return False

        if raw_prediction < 0 or raw_prediction > 36:
            return False

        return True


    def calculate_rotor(self, direction, green_point, degrees, rotor_measure_duration, fall_time_from_now):
        # first get the measured speed of the rotor in degrees/second
        speed = degrees / rotor_measure_duration

        # get the degree offset green is from the reference diamond
        # if degree_offset is less than 180, green is ABOVE reference diamond, assuming ref diamond is to the right
        # if degree_offset is more than 180, green is BELOW reference diamond, assuming ref diamond is to the right
        degree_offset = self.get_angle(green_point, self.wheel_center_point, self.reference_diamond_point)

        # now calculate where the green 0 will be in fall_time_from_now seconds
        degrees_green_travels = (speed * fall_time_from_now + .5 * self.rotor_acceleration * (fall_time_from_now ** 2)) % 360

        if direction == "anticlockwise":
            degree_offset_after_travel = (degree_offset + degrees_green_travels) % 360
        else:
            new_offset = degree_offset - degrees_green_travels
            degree_offset_after_travel = (new_offset + 360) if new_offset < 0 else new_offset

        # degree_offset_after_travel now represents where green is at the moment of ball fall
        # now calculate what number is under the reference diamond
        try:
            if degree_offset_after_travel >= 180:
                # if green is BELOW ref diamond, go to the left of the green to find raw
                ratio_to_look = (360 - degree_offset_after_travel) / 360
                idx = int(round(len(self.european_wheel) * ratio_to_look))
                raw = self.european_wheel[-idx]
            else:
                # if green is ABOVE ref diamond, go to the right of the green to find raw
                ratio_to_look = degree_offset_after_travel / 360
                idx = int(round(len(self.european_wheel) * ratio_to_look))
                raw = self.european_wheel[idx]
        except Exception as e:
            print(f"EXCEPTION: {e}")
            print(f"SPEED: {speed} degrees/second")
            print(f"Duration: {rotor_measure_duration}")
            print(f"degrees measured: {degrees}")
            print(f"degree_offset: {degree_offset}")
            print(f"degrees_green_travels: {degrees_green_travels}")
            print(f"degree_offset_after_travel: {degree_offset_after_travel}")
            print(f"ratio_to_look: {ratio_to_look}")
            print(f"idx: {idx}")

            return 0

        print(f"SPEED: {speed} degrees/second")
        print(f"Duration: {rotor_measure_duration}")
        print(f"degrees measured: {degrees}")
        print(f"degree_offset: {degree_offset}")
        print(f"degrees_green_travels: {degrees_green_travels}")
        print(f"degree_offset_after_travel: {degree_offset_after_travel}")
        print(f"ratio_to_look: {ratio_to_look}")
        print(f"idx: {idx}")

        
        return raw
