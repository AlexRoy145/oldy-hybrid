import cv2
import imutils
import multiprocessing as mp
import numpy as np
import time as t
import winsound
from collections import deque
from PIL import Image
from util import Util

MIN_BALL_AREA = 50
MAX_BALL_AREA = 2000
BALL_START_TIMINGS = 450
THRESH = 65
BALL_FALL_THRESH = 65
MAX_SPIN_DURATION = 30
FALSE_DETECTION_THRESH = 100
EPSILON = 25

ANGLE_START = 20
ANGLE_END = 340

class Ball:

    @staticmethod
    def start_capture(in_queue, out_queue, ball_sample, ball_detection_zone, ball_fall_detection_zone, wheel_center_point, reference_diamond_point):
        try:
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

            if ball_fall_detection_zone:
                ball_fall_in_queue = mp.Queue()
                ball_fall_out_queue = mp.Queue()
                ball_fall_proc = mp.Process(target=Ball.start_ball_fall_capture, args=(ball_fall_in_queue, ball_fall_out_queue, ball_fall_detection_zone))
                ball_fall_proc.start()

            while True:
                if in_queue.empty():
                    continue
                in_msg = in_queue.get()
                if in_msg["state"] == "quit":
                    cv2.destroyAllWindows()
                    '''
                    try:
                        ball_fall_in_queue.put({"state" : "quit"})
                        ball_fall_proc.join()
                        ball_fall_proc.close()
                    except BrokenPipeError:
                        pass
                    '''
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
                    ball_frame = np.array(frame)

                if start_ball_timings:
                    try:
                        ball_fall_in_queue.put({"frame" : frame, "state" : "good"})
                    except BrokenPipeError:
                        pass
                    if not false_detections:
                        gray = cv2.cvtColor(ball_frame, cv2.COLOR_BGR2GRAY)
                        gray = cv2.GaussianBlur(gray, (11, 11), 0)
                        gray = np.bitwise_and(gray, ball_detection_zone.mask)

                        if fall_time > 0:
                            elapsed_time = (Util.time() - fall_time_timestamp) * 1000
                            if not did_beep and abs(elapsed_time - fall_time) < EPSILON:
                                winsound.Beep(1000, 50)
                                did_beep = True

                        # fall accuracy evaluation
                        if ball_fall_detection_zone:
                            if not ball_fall_out_queue.empty():
                                ball_fall_out_msg = ball_fall_out_queue.get()
                                true_ball_fall_timestamp = ball_fall_out_msg["timestamp"]
                                expected_ball_fall_timestamp = fall_time_timestamp + fall_time / 1000
                                diff = int((expected_ball_fall_timestamp - true_ball_fall_timestamp) * 1000)
                                if diff <= 0:
                                    print(f"The ball fall beep was {-diff}ms early.")
                                else:
                                    print(f"The ball fall beep was {diff}ms late.")
                                ball_fall_in_queue.put({"state" : "quit"})
                                '''
                                ball_fall_proc.join()
                                ball_fall_proc.close()
                                '''

                        if Util.time() - spin_start_time > MAX_SPIN_DURATION:
                            out_msg = {"state" : "ball_update", "current_ball_sample" : current_ball_sample}
                            out_queue.put(out_msg)

                        ball_frame_delta = cv2.absdiff(ball_reference_frame, gray)
                        ball_thresh = cv2.threshold(ball_frame_delta, THRESH, 255, cv2.THRESH_BINARY)[1]

                        ball_thresh = cv2.dilate(ball_thresh, None, iterations=2)
                        ball_cnts = cv2.findContours(ball_thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        ball_cnts = imutils.grab_contours(ball_cnts)

                        for c in ball_cnts:
                            M = cv2.moments(c)
                            center = int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
                            area = cv2.contourArea(c)
                            if area < MIN_BALL_AREA or area > MAX_BALL_AREA:
                                continue

                            angle_from_ref = Util.get_angle(center, wheel_center_point, reference_diamond_point)
                            if angle_from_ref > ANGLE_START and angle_from_ref < ANGLE_END:
                                continue

                            now = int(round(Util.time() * 1000))
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
                                            fall_time_timestamp = Util.time()
                                            #print(f"FALL TIME CALCULATED TO BE {fall_time} MS FROM NOW")
                                            out_msg = {"state": "fall_time_calculated",
                                                       "fall_time" : fall_time,
                                                       "fall_time_timestamp" : fall_time_timestamp}
                                            out_queue.put(out_msg)


                
                if start_ball_timings:
                    cv2.imshow("Ball Detection", ball_thresh)
                    key = cv2.waitKey(1) & 0xFF
        except BrokenPipeError:
            pass

    @staticmethod
    def start_ball_fall_capture(in_queue, out_queue, ball_fall_detection_zone):
        ball_fall_detected = False
        while True:
            if in_queue.empty():
                continue
            in_msg = in_queue.get()
            if in_msg["state"] == "quit":
                return
            else:
                frame = in_msg["frame"]
                
                if not ball_fall_detected:
                    # fall ref frame is already preprocessed
                    fall_reference_frame = ball_fall_detection_zone.reference_frame
                    ball_frame = np.array(frame)

                    gray = cv2.cvtColor(ball_frame, cv2.COLOR_BGR2GRAY)
                    gray = cv2.GaussianBlur(gray, (11, 11), 0)

                    # mask ball_frame to match fall_reference_frame
                    gray = np.bitwise_and(gray, ball_fall_detection_zone.mask)

                    ball_frame_delta = cv2.absdiff(fall_reference_frame, gray)
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

                        timestamp = Util.time()
                        print(f"BALL FALL DETECTED")
                        out_queue.put({"state" : "ball_fall_detected", "timestamp" : timestamp})
                        ball_fall_detected = True

                    '''
                    cv2.imshow(f"Ball Fall Detection", ball_thresh)
                    key = cv2.waitKey(1) & 0xFF
                    '''
