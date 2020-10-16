import ctypes
import ctypes.util
import cv2
import imutils
import mss
import os.path
import pickle
import numpy as np
import time
import threading
from pynput import mouse
from collections import deque
from PIL import Image
from pytessy import PyTessy

class OCR:

    GREEN_LOWER = (29, 86, 6)
    GREEN_UPPER = (64, 255, 255)
    MIN_STABILITY_DURATION = 1.5 #seconds
    GIVE_UP_LOOKING_FOR_RAW = 10 #seconds
    TIME_FOR_STABLE_DIRECTION = 2 #seconds
    MAX_MISDETECTIONS_BEFORE_RESETTING_STATE = 60
    DIFF_RATIO = 9
    MORPH_KERNEL_RATIO = .0005
    LOOKBACK = 20

    def __init__(self, profile_dir):
        self.raw_detection_zone = []
        self.wheel_detection_zone = []
        self.diff_thresh = 0
        self.wheel_detection_area = 0
        
        self.p = PyTessy()
        self.m = mouse.Controller()
        self.profile_dir = profile_dir


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
            d = {"raw_detection_zone" : self.raw_detection_zone,
                 "wheel_detection_zone" : self.wheel_detection_zone,
                 "diff_thresh" : self.diff_thresh,
                 "wheel_detection_area" :self.wheel_detection_area}
            pickle.dump(d, f)


    def set_raw_detection_zone(self):
        self.raw_detection_zone = []
        zone = self.raw_detection_zone
        input(f"Hover the mouse over the upper left corner of the detection zone for the raw prediction, then hit ENTER.")
        x_top,y_top = self.m.position
        zone.append(x_top)
        zone.append(y_top)

        input("Hover the mouse over the bottom right corner of the detection zone, then hit ENTER.")
        x_bot,y_bot = self.m.position
        zone.append(x_bot)
        zone.append(y_bot)

        print(f"Bounding box: {zone}")


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

        self.diff_thresh = int((self.wheel_detection_zone[2] - self.wheel_detection_zone[0]) / OCR.DIFF_RATIO)
        print(f"diff_thresh: {self.diff_thresh}")
        bbox = self.wheel_detection_zone
        width = bbox[2]-bbox[0]
        height = bbox[3]-bbox[1]

        self.wheel_detection_area = width * height


    def start_capture(self):
        pts = deque(maxlen=OCR.LOOKBACK)
        current_direction = ""
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
        wheel_center = int(width/2), int(height/2)

        with mss.mss() as sct:
            while True:
                frame = sct.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon":0})

                frame = Image.frombytes('RGB', frame.size, frame.rgb)
                frame = np.array(frame)
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
                        is_left = ((previous[0] - wheel_center[0]) * (current[1] - wheel_center[1]) - 
                                   (previous[1] - wheel_center[1]) * (current[0] - wheel_center[0])) < 0;

    
                        if is_left:
                            if current_direction == "clockwise":
                                # if we've already seen the direction change once, reset state as its unstable
                                if direction_changed:
                                    direction_changed = False
                                else:
                                    direction_changed = True
                                    seen_direction_start_time = time.time()
                            current_direction = "anticlockwise"
                        else:
                            if current_direction == "anticlockwise":
                                if direction_changed:
                                    direction_changed = False
                                else:
                                    direction_changed = True
                                    seen_direction_start_time = time.time()
                            current_direction = "clockwise"

                if direction_changed:
                    duration = time.time() - seen_direction_start_time
                    if duration > OCR.TIME_FOR_STABLE_DIRECTION:
                        direction_change_stable = True

                cv2.putText(frame, current_direction, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 3)
                # show the frame to our screen
                cv2.circle(frame, wheel_center, 15, (0, 0, 255), -1)
                cv2.imshow("Wheel Detection", frame)
                key = cv2.waitKey(1) & 0xFF
                frames_seen = (frames_seen + 1) % (OCR.MAX_MISDETECTIONS_BEFORE_RESETTING_STATE + 2)

                if frames_seen == 0:
                    misdetections = 0
                if counter <= OCR.LOOKBACK:
                    counter += 1

                if direction_change_stable:
                    print(f"Direction change confirmed: {current_direction}. Identifying if raw is present.")
                    previous_raw = self.read(capture=sct)
                    if self.is_valid_raw(previous_raw):
                        print(f"Raw is valid and is currently: {previous_raw}. Waiting up to {OCR.GIVE_UP_LOOKING_FOR_RAW} seconds for change.")
                        # now wait for a change
                        start_time = time.time()
                        while True:
                            current_raw = self.read(capture=sct)
                            if self.is_valid_raw(current_raw):
                                if current_raw != previous_raw:
                                    print(f"Detected change in raw! Pressing space bar...")
                                    return current_direction, int(current_raw)

                            duration = time.time() - start_time
                            if duration > OCR.GIVE_UP_LOOKING_FOR_RAW:
                                print(f"Could not detect change in raw prediction properly")
                                return None, None

                    else:
                        print(f"Could not detect change in raw prediction properly")
                        return None, None


    def read(self, test=False, capture=None):
        now = time.time()
        bbox = self.raw_detection_zone
        width = bbox[2]-bbox[0]
        height = bbox[3]-bbox[1]
        if capture:
            sct_img = capture.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon":0})
        else:
            with mss.mss() as sct:
                sct_img = sct.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon":0})
        pil_image = Image.frombytes('RGB', sct_img.size, sct_img.rgb)
        open_cv_image = np.array(pil_image)
        open_cv_image = open_cv_image[:, :, ::-1].copy() 
        if test:
            cv2.imshow("captured image", open_cv_image)
            cv2.waitKey(0)

        finalimage = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        ret,thresholded = cv2.threshold(finalimage, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)

        finalimage = thresholded
        end = time.time()

        now_2 = time.time()
        prediction = self.p.read(finalimage.ctypes, finalimage.shape[1], finalimage.shape[0], 1) 
        end_2 = time.time()

        prediction = self.post_process(prediction)

        return prediction


    def post_process(self, prediction):
        if prediction:
            prediction = prediction.replace("s", "5")
            prediction = prediction.replace("S", "5")

            prediction = prediction.replace("Z", "2")
            prediction = prediction.replace("z", "2")

            prediction = prediction.replace("l", "1")
            prediction = prediction.replace("L", "1")
            prediciton = prediction.replace("i", "1")

            prediction = prediction.replace("g", "9")
            prediction = prediction.replace("G", "9")

            prediction = prediction.replace("A", "4")

            prediction = prediction.replace("O", "0")
            prediction = prediction.replace("o", "0")
            prediction = prediction.replace("Q", "0")

            prediction = prediction.replace("a", "8")
            prediction = prediction.replace("B", "8")

        return prediction


    def is_valid_raw(self, raw_prediction):
        try:
            raw_prediction = int(raw_prediction)
        except (ValueError, TypeError) as e:
            return False

        if raw_prediction < 0 or raw_prediction > 36:
            return False

        return True

