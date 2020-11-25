import cv2
import imutils
import math
import numpy as np
import time as t
from collections import deque
from PIL import Image


GREEN_LOWER = (29, 86, 6)
GREEN_UPPER = (64, 255, 255)
GIVE_UP_LOOKING_FOR_RAW = 10 #seconds
TIME_FOR_STABLE_DIRECTION = 1.5 #seconds
MAX_MISDETECTIONS_BEFORE_RESETTING_STATE = 60
DIFF_RATIO = 9
MORPH_KERNEL_RATIO = .0005
LOOKBACK = 30
DELAY_FOR_RAW_UPDATE = .1
ROTOR_ANGLE_ELLIPSE = 100

class Rotor:

    @staticmethod
    def start_capture(in_queue, out_queue, wheel_detection_zone, wheel_detection_area, wheel_center_point, reference_diamond_point, diff_thresh):
        # ROTOR VARS
        pts = deque(maxlen=LOOKBACK)
        current_direction = ""
        seen_direction_change_start_time = None
        seen_direction_start_time = None

        watch_for_direction_change = False
        direction_change_stable = False
        direction_changed = False
        direction_confirmed = False
        misdetections = 0
        kernel_size = int((MORPH_KERNEL_RATIO * wheel_detection_area)**.5)

        counter = 0
        frames_seen = 0
        bbox = wheel_detection_zone
        width = bbox[2]-bbox[0]
        height = bbox[3]-bbox[1]
        wheel_center = wheel_center_point
        ref_diamond = reference_diamond_point

        # rotor calculation vars
        rotor_start_point = None
        rotor_end_point = None
        rotor_measure_start_time = 0
        rotor_measure_complete_timestamp = 0
        rotor_measure_duration = 0
        degrees = 0

        # ball vars
        fall_time = -1
        fall_time_timestamp = -1
        sent_fall = False
        EPSILON = 50 #ms

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
            frame = np.array(frame)

            if fall_time < 0:
                if "fall_time" in in_msg:
                    fall_time = in_msg["fall_time"]
                    fall_time_timestamp = in_msg["fall_time_timestamp"]
            

            blurred = cv2.GaussianBlur(frame, (11, 11), 0)
            hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

            mask = cv2.inRange(hsv, GREEN_LOWER, GREEN_UPPER)
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

                    # Code to determine if we need to send rotor position out
                    if fall_time > 0:
                        elapsed_time = (Rotor.time() - fall_time_timestamp) * 1000
                        if not sent_fall and abs(elapsed_time - fall_time) < EPSILON:
                            out_queue.put({"state" : "green_position_update", "green_position" : center})
                            sent_fall = True

                    
                    if direction_change_stable:
                        if not rotor_start_point:
                            rotor_start_point = center
                            rotor_measure_start_time = Rotor.time()
                        elif not rotor_end_point:
                            # calculate how many degrees have been measured since rotor_start_point
                            degrees = Rotor.get_angle(rotor_start_point, wheel_center, center)
                            if degrees > 180:
                                degrees = 360 - degrees
                            if degrees >= ROTOR_ANGLE_ELLIPSE:
                                rotor_end_point = center
                                rotor_measure_complete_timestamp = Rotor.time()
                                rotor_measure_duration = rotor_measure_complete_timestamp - rotor_measure_start_time

                                out_msg = {"state" : "rotor_measure_complete", 
                                            "rotor_start_point" : rotor_start_point,
                                            "rotor_end_point" : rotor_end_point,
                                            "rotor_measure_complete_timestamp" : rotor_measure_complete_timestamp,
                                            "rotor_measure_duration" : rotor_measure_duration,
                                            "degrees" : degrees}

                                out_queue.put(out_msg)


                else:
                    misdetections += 1
            else:
                misdetections += 1

            if misdetections > MAX_MISDETECTIONS_BEFORE_RESETTING_STATE:
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

            if len(pts) == LOOKBACK: 
                previous = pts[-1]
                current = pts[0]

                dx = previous[0] - current[0]
                dy = previous[1] - current[1]

                if np.abs(dx) > diff_thresh or np.abs(dy) > diff_thresh:
                    # get direction of wheel movement
                    is_anticlockwise = ((previous[0] - wheel_center[0]) * (current[1] - wheel_center[1]) - 
                                        (previous[1] - wheel_center[1]) * (current[0] - wheel_center[0])) < 0;


                    if is_anticlockwise:
                        if current_direction == "clockwise":
                            # if we've already seen the direction change once, reset state as its unstable
                            if direction_changed:
                                direction_changed = False
                            else:
                                if Rotor.time() - seen_direction_start_time > TIME_FOR_STABLE_DIRECTION:
                                    direction_changed = True
                                    seen_direction_change_start_time = Rotor.time()
                                else:
                                    # initial direction changed too rapidly
                                    current_direction = ""
                        if current_direction == "":
                            seen_direction_start_time = Rotor.time()
                            
                        current_direction = "anticlockwise"
                    else:
                        if current_direction == "anticlockwise":
                            if direction_changed:
                                direction_changed = False
                            else:
                                if Rotor.time() - seen_direction_start_time > TIME_FOR_STABLE_DIRECTION:
                                    direction_changed = True
                                    seen_direction_change_start_time = Rotor.time()
                                else:
                                    current_direction = ""
                        if current_direction == "":
                            seen_direction_start_time = Rotor.time()

                        current_direction = "clockwise"

            if direction_changed:
                duration = Rotor.time() - seen_direction_change_start_time
                if duration > TIME_FOR_STABLE_DIRECTION:
                    direction_change_stable = True
                    spin_start_time = Rotor.time()
                    # reset some state so this block doesn't happen again
                    direction_changed = False

                    out_msg = {"state" : "direction_change_stable", "direction" : current_direction}
                    out_queue.put(out_msg)


            cv2.putText(frame, current_direction, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 3)
            # show the frame to our screen
            cv2.circle(frame, wheel_center, 15, (0, 0, 255), -1)
            cv2.circle(frame, ref_diamond, 5, (0, 0, 255), -1)
            #cv2.imshow("Wheel Detection", frame)
            key = cv2.waitKey(1) & 0xFF
            frames_seen = (frames_seen + 1) % (MAX_MISDETECTIONS_BEFORE_RESETTING_STATE + 2)

            if frames_seen == 0:
                misdetections = 0
            if counter <= LOOKBACK:
                counter += 1



    @staticmethod
    def measure_rotor_acceleration(in_queue, out_queue, wheel_detection_zone, wheel_detection_area, wheel_center_point, reference_diamond_point, diff_thresh):

        rotor_start_point = None
        rotor_end_point = None
        rotor_measure_start_time = 0
        rotor_measure_duration = 0
        rotor_measure_complete_timestamp = 0
        initial_speed = 0
        ending_speed = 0
        total_degrees = 0
        kernel_size = int((MORPH_KERNEL_RATIO * wheel_detection_area)**.5)

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
            frame = np.array(frame)

            blurred = cv2.GaussianBlur(frame, (11, 11), 0)
            hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

            mask = cv2.inRange(hsv, GREEN_LOWER, GREEN_UPPER)
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
                    
                    if not rotor_start_point:
                        rotor_start_point = center
                        rotor_measure_start_time = Rotor.time()
                    elif not rotor_end_point:
                        # calculate how many degrees have been measured since rotor_start_point
                        degrees = Rotor.get_angle(rotor_start_point, wheel_center_point, center)
                        if degrees > 180:
                            degrees = 360 - degrees
                        if degrees >= 175:
                            rotor_end_point = center
                            rotor_measure_complete_timestamp = Rotor.time()
                            rotor_measure_duration = rotor_measure_complete_timestamp - rotor_measure_start_time
                            print(f"Degrees: {degrees}")
                            print(f"Duration: {rotor_measure_duration}")

                            if not initial_speed:
                                initial_speed = degrees / rotor_measure_duration
                                total_degrees += degrees
                                rotor_start_point = rotor_end_point
                                rotor_end_point = None
                                rotor_measure_start_time = Rotor.time()
                                print(f"Initial speed: {initial_speed} degrees/second")
                            else:
                                ending_speed = degrees / rotor_measure_duration
                                total_degrees += degrees
                                acceleration = ( ending_speed ** 2 - initial_speed ** 2 ) / ( 2 * total_degrees )
                                print(f"Ending speed: {ending_speed} degrees/second")
                                out_queue.put({"state" : "done", "acceleration" : acceleration})
                                cv2.destroyAllWindows()
                                return


            # show the frame to our screen
            cv2.circle(frame, wheel_center_point, 15, (0, 0, 255), -1)
            cv2.circle(frame, reference_diamond_point, 5, (0, 0, 255), -1)
            cv2.imshow("Wheel Detection", frame)
            key = cv2.waitKey(1) & 0xFF




    @staticmethod
    def get_angle(a, b, c):
        ang = math.degrees(math.atan2(c[1]-b[1], c[0]-b[0]) - math.atan2(a[1]-b[1], a[0]-b[0]))
        return (ang + 360) if ang < 0 else ang


    @staticmethod
    def time():
        return t.time_ns() / 1000000000
