import cv2
import mss
import numpy as np
from pynput import mouse
from PIL import Image
from util import Util

DIFF_RATIO = 9
DIAMONDS = ["twelve", "three", "six", "nine"]

class EllipticalDetectionZone:
    def __init__(self, wheel_bounding_box, reference_frame, outer_diamond_points, inner_diamond_points, angles=None):
        self.center = None
        self.reference_frame = np.array(Image.frombytes('RGB', reference_frame.size, reference_frame.rgb))
        self.reference_frame = cv2.cvtColor(self.reference_frame, cv2.COLOR_BGR2GRAY)
        self.reference_frame = cv2.GaussianBlur(self.reference_frame, (11, 11), 0)

        self.wheel_bounding_box = wheel_bounding_box
        self.outer_diamond_points = outer_diamond_points
        self.inner_diamond_points = inner_diamond_points

        mask = np.zeros_like(self.reference_frame)

        outer_ellipse_mask = self.get_ellipse(mask, outer_diamond_points, angles=angles)
        self.mask = self.get_ellipse(outer_ellipse_mask, inner_diamond_points, inner=True, angles=angles)
        self.reference_frame = np.bitwise_and(self.reference_frame, self.mask)
        cv2.imshow("ref zone", self.reference_frame)
        cv2.waitKey(0)

    def get_ellipse(self, mask, diamond_points, inner=False, angles=None):
        if not angles:
            start_angle = 0
            end_angle = 360
        else:
            start_angle = angles[0]
            end_angle = angles[1]
        x_average = int(round(sum([x[0] for x in diamond_points.values()]) / len(diamond_points)))
        y_average = int(round(sum([x[1] for x in diamond_points.values()]) / len(diamond_points)))
        if not self.center:
            self.center = x_average, y_average
        ninety_degree_point = self.center[0] + 10, self.center[1]
        ellipse_angle = Util.get_angle(ninety_degree_point, self.center, diamond_points["three"])
        axis_1 = int(round(Util.get_distance(diamond_points["three"], diamond_points["nine"]) / 2))
        axis_2 = int(round(Util.get_distance(diamond_points["twelve"], diamond_points["six"]) / 2))
        if inner:
            color = (0,0,0)
        else:
            color = (255,255,255)
        return cv2.ellipse(mask, self.center, axes=(axis_1,axis_2), angle=ellipse_angle, startAngle=start_angle, endAngle=end_angle, color=color, thickness=-1)

