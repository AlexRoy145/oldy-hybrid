import cv2
import imutils
import multiprocessing as mp
import numpy as np
import time as t
import winsound
from collections import deque
from pynput.mouse import Button, Controller
from PIL import Image
from util import Util

MIN_BALL_AREA = 50
MAX_BALL_AREA = 1500
FASTEST_LAP_TIME = 150
THRESH = 45
BALL_FALL_THRESH = 65
MAX_SPIN_DURATION = 30
FALSE_DETECTION_THRESH = 100
EPSILON = 25
FRAME_LOOKBACK = 2

MAX_EXTENSION = 30 # 30 degrees each direction, which is about 3 pockets each direction

MAX_STDEV = 150

WAIT_FOR_FALL_DETECTION = 5 #seconds
SINGLE_CONTOURS_NEEDED = 8 #frames, about 18ms per frame

ANGLE_START = 10
ANGLE_END = 350

ANGLE_1 = 30
ANGLE_MAIN = 0
ANGLE_2 = 330

TEST_ANGLE_1 = 40
TEST_ANGLE_2 = 20
TEST_ANGLE_3 = 340
TEST_ANGLE_4 = 320

CENTER_ANGLE_IDX = 2

DONT_NEED_AVERAGING_TIMING = 2000

NUMBER_OF_CLICKS = 2

