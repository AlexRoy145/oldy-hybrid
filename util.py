import math
import time as t

class Util:

    @staticmethod
    def get_angle(a, b, c):
        ang = math.degrees(math.atan2(c[1]-b[1], c[0]-b[0]) - math.atan2(a[1]-b[1], a[0]-b[0]))
        return (ang + 360) if ang < 0 else ang

    @staticmethod
    def get_distance(a, b):
        return math.sqrt( (a[0] - b[0])**2 + (a[1] - b[1])**2 )

    @staticmethod
    def time():
        return t.time_ns() / 1000000000
