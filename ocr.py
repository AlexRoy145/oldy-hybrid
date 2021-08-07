import ctypes
import ctypes.util
import cv2
import mss
import multiprocessing as mp
import os.path
import pickle
import numpy as np
import time
import PIL.ImageOps
from collections import deque
from PIL import Image
from pytessy import PyTessy
from ball_sample_work_in_progress import BallSample
from ball import Ball
from rotor import Rotor
from util import Util
from detection_zone import SetDetection

BALL_FILE = "crm_saved_profiles/ball_small.png"

MOST_RECENT_SPIN_COUNT = 10


class OCR:

    def __init__(self, profile_dir):
        self.wheel_detection_zone = []
        self.sample_detection_zone = []
        self.wheel_center_point = None
        self.reference_diamond_point = None
        self.ball_detection_zone = None
        self.winning_number_detection_zone = None

        self.time_for_stable_direction = 1.5  # seconds

        self.ball_fall_detection_zone = None

        # used for typing out to anydesk
        self.most_recent_timings = []

        # diamond isolation testing
        self.diamond_target_time = 600
        self.diamond_target_time_tolerance = 50
        self.diamond_targeting_button_zone = []

        self.screenshot_zone = []
        self.dealer_name_zone = []
        self.diff_thresh = 0
        self.wheel_detection_area = 0
        self.rotor_acceleration = -.127  # degrees per second per second
        self.rotor_angle_ellipse = 150

        self.profile_dir = profile_dir

        self.ball_sample = BallSample()

        self.most_recent_spin_data = deque(maxlen=MOST_RECENT_SPIN_COUNT)

        self.is_running = True
        self.databot_mode = False
        self.start_ball_timings = False
        self.p = PyTessy()
        self.data_file = None
        self.winning_number = None
        self.green_calculated_offset = None
        self.raw = None
        self.direction = None
        self.rotor_speed = None
        self.fall_zone = None
        self.ball_revs = None
        self.quit = None

    def load_profile(self, data_file):
        path = os.path.join(self.profile_dir, data_file)
        self.data_file = data_file
        if os.path.isfile(path):
            with open(path, "rb") as f:
                self.__dict__.update(pickle.load(f))
            return True
        else:
            return False

    def save_profile(self, data_file):
        self.data_file = data_file
        path = os.path.join(self.profile_dir, data_file)
        with open(path, "wb") as f:
            d = {"wheel_detection_zone": self.wheel_detection_zone,
                 "wheel_center_point": self.wheel_center_point,
                 "sample_detection_zone": self.sample_detection_zone,
                 "winning_number_detection_zone": self.winning_number_detection_zone,
                 "reference_diamond_point": self.reference_diamond_point,
                 "time_for_stable_direction": self.time_for_stable_direction,
                 "ball_detection_zone": self.ball_detection_zone,
                 "dealer_name_zone": self.dealer_name_zone,
                 "screenshot_zone": self.screenshot_zone,
                 "diff_thresh": self.diff_thresh,
                 "wheel_detection_area": self.wheel_detection_area,
                 "rotor_acceleration": self.rotor_acceleration,
                 "rotor_angle_ellipse": self.rotor_angle_ellipse,
                 "ball_fall_detection_zone": self.ball_fall_detection_zone,
                 "ball_sample": self.ball_sample,
                 "most_recent_spin_data": self.most_recent_spin_data,
                 "diamond_target_time": self.diamond_target_time,
                 "diamond_targeting_button_zone": self.diamond_targeting_button_zone}
            pickle.dump(d, f)

    def set_ball_detection_zone(self):
        self.ball_detection_zone = SetDetection.set_ball_detection_zone(self.wheel_detection_zone)

    def set_wheel_detection_zone(self):
        params = SetDetection.set_wheel_detection_zone()
        self.wheel_detection_zone = params["wheel_detection_zone"]
        self.reference_diamond_point = params["reference_diamond_point"]
        self.diff_thresh = params["diff_thresh"]
        self.wheel_detection_area = params["wheel_detection_area"]

    def set_ball_fall_detection_zone(self):
        params = SetDetection.set_ball_fall_detection_zone(self.wheel_detection_zone)
        self.ball_fall_detection_zone = params["ball_fall_detection_zone"]
        self.wheel_center_point = params["wheel_center_point"]

    def set_sample_detection_zone(self):
        self.sample_detection_zone = SetDetection.set_sample_detection_zone()

    def set_winning_number_detection_zone(self):
        self.winning_number_detection_zone = SetDetection.set_winning_number_detection_zone(self.wheel_detection_zone)

    def set_screenshot_zone(self):
        self.screenshot_zone = SetDetection.set_screenshot_zone()

    def set_dealer_name_zone(self):
        self.dealer_name_zone = SetDetection.set_dealer_name_zone()

    def set_diamond_targeting_button_zone(self):
        self.diamond_targeting_button_zone = SetDetection.set_diamond_targeting_button_zone()

    def start_capture(self):
        try:
            rotor_out_queue = mp.Queue()
            rotor_in_queue = mp.Queue()
            ball_out_queue = mp.Queue()
            ball_in_queue = mp.Queue()
            rotor_proc = mp.Process(target=Rotor.start_capture, args=(
                rotor_in_queue, rotor_out_queue, self.wheel_detection_zone, self.wheel_detection_area,
                self.wheel_center_point, self.reference_diamond_point, self.diff_thresh, self.rotor_angle_ellipse,
                self.time_for_stable_direction))
            rotor_proc.start()
            if self.databot_mode:
                ball_proc = mp.Process(target=Ball.start_capture_databot, args=(
                    ball_in_queue, ball_out_queue, self.ball_sample, self.ball_detection_zone,
                    self.ball_fall_detection_zone, self.wheel_center_point, self.reference_diamond_point))
            else:
                ball_proc = mp.Process(target=Ball.start_capture, args=(
                    ball_in_queue, ball_out_queue, self.ball_sample, self.ball_detection_zone,
                    self.ball_fall_detection_zone, self.wheel_center_point, self.reference_diamond_point,
                    self.diamond_target_time, self.diamond_targeting_button_zone))
            ball_proc.start()

            direction = ""
            spin_start_time = 0
            rotor_done = False
            ball_done = False
            raw_calculated = False
            self.start_ball_timings = False
            self.raw = -1
            self.direction = ""
            self.rotor_speed = -1
            self.winning_number = -1
            self.fall_zone = -1
            self.ball_revs = -1

            bbox = self.wheel_detection_zone
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]

            with mss.mss() as sct:

                # wait until we get the direction change stable state
                while self.is_running:
                    frame = sct.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon": 0})

                    rotor_in_queue.put({"state": "", "frame": frame})
                    ball_in_queue.put({"state": "", "frame": frame})

                    if not rotor_out_queue.empty():
                        out_msg = rotor_out_queue.get()
                        if out_msg["state"] == "direction_change_stable":
                            direction = out_msg["direction"]
                            # automatically start ball timings if databot mode
                            if self.databot_mode:
                                self.start_ball_timings = True
                            break

                if not self.is_running:
                    rotor_in_queue.put({"state": "quit"})
                    ball_in_queue.put({"state": "quit"})
                    rotor_proc.join()
                    rotor_proc.close()
                    if ball_proc:
                        ball_proc.join()
                        ball_proc.close()
                    self.quit = True
                    return

                # start the ball process and wait until calculations are done
                while self.is_running:
                    frame = sct.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon": 0})

                    if self.start_ball_timings and spin_start_time == 0:
                        spin_start_time = time.time()
                        ball_in_queue.put({"state": "", "frame": frame, "spin_start_time": spin_start_time,
                                           "start_ball_timings": True, "direction": direction})

                    elif self.start_ball_timings:
                        ball_in_queue.put(
                            {"state": "", "frame": frame, "start_ball_timings": True, "direction": direction})

                    else:
                        ball_in_queue.put({"state": "", "frame": frame})

                    rotor_in_queue.put({"state": "", "frame": frame})

                    # now wait until rotor calculation and ball fall calculations are complete

                    if not rotor_out_queue.empty():
                        rotor_out_msg = rotor_out_queue.get()
                        if rotor_out_msg["state"] == "rotor_measure_complete":
                            rotor_speed = rotor_out_msg["rotor_speed"]
                            rotor_done = True
                        else:
                            print(f"Unexpected rotor message: {rotor_out_msg}")

                    if not ball_out_queue.empty():
                        ball_out_msg = ball_out_queue.get()

                        if self.databot_mode:
                            # at this point, we have just about everything to calculate things for databot,
                            # so the rest of the code won't execute
                            if ball_out_msg["state"] == "failed_detect":
                                print("Failed to detect ball, restarting state...")
                                ball_in_queue.put({"state": "quit"})
                                rotor_in_queue.put({"state": "quit"})
                                self.quit = True
                                return
                            fall_point = ball_out_msg["fall_point"]
                            ball_revs = ball_out_msg["ball_revs"]
                            rotor_in_queue.put({"state": "ball_fell", "frame": frame})

                            while True:
                                # wait for the rotor to come back with position
                                if not rotor_out_queue.empty():
                                    rotor_out_msg = rotor_out_queue.get()
                                    green_position = rotor_out_msg["green_position"]

                                    # get the TRUE raw
                                    green_offset = Util.get_angle(green_position, self.wheel_center_point,
                                                                  self.reference_diamond_point)
                                    ratio = int(round((green_offset / 360) * len(Util.EUROPEAN_WHEEL)))
                                    if ratio == len(Util.EUROPEAN_WHEEL):
                                        ratio = 0
                                    true_raw = Util.EUROPEAN_WHEEL[ratio]
                                    break

                            wait_for_winning_number = 7  # seconds
                            time.sleep(wait_for_winning_number)

                            # do template matching to get winning number
                            frame = sct.grab(
                                {"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon": 0})
                            frame_img = Image.frombytes('RGB', frame.size, frame.rgb)
                            frame_img = np.array(frame_img)

                            gray = cv2.cvtColor(frame_img, cv2.COLOR_BGR2GRAY)
                            gray = cv2.GaussianBlur(gray, (11, 11), 0)

                            gray = np.bitwise_and(gray, self.winning_number_detection_zone.mask)
                            ball_template = cv2.imread(BALL_FILE, 0)
                            w, h = ball_template.shape[::-1]
                            res = cv2.matchTemplate(gray, ball_template, cv2.TM_SQDIFF)
                            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                            top_left = min_loc
                            bottom_right = (top_left[0] + w, top_left[1] + h)
                            ball_center = (int(round((top_left[0] + bottom_right[0]) / 2)),
                                           int(round((top_left[1] + bottom_right[1]) / 2)))

                            # reset ball detection zone reference frame
                            self.ball_fall_detection_zone.process_reference_frame(frame)
                            self.ball_fall_detection_zone.mask_reference_frame()
                            self.ball_detection_zone.process_reference_frame(frame)
                            self.ball_detection_zone.mask_reference_frame()

                            # pass the same frame into the rotor to get the green position
                            rotor_in_queue.put({"state": "winning_number", "frame": frame})
                            while self.is_running:
                                if not rotor_out_queue.empty():
                                    rotor_out_msg = rotor_out_queue.get()
                                    green_position = rotor_out_msg["green_position"]

                                    # get the winning number using angles
                                    green_offset = Util.get_angle(green_position, self.wheel_center_point, ball_center)
                                    ratio = int(round(green_offset / 360 * len(Util.EUROPEAN_WHEEL)))
                                    if ratio == len(Util.EUROPEAN_WHEEL):
                                        ratio = 0
                                    winning_number = Util.EUROPEAN_WHEEL[ratio]
                                    '''
                                    cv2.circle(frame_img, ball_center, 5, (0, 0, 255), -1)
                                    cv2.circle(frame_img, green_position, 5, (0, 0, 255), -1)
                                    cv2.circle(frame_img, self.wheel_center_point, 5, (0, 0, 255), -1)
                                    cv2.imshow("framee", frame_img)
                                    cv2.waitKey(0)
                                    '''
                                    break

                            # kill the rotor and ball procs
                            rotor_in_queue.put({"state": "quit"})
                            ball_in_queue.put({"state": "quit"})

                            # calculate fall angle. Degrees are relative to reference diamond
                            reference_point = self.reference_diamond_point
                            fall_angle = int(
                                round(Util.get_angle(fall_point, self.wheel_center_point, reference_point)))

                            # update the variables main thread is listening for
                            self.raw = true_raw
                            self.rotor_speed = rotor_speed
                            self.direction = direction
                            self.winning_number = winning_number
                            self.fall_zone = fall_angle
                            self.ball_revs = ball_revs
                            time.sleep(5)
                            return

                        ball_done = True

                    if rotor_done and ball_done:
                        break

                if not self.is_running:
                    rotor_in_queue.put({"state": "quit"})
                    ball_in_queue.put({"state": "quit"})
                    rotor_proc.join()
                    rotor_proc.close()
                    if ball_proc:
                        ball_proc.join()
                        ball_proc.close()
                    self.quit = True
                    return

                while self.is_running:
                    frame = sct.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon": 0})
                    ball_in_queue.put({"state": "", "frame": frame})
                    rotor_in_queue.put({"state": "", "frame": frame})

                    if not raw_calculated:
                        # all information is present so we can now calculate raw
                        rotor_start_point = rotor_out_msg["rotor_start_point"]
                        rotor_end_point = rotor_out_msg["rotor_end_point"]
                        rotor_measure_complete_timestamp = rotor_out_msg["rotor_measure_complete_timestamp"]
                        rotor_measure_duration = rotor_out_msg["rotor_measure_duration"]
                        rotor_speed = rotor_out_msg["rotor_speed"]
                        degrees = rotor_out_msg["degrees"]

                        if ball_out_msg["state"] == "false_detections":
                            # destroy everything
                            rotor_in_queue.put({"state": "quit"})
                            ball_in_queue.put({"state": "quit"})
                            self.quit = True
                            return

                        # '''
                        if "a" in direction:
                            samples = self.ball_sample.samples_anti
                        else:
                            samples = self.ball_sample.samples_clock
                        # '''
                        # samples = self.ball_sample.samples

                        if len(samples) > 0:
                            fall_time = ball_out_msg["fall_time"]
                            fall_time_timestamp = ball_out_msg["fall_time_timestamp"]

                            diff_between_fall_timestamp_and_rotor_timestamp = fall_time_timestamp - \
                                                                              rotor_measure_complete_timestamp
                            # converting fall time mS to seconds
                            fall_time_from_now = fall_time / 1000 + diff_between_fall_timestamp_and_rotor_timestamp

                            params = Util.calculate_rotor(direction, rotor_end_point, degrees, rotor_measure_duration,
                                                          fall_time_from_now, self.reference_diamond_point,
                                                          self.rotor_acceleration, self.wheel_center_point)
                            raw = params["raw"]
                            self.green_calculated_offset = params["green_calculated_offset"]
                            self.raw = raw
                            self.direction = direction
                            self.rotor_speed = rotor_speed
                            raw_calculated = True

                            # tell the rotor when the fall time is so it can capture the true raw at expected fall time
                            # rotor_in_queue.put({"state" : "ball_info", "fall_time" : fall_time, "fall_time_timestamp"
                            # : fall_time_timestamp, "frame" : frame})
                        else:
                            rotor_in_queue.put({"state": "quit"})
                            ball_in_queue.put({"state": "quit"})
                            rotor_proc.join()
                            rotor_proc.close()
                            if ball_proc:
                                ball_proc.join()
                                ball_proc.close()
                            self.quit = True
                            return

                    # while self.is_running:
                    if not ball_out_queue.empty():
                        ball_out_msg = ball_out_queue.get()
                        if ball_out_msg["state"] == "ball_fell":
                            rotor_in_queue.put({"state": "ball_fell", "frame": frame})

                            while True:
                                # wait for the rotor to come back with position
                                if not rotor_out_queue.empty():
                                    rotor_out_msg = rotor_out_queue.get()
                                    green_position = rotor_out_msg["green_position"]

                                    # get the TRUE raw
                                    green_offset = Util.get_angle(green_position, self.wheel_center_point,
                                                                  self.reference_diamond_point)
                                    ratio = int(round((green_offset / 360) * len(Util.EUROPEAN_WHEEL)))
                                    if ratio == len(Util.EUROPEAN_WHEEL):
                                        ratio = 0
                                    true_raw = Util.EUROPEAN_WHEEL[ratio]
                                    print(f"TRUE RAW: {true_raw}")

                                    true_raw_idx = Util.EUROPEAN_WHEEL.index(true_raw)
                                    predicted_raw_idx = Util.EUROPEAN_WHEEL.index(raw)
                                    diff = abs(true_raw_idx - predicted_raw_idx)
                                    if diff > 18:
                                        diff = len(Util.EUROPEAN_WHEEL) - diff
                                    print(f"Predicted raw was {diff} pockets off.")

                                    break

                        elif ball_out_msg["state"] == "ball_update":
                            current_ball_sample = ball_out_msg["current_ball_sample"]
                            fall_zone = ball_out_msg["fall_point"]

                            # calculate fall angle. Degrees are relative to reference diamond
                            reference_point = self.reference_diamond_point
                            self.fall_zone = int(
                                round(Util.get_angle(fall_zone, self.wheel_center_point, reference_point)))

                            self.ball_revs = ball_out_msg["ball_revs"]

                            # TODO don't update with using steve's default sample
                            self.ball_sample.update_sample(current_ball_sample, direction)
                            # self.ball_sample.update_sample(current_ball_sample)
                            print(f"Sample: {current_ball_sample}")
                            self.most_recent_timings = current_ball_sample
                            self.save_profile(self.data_file)

                            '''
                            # at this point, everything is officially over
                            rotor_in_queue.put({"state" : "quit"})
                            ball_in_queue.put({"state" : "quit"})
                            self.quit = True
                            return
                            '''
                            # break
                            rotor_in_queue.put({"state": "quit"})
                            ball_in_queue.put({"state": "quit"})
                            rotor_proc.join()
                            rotor_proc.close()
                            if ball_proc:
                                ball_proc.join()
                                ball_proc.close()
                            self.quit = True
                            return

                    '''
                    if not rotor_out_queue.empty():
                        # ROTOR ACCURACY EVALUATION
                        true_green_position = rotor_out_queue.get()["green_position"]
                        true_green_offset = Util.get_angle(true_green_position, self.wheel_center_point, 
                        self.reference_diamond_point)
                        degrees_off = abs(true_green_offset - self.green_calculated_offset)
                        if degrees_off >= 180:
                            pockets_off = int(round((360 - degrees_off) / (360 / len(Util.EUROPEAN_WHEEL))))
                        else:
                            pockets_off = abs(int(round(degrees_off / (360 / len(Util.EUROPEAN_WHEEL)))))
                        print(f"Raw prediction was {pockets_off} pockets off of the TRUE raw.")
                    '''

                if not self.is_running:
                    rotor_in_queue.put({"state": "quit"})
                    ball_in_queue.put({"state": "quit"})
                    rotor_proc.join()
                    rotor_proc.close()
                    if ball_proc:
                        ball_proc.join()
                        ball_proc.close()
                    self.quit = True
                    return



        except mss.exception.ScreenShotError:
            print(f"THREADING ERROR!! You need to quit the detection loop!")

        cv2.destroyAllWindows()

    def read(self, test=False, capture=None, zone=None, get_letters=False, pageseg=5, invert=False):
        if not zone:
            zone = self.raw_detection_zone
        now = time.time()
        bbox = zone
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        if capture:
            sct_img = capture.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon": 0})
        else:
            try:
                with mss.mss() as sct:
                    sct_img = sct.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon": 0})
            except mss.exception.ScreenShotError:
                print("Threading issue!!! Close detection thread?")
                return None
        pil_image = Image.frombytes('RGB', sct_img.size, sct_img.rgb)
        if invert:
            pil_image = PIL.ImageOps.invert(pil_image)
        open_cv_image = np.array(pil_image)
        open_cv_image = open_cv_image[:, :, ::-1].copy()
        finalimage = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        ret, thresholded = cv2.threshold(finalimage, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if test:
            cv2.imshow("captured image", thresholded)
            cv2.waitKey(0)

        finalimage = thresholded
        end = time.time()

        now_2 = time.time()
        prediction = self.p.read(finalimage.ctypes, finalimage.shape[1], finalimage.shape[0], 1, pageseg=pageseg)
        end_2 = time.time()

        if not get_letters:
            prediction = self.post_process(prediction)

        return prediction

    def take_screenshot(self, filename):
        bbox = self.screenshot_zone
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        with mss.mss() as sct:
            sct_img = sct.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon": 0})

        pil_image = Image.frombytes('RGB', sct_img.size, sct_img.rgb)
        pil_image.save(filename)

    @staticmethod
    def post_process(prediction):
        if prediction:
            prediction = prediction.replace("s", "5")
            prediction = prediction.replace("S", "5")
            prediction = prediction.replace("$", "5")

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

    @staticmethod
    def is_valid_prediction(raw_prediction):
        try:
            raw_prediction = int(raw_prediction)
        except (ValueError, TypeError) as e:
            return False

        if raw_prediction < 0 or raw_prediction > 36:
            return False

        return True

    def show_ball_samples(self, direction):
        if "a" in direction:
            samples = self.ball_sample.samples_anti
            averaged_sample = self.ball_sample.averaged_sample_anti
        else:
            samples = self.ball_sample.samples_clock
            averaged_sample = self.ball_sample.averaged_sample_clock
        # samples = self.ball_sample.samples
        # averaged_sample = self.ball_sample.averaged_sample

        for i, sample in enumerate(samples):
            print(f"Sample #{i}: {sample}")
            print(f"Adjusted Sample #{i}: {sample.adjusted_sample}")
            print()
        print(f"Averaged sample: {averaged_sample.adjusted_sample}")

        '''
        for i, sample in enumerate(samples):
            slope = []
            for j in range(len(sample.adjusted_sample) - 1):
                slope.append(sample.adjusted_sample[j+1] - sample.adjusted_sample[j])
            print(f"Sample #{i} Slopes: {slope}")
        '''

    '''
    def show_ball_samples(self):
        samples = self.ball_sample.samples
        averaged_sample = self.ball_sample.averaged_sample
        
        for i, sample in enumerate(samples):
            print(f"Sample #{i}: {sample}")
            print(f"Adjusted Sample #{i}: {sample.adjusted_sample}")
            print()
        print(f"Averaged sample: {averaged_sample.adjusted_sample}")
    '''

    def delete_ball_sample(self, idx, direction):
        if "a" in direction:
            samples = self.ball_sample.samples_anti
        else:
            samples = self.ball_sample.samples_clock

        try:
            del samples[idx]
            # self.ball_sample.update_averaged_sample()
        except IndexError:
            print("That sample doesn't exist.")

        self.ball_sample.update_averaged_sample(direction)
        # self.ball_sample.update_averaged_sample()
        self.save_profile(self.data_file)

    '''
    def delete_ball_sample(self, idx):
        samples = self.ball_sample.samples
        try:
            del samples[idx]
        except IndexError:
            print("That sample doesn't exist.")

        self.ball_sample.update_averaged_sample()
        self.save_profile(self.data_file)
    '''

    def add_ball_sample(self, sample, direction):
        self.ball_sample.update_sample(sample, direction)
        self.save_profile(self.data_file)

    '''
    def add_ball_sample(self, sample):
        self.ball_sample.update_sample(sample)
        self.save_profile(self.data_file)
    '''

    def change_vps(self, vps, direction):
        self.ball_sample.change_vps(vps, direction)
        self.save_profile(self.data_file)

    '''
    def change_vps(self, vps):
        self.ball_sample.change_vps(vps)
        self.save_profile(self.data_file)
    '''

    def change_max_samples(self, new_max_samples, direction):
        if "a" in direction:
            max_samples = self.ball_sample.max_samples_anti
        else:
            max_samples = self.ball_sample.max_samples_clock

        if new_max_samples != max_samples:
            self.ball_sample.change_max_samples(new_max_samples, direction)

        self.save_profile(self.data_file)

    '''
    def change_max_samples(self, new_max_samples):
        max_samples = self.ball_sample.max_samples

        if new_max_samples != max_samples:
            self.ball_sample.change_max_samples(new_max_samples)

        self.save_profile(self.data_file)
    '''

    def graph_samples(self, direction):
        self.ball_sample.graph_samples(direction)

    '''
    def graph_samples(self):
        self.ball_sample.graph_samples()
    '''

    def scan_sample(self):
        """
        # not needed
        return
        """
        sample = self.read(zone=self.sample_detection_zone).split("\n")
        parsed_sample = []

        try:
            for rev in sample:
                if rev != "\n" and rev != "":
                    parsed_sample.append(rev)

            sample_str = ""
            for rev in parsed_sample:
                sample_str += f"{rev}, "

            print(f"Scanned sample: {sample_str}")
            parsed_sample = [int(x) for x in parsed_sample]
            self.add_ball_sample(parsed_sample, "anticlockwise")
            self.add_ball_sample(parsed_sample, "clockwise")
        except ValueError:
            print(
                f"There is an error in the sample. Either reset detection zone, or manually copy the above sample "
                f"and add it manually with AS")
