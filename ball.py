import cv2
import imutils
import numpy as np
import time as t
import winsound
from collections import deque
from PIL import Image

MIN_BALL_AREA = 100
MAX_BALL_AREA = 2000
BALL_START_TIMINGS = 550
THRESH = 65
MAX_SPIN_DURATION = 30
FALSE_DETECTION_THRESH = 100
EPSILON = 250

class Ball:

    @staticmethod
    def start_capture(in_queue, out_queue, relative_ball_detection_zone, ball_sample, spin_start_time):
        current_ball_sample = []
        first_ball_frame = []
        first_capture = True
        first_pass = True
        start_time = 0
        rev_time = 0
        fall_time = -1
        fall_time_timestamp = 0
        did_beep = False
        false_detections = False


        while True:
            if in_queue.empty():
                continue
            in_msg = in_queue.get()
            if in_msg["state"] == "quit":
                cv2.destroyAllWindows()
                return
            else:
                frame = in_msg["frame"]
                frame = Image.frombytes('RGB', frame.size, frame.rgb)
                ball_frame = frame.crop(relative_ball_detection_zone)
                ball_frame = np.array(ball_frame)

            if not false_detections:
                gray = cv2.cvtColor(ball_frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (11, 11), 0)
                if first_capture:
                    first_ball_frame = gray
                    first_capture = False

                if fall_time > 0:
                    elapsed_time = (Ball.time() - fall_time_timestamp) * 1000
                    if not did_beep and abs(elapsed_time - fall_time) < EPSILON:
                        winsound.Beep(1000, 50)
                        did_beep = True
                    

                if Ball.time() - spin_start_time > MAX_SPIN_DURATION:
                    out_msg = {"state" : "ball_update", "current_ball_sample" : current_ball_sample}
                    out_queue.put(out_msg)

                ball_frame_delta = cv2.absdiff(first_ball_frame, gray)
                ball_thresh = cv2.threshold(ball_frame_delta, THRESH, 255, cv2.THRESH_BINARY)[1]

                ball_thresh = cv2.dilate(ball_thresh, None, iterations=2)
                ball_cnts = cv2.findContours(ball_thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                ball_cnts = imutils.grab_contours(ball_cnts)

                for c in ball_cnts:
                    area = cv2.contourArea(c)
                    if area < MIN_BALL_AREA or area > MAX_BALL_AREA:
                        continue

                    now = int(round(Ball.time() * 1000))
                    if first_pass:
                        start_time = now
                        first_pass = False
                    else:
                        lap_time = now - start_time

                        if lap_time > BALL_START_TIMINGS:
                            start_time = now
                            print("Ball detected, lap: %dms" % lap_time)
                            if len(current_ball_sample) > 0:
                                if current_ball_sample[-1] - lap_time > FALSE_DETECTION_THRESH:
                                    print("FALSE DETECTIONS")
                                    out_msg = {"state" : "false_detections"}
                                    out_queue.put(out_msg)

                            current_ball_sample.append(lap_time)
                            if fall_time < 0:
                                fall_time = ball_sample.get_fall_time(lap_time) 
                                if fall_time > 0:
                                    fall_time_timestamp = Ball.time()
                                    print(f"FALL TIME CALCULATED TO BE {fall_time} MS FROM NOW")
                                    out_msg = {"state": "fall_time_calculated",
                                               "fall_time" : fall_time,
                                               "fall_time_timestamp" : fall_time_timestamp}
                                    out_queue.put(out_msg)


            
            cv2.imshow("Ball Detection", ball_frame)
            key = cv2.waitKey(1) & 0xFF


    @staticmethod
    def time():
        return t.time_ns() / 1000000000