class SetDetection:
    
    @staticmethod
    def set_ball_detection_zone(wheel_detection_zone):
        m = mouse.Controller()
        print("Capture the ball detection zone. ENSURE THAT NO BALL IS PRESENT IN THE ZONE WHEN THE LAST ENTER IS PRESSED.")
        print("Capture the outer points of the ball detection points aligned with the diamonds.")
        outer_diamond_points = {}
        for diamond in DIAMONDS:
            input(f"Hover the mouse over the outermost point of the ball track aligned with the {diamond} o'clock diamond, then press ENTER: ")
            x, y = m.position
            x = x - wheel_detection_zone[0]
            y = y - wheel_detection_zone[1]
            outer_diamond_points[diamond] = x,y

        inner_diamond_points = {}
        for diamond in DIAMONDS:
            input(f"Hover the mouse over the innermost point of the {diamond} o'clock diamond, then press ENTER: ")
            x, y = m.position
            x = x - wheel_detection_zone[0]
            y = y - wheel_detection_zone[1]
            inner_diamond_points[diamond] = x,y

        # take screenshot to get first frame 
        bbox = wheel_detection_zone
        width = bbox[2]-bbox[0]
        height = bbox[3]-bbox[1]

        with mss.mss() as sct:
            frame = sct.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon":0})
            reference_frame = frame

        ball_detection_zone = EllipticalDetectionZone(wheel_detection_zone, reference_frame, outer_diamond_points, inner_diamond_points)
        return ball_detection_zone


    @staticmethod
    def set_ball_fall_detection_zone(wheel_detection_zone):
        m = mouse.Controller()
        print("Capture the ball fall zone. ENSURE THAT NO BALL IS PRESENT IN THE ZONE WHEN THE LAST ENTER IS PRESSED.")
        print("Capture the outermost points of the ball fall elliptical zone. These 4 points are the outermost points on the 4 vertical diamonds")
        outer_diamond_points = {}
        for diamond in DIAMONDS:
            input(f"Hover the mouse over the outermost point of the {diamond} o'clock diamond, then press ENTER: ")
            x, y = m.position
            x = x - wheel_detection_zone[0]
            y = y - wheel_detection_zone[1]
            outer_diamond_points[diamond] = x,y

        inner_diamond_points = {}
        for diamond in DIAMONDS:
            input(f"Hover the mouse over the innermost point of the {diamond} o'clock diamond, then press ENTER: ")
            x, y = m.position
            x = x - wheel_detection_zone[0]
            y = y - wheel_detection_zone[1]
            inner_diamond_points[diamond] = x,y

        # set wheel center here to be more accurate
        x_average = int(round(sum([x[0] for x in outer_diamond_points.values()]) / len(outer_diamond_points)))
        y_average = int(round(sum([x[1] for x in outer_diamond_points.values()]) / len(outer_diamond_points)))
        center = x_average, y_average
        wheel_center_point = center

        # take screenshot to get first frame 
        bbox = wheel_detection_zone
        width = bbox[2]-bbox[0]
        height = bbox[3]-bbox[1]

        with mss.mss() as sct:
            frame = sct.grab({"left": bbox[0], "top": bbox[1], "width": width, "height": height, "mon":0})
            reference_frame = frame

        ball_fall_detection_zone = EllipticalDetectionZone(wheel_detection_zone, reference_frame, outer_diamond_points, inner_diamond_points)
        return {"ball_fall_detection_zone" : ball_fall_detection_zone,
                "wheel_center_point" : wheel_center_point}


    @staticmethod
    def set_sample_detection_zone():
        m = mouse.Controller()
        zone = []
        input(f"Hover the mouse over the upper left corner of the detection zone for the sample, then hit ENTER.")
        x_top,y_top = m.position
        zone.append(x_top)
        zone.append(y_top)

        input("Hover the mouse over the bottom right corner of the detection zone, then hit ENTER.")
        x_bot,y_bot = m.position
        zone.append(x_bot)
        zone.append(y_bot)

        print(f"Bounding box: {zone}")
        return zone


    @staticmethod
    def set_wheel_detection_zone():
        m = mouse.Controller()
        zone = []
        input(f"Hover the mouse over the upper left corner of the detection zone for the WHEEL, then hit ENTER.")
        x_top,y_top = m.position
        zone.append(x_top)
        zone.append(y_top)

        input("Hover the mouse over the bottom right corner of the detection zone, then hit ENTER.")
        x_bot,y_bot = m.position
        zone.append(x_bot)
        zone.append(y_bot)

        wheel_detection_zone = zone
        print(f"Bounding box: {zone}")

        input(f"Hover the mouse over the the center of the pocket RIGHT UNDER the REFERENCE DIAMOND, then hit ENTER.")
        x_ref,y_ref = m.position
        x_ref -= zone[0]
        y_ref -= zone[1]
        reference_diamond_point = x_ref, y_ref

        diff_thresh = int((wheel_detection_zone[2] - wheel_detection_zone[0]) / DIFF_RATIO)
        print(f"diff_thresh: {diff_thresh}")
        bbox = wheel_detection_zone
        width = bbox[2]-bbox[0]
        height = bbox[3]-bbox[1]

        wheel_detection_area = width * height

        return {"wheel_detection_zone" : wheel_detection_zone,
                "reference_diamond_point" : reference_diamond_point,
                "diff_thresh" : diff_thresh,
                "wheel_detection_area": wheel_detection_area}


    @staticmethod
    def set_screenshot_zone():
        m = mouse.Controller()
        screenshot_zone = []
        zone = screenshot_zone
        input(f"Hover the mouse over the upper left corner for where to take a screenshot (betting board + acct balance), then hit ENTER.")
        x_top,y_top = m.position
        zone.append(x_top)
        zone.append(y_top)

        input("Hover the mouse over the bottom right corner of the screenshot area, then hit ENTER.")
        x_bot,y_bot = m.position
        zone.append(x_bot)
        zone.append(y_bot)

        print(f"Bounding box: {zone}")

