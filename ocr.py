import ctypes
import ctypes.util
import cv2
import imutils
import math
import mss
import os.path
import pickle
import numpy as np
import time
import threading
import winsound
from pynput import mouse
from collections import deque
from PIL import Image
from pytessy import PyTessy
from ball_sample import BallSample

class OCR:

    GREEN_LOWER = (29, 86, 6)
    GREEN_UPPER = (64, 255, 255)
    GIVE_UP_LOOKING_FOR_RAW = 10 #seconds
    TIME_FOR_STABLE_DIRECTION = 1.5 #seconds
    MAX_MISDETECTIONS_BEFORE_RESETTING_STATE = 60
    DIFF_RATIO = 9
    MORPH_KERNEL_RATIO = .0005
    LOOKBACK = 20
    DELAY_FOR_RAW_UPDATE = .1
    ROTOR_ANGLE_ELLIPSE = 70

    # BALL VARS
    MIN_BALL_AREA = 100
    MAX_BALL_AREA = 2000
    BALL_START_TIMINGS = 550
    THRESH = 65
    MAX_SPIN_DURATION = 30
    FALSE_DETECTION_THRESH = 100

    def __init__(self, profile_dir):
        self.wheel_detection_zone = []
        self.wheel_center_point = None
        self.reference_diamond_point = None
        self.ball_detection_zone = []
        self.relative_ball_detection_zone = []
        self.screenshot_zone = []
        self.diff_thresh = 0
        self.wheel_detection_area = 0
        self.rotor_acceleration = -3.5 # degrees per second per second
        
        self.p = PyTessy()
        self.m = mouse.Controller()
        self.profile_dir = profile_dir

        self.ball = BallSample()

        self.is_running = True
        self.start_ball_timings = False

        self.european_wheel = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]

        self.raw = -1
        self.direction = ""
        self.quit = False

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
            d = {"wheel_detection_zone" : self.wheel_detection_zone,
                 "wheel_center_point" : self.wheel_center_point,
                 "reference_diamond_point" : self.reference_diamond_point,
                 "ball_detection_zone" : self.ball_detection_zone,
                 "relative_ball_detection_zone" : self.relative_ball_detection_zone,
                 "rotor_acceleration" : self.rotor_acceleration,
                 "screenshot_zone" : self.screenshot_zone,
                 "diff_thresh" : self.diff_thresh,
                 "wheel_detection_area" : self.wheel_detection_area,
                 "ball" : self.ball}
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
        # ROTOR VARS
        pts = deque(maxlen=OCR.LOOKBACK)
        current_direction = ""
        seen_direction_change_start_time = None
        seen_direction_start_time = None

        watch_for_direction_change = False
        direction_change_stable = False
        direction_changed = False
        direction_confirmed = False
        misdetections = 0
        kernel_size = int((OCR.MORPH_KERNEL_RATIO * self.wheel_detection_area)**.5)

        counter = 0
        frames_seen = 0
        bbox = self.wheel_detection_zone
        width = bbox[2]-bbox[0]
        height = bbox[3]-bbox[1]
        wheel_center = self.wheel_center_point
        ref_diamond = self.reference_diamond_point

        # rotor calculation vars
        rotor_start_point = None
        rotor_end_point = None
        rotor_measure_start_time = 0
        rotor_measure_complete_timestamp = 0
        rotor_measure_duration = 0
        degrees = 0

        
        # BALL VARS
        current_ball_sample = []
        first_ball_frame = []
        first_capture = True
        first_pass = True
        start_time = 0
        rev_time = 0
        spin_start_time = 0
        fall_time = -1
        fall_time_timestamp = 0
        did_beep = False
        self.start_ball_timings = False

        try:
            with mss.mss() as sct:
                while self.is_running:
                    frame = sct.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon":0})

                    frame = Image.frombytes('RGB', frame.size, frame.rgb)
                    ball_frame = frame.crop(self.relative_ball_detection_zone)

                    frame = np.array(frame)
                    ball_frame = np.array(ball_frame)


                    # BALL PROCESSING
                    if direction_change_stable and self.start_ball_timings:
                        gray = cv2.cvtColor(ball_frame, cv2.COLOR_BGR2GRAY)
                        gray = cv2.GaussianBlur(gray, (11, 11), 0)
                        if first_capture:
                            first_ball_frame = gray
                            first_capture = False

                        if fall_time > 0:
                            EPSILON = 250
                            elapsed_time = time.time() * 1000 - fall_time_timestamp * 1000
                            if not did_beep and abs(elapsed_time - fall_time) < EPSILON:
                                winsound.Beep(1000, 50)
                                did_beep = True
                            

                        if time.time() - spin_start_time > OCR.MAX_SPIN_DURATION:
                            self.ball.update_sample(current_ball_sample)
                            self.quit = True
                            cv2.destroyAllWindows()
                            return

                        ball_frame_delta = cv2.absdiff(first_ball_frame, gray)
                        ball_thresh = cv2.threshold(ball_frame_delta, OCR.THRESH, 255, cv2.THRESH_BINARY)[1]

                        ball_thresh = cv2.dilate(ball_thresh, None, iterations=2)
                        ball_cnts = cv2.findContours(ball_thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        ball_cnts = imutils.grab_contours(ball_cnts)

                        for c in ball_cnts:
                            area = cv2.contourArea(c)
                            if area < OCR.MIN_BALL_AREA or area > OCR.MAX_BALL_AREA:
                                continue

                            now = int(round(time.time() * 1000))
                            if first_pass:
                                start_time = now
                                first_pass = False
                            else:
                                lap_time = now - start_time

                                if lap_time > OCR.BALL_START_TIMINGS:
                                    start_time = now
                                    print("Ball detected, lap: %dms" % lap_time)
                                    if len(current_ball_sample) > 0:
                                        if current_ball_sample[-1] - lap_time > OCR.FALSE_DETECTION_THRESH:
                                            print("FALSE DETECTIONS")
                                            self.quit = True
                                    current_ball_sample.append(lap_time)
                                    if fall_time < 0:
                                        fall_time = self.ball.get_fall_time(lap_time) 
                                        if fall_time > 0:
                                            fall_time_timestamp = time.time()
                                            print(f"FALL TIME THOUGHT TO BE {fall_time} MS FROM NOW")


                    # ROTOR PROCESSING
                    if not rotor_measure_complete_timestamp:
                        blurred = cv2.GaussianBlur(frame, (11, 11), 0)
                        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

                        mask = cv2.inRange(hsv, OCR.GREEN_LOWER, OCR.GREEN_UPPER)
                        mask = cv2.erode(mask, None, iterations=2)
                        mask = cv2.dilate(mask, None, iterations=2)

                        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size,kernel_size)));

                        cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        cnts = imutils.grab_contours(cnts)


                    center = None
                    if len(cnts) > 0:
                        c = max(cnts, key=cv2.contourArea)
                        ((x, y), radius) = cv2.minEnclosingCircle(c)
                        M = cv2.moments(c)
                        center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
                        # only proceed if the radius meets a minimum size
                        if radius > 10:
                            # draw the circle and centroid on the frame,
                            # then update the list of tracked points
                            cv2.circle(frame, (int(x), int(y)), int(radius),
                                    (0, 255, 255), 2)
                            cv2.circle(frame, center, 5, (0, 0, 255), -1)
                            # update the points queue
                            pts.appendleft(center)
                            
                            if direction_change_stable:
                                if not rotor_start_point:
                                    rotor_start_point = center
                                    rotor_measure_start_time = time.time()
                                elif not rotor_end_point:
                                    # calculate how many degrees have been measured since rotor_start_point
                                    degrees = self.get_angle(rotor_start_point, wheel_center, center)
                                    if degrees > 180:
                                        degrees = 360 - degrees
                                    if degrees >= OCR.ROTOR_ANGLE_ELLIPSE:
                                        rotor_end_point = center
                                        rotor_measure_complete_timestamp = time.time()
                                        rotor_measure_duration = rotor_measure_complete_timestamp - rotor_measure_start_time


                                # if the fall time is valid, get how long it's been since the fall time got recorded then use that time
                                # plus fall time to calculate rotor position
                                elif rotor_start_point and rotor_end_point:
                                    if self.raw == -1 and fall_time > 0:
                                        diff_between_fall_timestamp_and_rotor_timestamp = fall_time_timestamp - rotor_measure_complete_timestamp
                                        # converting fall time mS to seconds
                                        fall_time_from_now = fall_time / 1000 + diff_between_fall_timestamp_and_rotor_timestamp

                                        raw = self.calculate_rotor(current_direction, rotor_end_point, degrees, rotor_measure_duration, ref_diamond, fall_time_from_now)
                                        self.raw = raw
                                        self.direction = current_direction


                        else:
                            misdetections += 1
                    else:
                        misdetections += 1

                    if misdetections > OCR.MAX_MISDETECTIONS_BEFORE_RESETTING_STATE:
                        # completely reset state
                        watch_for_direction_change = False
                        direction_change_stable = False
                        direction_changed = False
                        direction_confirmed = False
                        current_direction = ""
                        seen_direction_change_start_time = None
                        seen_direction_start_time = None
                        counter = 0
                        pts.clear()
                        misdetections = 0
                        continue

                    if len(pts) == OCR.LOOKBACK: 
                        previous = pts[-1]
                        current = pts[0]

                        dx = previous[0] - current[0]
                        dy = previous[1] - current[1]

                        if np.abs(dx) > self.diff_thresh or np.abs(dy) > self.diff_thresh:
                            # get direction of wheel movement
                            is_anticlockwise = ((previous[0] - wheel_center[0]) * (current[1] - wheel_center[1]) - 
                                                (previous[1] - wheel_center[1]) * (current[0] - wheel_center[0])) < 0;

        
                            if is_anticlockwise:
                                if current_direction == "clockwise":
                                    # if we've already seen the direction change once, reset state as its unstable
                                    if direction_changed:
                                        direction_changed = False
                                    else:
                                        if time.time() - seen_direction_start_time > OCR.TIME_FOR_STABLE_DIRECTION:
                                            direction_changed = True
                                            seen_direction_change_start_time = time.time()
                                        else:
                                            # initial direction changed too rapidly
                                            current_direction = ""
                                if current_direction == "":
                                    seen_direction_start_time = time.time()
                                    
                                current_direction = "anticlockwise"
                            else:
                                if current_direction == "anticlockwise":
                                    if direction_changed:
                                        direction_changed = False
                                    else:
                                        if time.time() - seen_direction_start_time > OCR.TIME_FOR_STABLE_DIRECTION:
                                            direction_changed = True
                                            seen_direction_change_start_time = time.time()
                                        else:
                                            current_direction = ""
                                if current_direction == "":
                                    seen_direction_start_time = time.time()

                                current_direction = "clockwise"

                    if direction_changed:
                        duration = time.time() - seen_direction_change_start_time
                        if duration > OCR.TIME_FOR_STABLE_DIRECTION:
                            direction_change_stable = True
                            spin_start_time = time.time()
                            # reset some state so this block doesn't happen again
                            direction_changed = False

                    cv2.putText(frame, current_direction, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 3)
                    # show the frame to our screen
                    cv2.circle(frame, wheel_center, 15, (0, 0, 255), -1)
                    cv2.circle(frame, ref_diamond, 5, (0, 0, 255), -1)
                    cv2.imshow("Wheel Detection", frame)
                    cv2.imshow("Ball Detection", ball_frame)
                    key = cv2.waitKey(1) & 0xFF
                    frames_seen = (frames_seen + 1) % (OCR.MAX_MISDETECTIONS_BEFORE_RESETTING_STATE + 2)

                    if frames_seen == 0:
                        misdetections = 0
                    if counter <= OCR.LOOKBACK:
                        counter += 1

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


    def calculate_rotor(self, direction, green_point, degrees, rotor_measure_duration, ref_diamond_point, fall_time_from_now):
        # first get the measured speed of the rotor in degrees/second
        speed = degrees / rotor_measure_duration

        # get the degree offset green is from the reference diamond
        # if degree_offset is less than 180, green is ABOVE reference diamond, assuming ref diamond is to the right
        # if degree_offset is more than 180, green is BELOW reference diamond, assuming ref diamond is to the right
        degree_offset = self.get_angle(green_point, self.wheel_center_point, ref_diamond_point)

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
            if degree_offset_after_travel <= 180:
                # if green is ABOVE ref diamond, go to the right of the green to find raw
                ratio_to_look = (degree_offset_after_travel - 180) / 360
                idx = int(round(len(self.european_wheel) * ratio_to_look))
                raw = self.european_wheel[idx]
            else:
                # if green is BELOW ref diamond, go to the left of the green to find raw
                ratio_to_look = degree_offset_after_travel / 360
                idx = int(round(len(self.european_wheel) * ratio_to_look))
                raw = self.european_wheel[-idx]
        except Exception as e:
            print(f"EXCEPTION: {e}")
            print(f"degree_offset: {degree_offset}")
            print(f"degrees_green_travels: {degrees_green_travels}")
            print(f"degree_offset_after_travel: {degree_offset_after_travel}")
            return 0

        print(f"SPEED: {speed} degrees/second")
        print(f"Duration: {rotor_measure_duration}")
        print(f"degrees measured: {degrees}")
        print(f"degree_offset: {degree_offset}")
        print(f"degrees_green_travels: {degrees_green_travels}")
        print(f"degree_offset_after_travel: {degree_offset_after_travel}")

        
        return raw