class Ball:

    @staticmethod
    def start_capture(in_queue, out_queue, ball_sample, ball_detection_zone, ball_fall_detection_zone, wheel_center_point, reference_diamond_point, diamond_target_time, diamond_targeting_button_zone):
        try:
            mouse = Controller()
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

            ball_in_detection_zone = True

            time_elapsed_since_frame = 0

            ball_reference_frame = ball_detection_zone.reference_frame

            ball_fall_in_queue = mp.Queue()
            ball_fall_out_queue = mp.Queue()
            ball_fall_proc = mp.Process(target=Ball.start_ball_fall_capture, args=(ball_fall_in_queue, ball_fall_out_queue, ball_fall_detection_zone))
            ball_fall_proc.start()

            angles = TEST_ANGLE_1, TEST_ANGLE_2, ANGLE_MAIN, TEST_ANGLE_3, TEST_ANGLE_4
            #angles = TEST_ANGLE_1, ANGLE_MAIN, TEST_ANGLE_4
            timestamps = [0] * len(angles)
            timings = [0] * len(angles)
            #angles = ANGLE_1, ANGLE_MAIN, ANGLE_2

            # diamond isolation testing

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
                    time_elapsed_since_frame = int(round(Util.time() * 1000))
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

                            if ball_in_detection_zone:
                                if angle_from_ref > 90 and angle_from_ref < 270:
                                    ball_in_detection_zone = False

                            if not previous_angle:
                                previous_angle = angle_from_ref
                            else: 
                                if not ball_in_detection_zone:
                                    timestamps, timings = Ball.measure_ball(direction, previous_angle, angle_from_ref, timestamps, timings, angles)
                                #print(f"Timings: {timings}, Timestamps: {timestamps}")
                                
                                if not 0 in timings or timings[len(angles) // 2] > DONT_NEED_AVERAGING_TIMING:
                                    now = int(round(Util.time() * 1000))
                                    diff = now - time_elapsed_since_frame
                                    if timings[len(angles) // 2] > DONT_NEED_AVERAGING_TIMING:
                                        lap_time = timings[len(angles) // 2] - diff
                                        filtered_lap_times = []
                                    else:
                                        m = 2
                                        np_timings = np.array(timings)
                                        filtered_lap_times = list(Ball.reject_outliers(np_timings, m=m))
                                        if len(filtered_lap_times) == 0:
                                            print(f"Rejected all timings: {np_timings}")
                                            timings = [0] * len(angles)
                                            timestamps = [0] * len(angles)
                                            break
                                        try:
                                            lap_time = int(round(sum(filtered_lap_times) / len(filtered_lap_times))) - diff
                                        except TypeError:
                                            lap_time = int(round(sum(list(filtered_lap_times[0][0])) / len(filtered_lap_times))) - diff
                                        #lap_time = int(round((timings[0] + timings[2]) / 2)) - diff


                                    diamond_target_time_diff = lap_time - diamond_target_time
                                    #print(f"diamond target time: {diamond_target_time} | diamond diff: {diamond_target_time_diff}")
                                    if "a" in direction:
                                        rev_tol = ball_sample.rev_tolerance_anti
                                    else:
                                        rev_tol = ball_sample.rev_tolerance_clock

                                    '''
                                    if (diamond_target_time_diff < 0 and diamond_target_time_diff >= -10) or (diamond_target_time_diff >= 0 and diamond_target_time_diff < rev_tol):
                                        print("clicking diamond")
                                        mouse.position = diamond_targeting_button_zone
                                        mouse.click(Button.left)
                                    '''

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
                                        
                                        #print(f"MS difference: {now - time_elapsed_since_frame}")
                                        previous_lap_time = lap_time
                                        frame_counter = 0
                                        print(f"Ball detected, lap: {lap_time}ms, filtered timings: {filtered_lap_times}") 
                                        ball_revs += 1
                                        if len(current_ball_sample) > 0:
                                            '''
                                            if current_ball_sample[-1] - lap_time > FALSE_DETECTION_THRESH:
                                                print("FALSE DETECTIONS")
                                                out_msg = {"state" : "false_detections"}
                                                out_queue.put(out_msg)
                                            '''

                                        current_ball_sample.append(lap_time)
                                        timings = [0] * len(angles)


                                        if fall_time < 0:
                                            fall_time = ball_sample.get_fall_time_averaged(lap_time, direction)

                                            
                                            '''
                                            if len(current_ball_sample) >= NUMBER_OF_CLICKS:
                                                fall_time = ball_sample.get_fall_time(current_ball_sample[-NUMBER_OF_CLICKS:]) 
                                            '''

                                            #fall_time = ball_sample.get_fall_time_averaged(lap_time)
                                            #fall_time = ball_sample.get_fall_time(lap_time)
                                            if fall_time > 0:
                                                center_angle_idx = len(angles) // 2
                                                center_timestamp = timestamps[center_angle_idx]
                                                if "a" in direction:
                                                    last_timestamp = timestamps[-1]
                                                else:
                                                    last_timestamp = timestamps[0]

                                                subtract_from_fall = abs(last_timestamp - center_timestamp)
                                                fall_time -= subtract_from_fall
                                                print(f"Fall adjustment: {subtract_from_fall}ms")

                                                fall_time_timestamp = Util.time()
                                                #print(f"FALL TIME CALCULATED TO BE {fall_time} MS FROM NOW")
                                                out_msg = {"state": "fall_time_calculated",
                                                           "fall_time" : fall_time,
                                                           "fall_time_timestamp" : fall_time_timestamp}
                                                out_queue.put(out_msg)

                                previous_angle = angle_from_ref

                                break
                        
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

                            # calculate how much time passed since last rev timing and when the ball fell
                            center_angle_idx = len(angles) // 2
                            fall_time_last_rev = int(round(true_ball_fall_timestamp * 1000 - timestamps[center_angle_idx]))
                            print(f"Fall time after last rev was {fall_time_last_rev} ms")
                            current_ball_sample[-1] += fall_time_last_rev

                            ball_fall_in_queue.put({"state" : "quit"})
                            '''
                            ball_fall_proc.join()
                            ball_fall_proc.close()
                            '''

                
                if start_ball_timings:
                    '''
                    cv2.imshow("Ball Detection", ball_thresh)
                    key = cv2.waitKey(1) & 0xFF
                    '''
        except BrokenPipeError:
            pass

    '''
    Returns two lists: the updated timestamps and timings.
    The timestamps list will have the new NOW timestamps for each respective angle.
    The timings list will have the previous lap timings for each respective angle.
    The initial values for both will be 0.
    '''
    @staticmethod
    def measure_ball(direction, previous_angle, angle_from_ref, timestamps, timings, angles):
        now = int(round(Util.time() * 1000))

        timestamps_to_return = timestamps[:]
        timings_to_return = timings[:]

        if "a" in direction:
            i = 0
            for timestamp, timing, angle in zip(timestamps, timings, angles):
                if angle == 0:
                    if angle_from_ref > previous_angle:
                        timestamps_to_return[i] = now
                        if timestamps[i] != 0:
                            timings_to_return[i] = now - timestamps[i]
                else:
                    if angle_from_ref < angle and previous_angle > angle:
                        timestamps_to_return[i] = now
                        if timestamps[i] != 0:
                            timings_to_return[i] = now - timestamps[i]

                i += 1

        else:
            i = 0
            for timestamp, timing, angle in zip(timestamps, timings, angles):
                if angle == 0:
                    if angle_from_ref < previous_angle:
                        timestamps_to_return[i] = now
                        if timestamps[i] != 0:
                            timings_to_return[i] = now - timestamps[i]
                else:
                    if angle_from_ref > angle and previous_angle < angle:
                        timestamps_to_return[i] = now
                        if timestamps[i] != 0:
                            timings_to_return[i] = now - timestamps[i]

                i += 1


        return timestamps_to_return, timings_to_return

    @staticmethod
    def reject_outliers(data, m = 6.):
        all_same = all(ele == data[0] for ele in data) 
        if all_same:
            return data
        d = np.abs(data - np.mean(data))
        mdev = np.mean(d)
        s = d/mdev if mdev else 0.
        filtered = data[s<m]
        if np.std(filtered, ddof=1) > MAX_STDEV:
            return []
            
        return data[s<m]


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
