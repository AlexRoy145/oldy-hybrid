import cv2
import imutils
import multiprocessing as mp
import numpy as np
import time as t
import winsound
from collections import deque
from PIL import Image

MIN_BALL_AREA = 50
MAX_BALL_AREA = 2000
BALL_START_TIMINGS = 450
THRESH = 65
BALL_FALL_THRESH = 30
MAX_SPIN_DURATION = 30
FALSE_DETECTION_THRESH = 100
EPSILON = 25

class Ball:

    @staticmethod
    def start_capture(in_queue, out_queue, ball_sample, ball_detection_zone, ball_fall_detection_zones):
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
        spin_start_time = 0
        start_ball_timings = False

        ball_reference_frame = ball_detection_zone.reference_frame
        ball_detection_bbox = ball_detection_zone.bounding_box

        if ball_fall_detection_zones:
            ball_fall_in_queue = mp.Queue()
            ball_fall_out_queue = mp.Queue()
            ball_fall_proc = mp.Process(target=Ball.start_ball_fall_capture, args=(ball_fall_in_queue, ball_fall_out_queue, ball_fall_detection_zones))
            ball_fall_proc.start()

        first_frame = Image.frombytes('RGB', ball_reference_frame.size, ball_reference_frame.rgb)
        first_frame = np.array(first_frame)
        first_frame_gray = cv2.cvtColor(first_frame, cv2.COLOR_BGR2GRAY)
        first_frame_gray = cv2.GaussianBlur(first_frame_gray, (11, 11), 0)

        while True:
            if in_queue.empty():
                continue
            in_msg = in_queue.get()
            if in_msg["state"] == "quit":
                cv2.destroyAllWindows()
                ball_fall_in_queue.put({"state" : "quit"})
                ball_fall_proc.join()
                ball_fall_proc.close()
                return
            else:
                frame = in_msg["frame"]
                try:
                    if not start_ball_timings:
                        start_ball_timings = in_msg["start_ball_timings"]
                except KeyError:
                    pass

                try:
                    if not spin_start_time:
                        spin_start_time = in_msg["spin_start_time"]
                except KeyError:
                    pass
                frame = Image.frombytes('RGB', frame.size, frame.rgb)
                ball_frame = frame.crop(ball_detection_bbox)
                ball_frame = np.array(ball_frame)

            if start_ball_timings:
                ball_fall_in_queue.put({"frame" : frame, "state" : "good"})
                if not false_detections:
                    gray = cv2.cvtColor(ball_frame, cv2.COLOR_BGR2GRAY)
                    gray = cv2.GaussianBlur(gray, (11, 11), 0)
                    if first_capture:
                        first_ball_frame = first_frame_gray
                        first_capture = False

                    if fall_time > 0:
                        elapsed_time = (Ball.time() - fall_time_timestamp) * 1000
                        if not did_beep and abs(elapsed_time - fall_time) < EPSILON:
                            did_beep = True

                    # fall accuracy evaluation
                    if ball_fall_detection_zones:
                        if not ball_fall_out_queue.empty():
                            ball_fall_out_msg = ball_fall_out_queue.get()
                            true_ball_fall_timestamp = ball_fall_out_msg["timestamp"]
                            expected_ball_fall_timestamp = fall_time_timestamp + fall_time / 1000
                            diff = int((true_ball_fall_timestamp - expected_ball_fall_timestamp) * 1000)
                            if diff <= 0:
                                print(f"The ball fell {diff} ms earlier than expected.")
                            else:
                                print(f"The ball fell {diff} ms later than expected.")
                            ball_fall_proc.join()
                            ball_fall_proc.close()
                        

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
                                    fall_time = ball_sample.get_fall_time_averaged(lap_time) 
                                    if fall_time > 0:
                                        fall_time_timestamp = Ball.time()
                                        print(f"FALL TIME CALCULATED TO BE {fall_time} MS FROM NOW")
                                        out_msg = {"state": "fall_time_calculated",
                                                   "fall_time" : fall_time,
                                                   "fall_time_timestamp" : fall_time_timestamp}
                                        out_queue.put(out_msg)


            
            if start_ball_timings:
                cv2.imshow("Ball Detection", ball_thresh)
            else:
                cv2.imshow("Ball Detection", ball_frame)
            key = cv2.waitKey(1) & 0xFF


    @staticmethod
    def start_ball_fall_capture(in_queue, out_queue, ball_fall_detection_zones):
        while True:
            if in_queue.empty():
                continue
            in_msg = in_queue.get()
            if in_msg["state"] == "quit":
                return
            else:
                frame = in_msg["frame"]
                
                for i, ball_fall_detection_zone in enumerate(ball_fall_detection_zones):
                    ball_frame = frame.crop(ball_fall_detection_zone.bounding_box)
                    ball_reference_frame = ball_fall_detection_zone.reference_frame
                    ball_frame = np.array(ball_frame)

                    ball_reference_frame = Image.frombytes('RGB', ball_reference_frame.size, ball_reference_frame.rgb)
                    ball_reference_frame = np.array(ball_reference_frame)
                    ball_reference_frame_gray = cv2.cvtColor(ball_reference_frame, cv2.COLOR_BGR2GRAY)
                    ball_reference_frame_gray = cv2.GaussianBlur(ball_reference_frame_gray, (11, 11), 0)

                    gray = cv2.cvtColor(ball_frame, cv2.COLOR_BGR2GRAY)
                    gray = cv2.GaussianBlur(gray, (11, 11), 0)

                    ball_frame_delta = cv2.absdiff(ball_reference_frame_gray, gray)
                    ball_thresh = cv2.threshold(ball_frame_delta, BALL_FALL_THRESH, 255, cv2.THRESH_BINARY)[1]

                    ball_thresh = cv2.dilate(ball_thresh, None, iterations=2)
                    ball_cnts = cv2.findContours(ball_thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    ball_cnts = imutils.grab_contours(ball_cnts)

                    for c in ball_cnts:
                        area = cv2.contourArea(c)
                        '''
                        if area < MIN_BALL_AREA or area > MAX_BALL_AREA:
                            continue
                        '''

                        timestamp = Ball.time()
                        print(f"BALL FALL DETECTED VIA DETECTION {i} at {timestamp}")
                        out_queue.put({"state" : "ball_fall_detected", "timestamp" : timestamp})
                        return


                    cv2.imshow(f"Ball Fall Detection {i}", ball_thresh)
                    key = cv2.waitKey(1) & 0xFF

    @staticmethod
    def time():
        return t.time_ns() / 1000000000
