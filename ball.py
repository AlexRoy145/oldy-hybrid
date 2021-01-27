import cv2
import imutils
import multiprocessing as mp
import numpy as np
import time as t
import winsound
import autoit
from collections import deque
from PIL import Image
from util import Util

MIN_BALL_AREA = 50
MAX_BALL_AREA = 1500
FASTEST_LAP_TIME = 300
THRESH = 45
BALL_FALL_THRESH = 65
MAX_SPIN_DURATION = 30
FALSE_DETECTION_THRESH = 100
EPSILON = 25
FRAME_LOOKBACK = 2

MAX_EXTENSION = 30 # 30 degrees each direction, which is about 3 pockets each direction

WAIT_FOR_FALL_DETECTION = 5 #seconds
SINGLE_CONTOURS_NEEDED = 8 #frames, about 18ms per frame

ANGLE_START = 10
ANGLE_END = 350

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

            start_ball_timings_timestamp = -1
            direction = "anticlockwise"

            single_contour_detected_count = 0
            previous_angle = None

            previous_lap_time = None

            ball_revs = 0

            ball_reference_frame = ball_detection_zone.reference_frame

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
                            direction = in_msg["direction"]
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
                    if start_ball_timings_timestamp == -1:
                        start_ball_timings_timestamp = Util.time()
                        print("Started ball timings")

                    if Util.time() - start_ball_timings_timestamp > WAIT_FOR_FALL_DETECTION:
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
                        if not ball_fall_out_queue.empty():
                            ball_fall_out_msg = ball_fall_out_queue.get()
                            out_queue.put({"state" : "ball_fell", "fall_point" : ball_fall_out_msg["fall_point"], "ball_revs" : ball_revs})
                            fall_point = ball_fall_out_msg["fall_point"]
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
                            out_msg = {"state" : "ball_update", "current_ball_sample" : current_ball_sample, "fall_point" : fall_point, "ball_revs" : ball_revs}
                            out_queue.put(out_msg)

                        ball_frame_delta = cv2.absdiff(ball_reference_frame, gray)
                        ball_thresh = cv2.threshold(ball_frame_delta, THRESH, 255, cv2.THRESH_BINARY)[1]

                        ball_thresh = cv2.dilate(ball_thresh, None, iterations=2)
                        ball_cnts = cv2.findContours(ball_thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        ball_cnts = imutils.grab_contours(ball_cnts)

                        #print(f"NUM BALL_CNTS: {len(ball_cnts)}")

                        for c in ball_cnts:
                            M = cv2.moments(c)
                            center = int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
                            area = cv2.contourArea(c)
                            if area < MIN_BALL_AREA or area > MAX_BALL_AREA:
                                continue

                            angle_from_ref = Util.get_angle(center, wheel_center_point, reference_diamond_point)
                            if not previous_angle:
                                previous_angle = angle_from_ref
                            else: 
                                difference = abs(angle_from_ref - previous_angle) % 180
                                #extension = Ball.get_extension(difference)
                                extension = 2
                                previous_angle = angle_from_ref

                                if Ball.in_range(angle_from_ref, ANGLE_START, ANGLE_END, extension=extension):
                                    now = int(round(Util.time() * 1000))
                                    if first_pass:
                                        start_time = now
                                        first_pass = False
                                        ball_revs += 1
                                    else:
                                        lap_time = now - start_time

                                        # increase refractory period as laps get slower
                                        if not previous_lap_time:
                                            previous_lap_time = lap_time
                                            fastest_lap_time = FASTEST_LAP_TIME
                                        else:
                                            if previous_lap_time > 1000:
                                                fastest_lap_time = previous_lap_time - 500
                                            else:
                                                fastest_lap_time = FASTEST_LAP_TIME

                                        if lap_time > fastest_lap_time:
                                            previous_lap_time = lap_time
                                            start_time = now
                                            frame_counter = 0
                                            print("Ball detected, lap: %dms" % lap_time)
                                            autoit.send("z")
                                            ball_revs += 1
                                            if len(current_ball_sample) > 0:
                                                '''
                                                if current_ball_sample[-1] - lap_time > FALSE_DETECTION_THRESH:
                                                    print("FALSE DETECTIONS")
                                                    out_msg = {"state" : "false_detections"}
                                                    out_queue.put(out_msg)
                                                '''

                                            current_ball_sample.append(lap_time)

                                            if fall_time < 0:
                                                fall_time = ball_sample.get_fall_time_averaged(lap_time, direction)
                                                if fall_time > 0:
                                                    fall_time_timestamp = Util.time()
                                                    #print(f"FALL TIME CALCULATED TO BE {fall_time} MS FROM NOW")
                                                    out_msg = {"state": "fall_time_calculated",
                                                               "fall_time" : fall_time,
                                                               "fall_time_timestamp" : fall_time_timestamp}
                                                    out_queue.put(out_msg)
                            break


                
                if start_ball_timings:
                    '''
                    cv2.imshow("Ball Detection", ball_thresh)
                    key = cv2.waitKey(1) & 0xFF
                    '''
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
                        M = cv2.moments(c)
                        center = int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
                        area = cv2.contourArea(c)
                        '''
                        if area < MIN_BALL_AREA or area > MAX_BALL_AREA:
                            continue
                        '''

                        timestamp = Util.time()
                        print(f"BALL FALL DETECTED")
                        out_queue.put({"state" : "ball_fall_detected", "timestamp" : timestamp, "fall_point" : center})
                        ball_fall_detected = True

                    '''
                    cv2.imshow(f"Ball Fall Detection", ball_thresh)
                    key = cv2.waitKey(1) & 0xFF
                    '''

    @staticmethod
    def start_capture_databot(in_queue, out_queue, ball_sample, ball_detection_zone, ball_fall_detection_zone, wheel_center_point, reference_diamond_point):
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

            start_ball_timings_timestamp = -1

            single_contour_detected_count = 0
            previous_angle = None

            ball_revs = 0

            ball_reference_frame = ball_detection_zone.reference_frame

            ball_fall_in_queue = mp.Queue()
            ball_fall_out_queue = mp.Queue()
            ball_fall_proc = mp.Process(target=Ball.start_ball_fall_capture, args=(ball_fall_in_queue, ball_fall_out_queue, ball_fall_detection_zone))
            ball_fall_proc.start()

            expecting_left = True
            every_two = 0

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

                    if start_ball_timings_timestamp == -1:
                        start_ball_timings_timestamp = Util.time()
                        print("Started ball timings")

                    if Util.time() - start_ball_timings_timestamp > WAIT_FOR_FALL_DETECTION:
                        try:
                            ball_fall_in_queue.put({"frame" : frame, "state" : "good"})
                        except BrokenPipeError:
                            pass

                    if not false_detections:
                        gray = cv2.cvtColor(ball_frame, cv2.COLOR_BGR2GRAY)
                        gray = cv2.GaussianBlur(gray, (11, 11), 0)
                        gray = np.bitwise_and(gray, ball_detection_zone.mask)

                        if not ball_fall_out_queue.empty():
                            ball_fall_out_msg = ball_fall_out_queue.get()
                            out_queue.put({"state" : "ball_fell", "fall_point" : ball_fall_out_msg["fall_point"], "ball_revs" : ball_revs})
                            ball_fall_in_queue.put({"state" : "quit"})

                        if Util.time() - spin_start_time > MAX_SPIN_DURATION:
                            # if didnt detect ball fall, quit gracefully
                            out_queue.put({"state" : "failed_detect"})

                        ball_frame_delta = cv2.absdiff(ball_reference_frame, gray)
                        ball_thresh = cv2.threshold(ball_frame_delta, THRESH, 255, cv2.THRESH_BINARY)[1]

                        ball_thresh = cv2.dilate(ball_thresh, None, iterations=2)
                        ball_cnts = cv2.findContours(ball_thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        ball_cnts = imutils.grab_contours(ball_cnts)

                        #print(f"NUM BALL_CNTS: {len(ball_cnts)}")
                        #for c in ball_cnts:
                        if len(ball_cnts) > 0:
                            c = ball_cnts[0]
                            M = cv2.moments(c)
                            center = int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
                            area = cv2.contourArea(c)
                            #print(area)
                            if area < MIN_BALL_AREA or area > MAX_BALL_AREA:
                                continue

                            angle_from_ref = Util.get_angle(center, wheel_center_point, reference_diamond_point)

                            if expecting_left:
                                if Ball.in_left_sector(angle_from_ref):
                                    expecting_left = False
                                    every_two += 1
                                    #break
                            else:
                                if Ball.in_right_sector(angle_from_ref):
                                    expecting_left = True
                                    ball_revs += 1
                                    print(f"Ball revs so far: {ball_revs}")
                                    #break

                if start_ball_timings:
                    '''
                    cv2.imshow("Ball Detection", ball_thresh)
                    key = cv2.waitKey(1) & 0xFF
                    '''
        except BrokenPipeError:
            pass



    @staticmethod
    def in_range(angle, start_angle, end_angle, extension=0):
        return (angle < start_angle + extension and angle >= 0) or (angle > end_angle - extension and angle <= 360)

    @staticmethod
    def in_left_sector(angle):
        return (angle < 270 and angle > 90)

    @staticmethod
    def in_right_sector(angle):
        return (angle < 90 and angle >= 0 or angle > 270 and angle <= 360)


    @staticmethod
    def get_extension(difference):
        if difference < 20:
            return 0
        elif difference < 30:
            return 10
        elif difference < 40:
            return 20
        elif difference < 50:
            return 30
        elif difference < 60:
            return 40
        else:
            return 60
