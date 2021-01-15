import math
import time as t

class SpinData:
    
    def __init__(self, direction, diamond_hit, ball_revs, rotor_speed):
        self.direction = direction
        self.diamond_hit = diamond_hit
        self.ball_revs = ball_revs
        self.rotor_speed = rotor_speed


class Util:

    EUROPEAN_WHEEL = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]

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


    @staticmethod
    def calculate_rotor(direction, green_point, degrees, rotor_measure_duration, fall_time_from_now, reference_diamond, rotor_acceleration, wheel_center_point):
        # first get the measured speed of the rotor in degrees/second
        speed = degrees / rotor_measure_duration

        # get the degree offset green is from the reference diamond
        # if degree_offset is less than 180, green is ABOVE reference diamond, assuming ref diamond is to the right
        # if degree_offset is more than 180, green is BELOW reference diamond, assuming ref diamond is to the right
        degree_offset = Util.get_angle(green_point, wheel_center_point, reference_diamond)

        # now calculate where the green 0 will be in fall_time_from_now seconds
        full_degrees_green_travels = (speed * fall_time_from_now + .5 * rotor_acceleration * (fall_time_from_now ** 2))
        degrees_green_travels = (speed * fall_time_from_now + .5 * rotor_acceleration * (fall_time_from_now ** 2)) % 360

        if direction == "anticlockwise":
            degree_offset_after_travel = (degree_offset + degrees_green_travels) % 360
        else:
            new_offset = degree_offset - degrees_green_travels
            degree_offset_after_travel = (new_offset + 360) if new_offset < 0 else new_offset

        # this is used to compare how off the raw is at ball fall beep
        green_calculated_offset = degree_offset_after_travel

        # degree_offset_after_travel now represents where green is at the moment of ball fall
        # now calculate what number is under the reference diamond
        try:
            if degree_offset_after_travel >= 180:
                # if green is BELOW ref diamond, go to the left of the green to find raw
                ratio_to_look = (360 - degree_offset_after_travel) / 360
                idx = int(round(len(Util.EUROPEAN_WHEEL) * ratio_to_look))
                raw = Util.EUROPEAN_WHEEL[-idx]
            else:
                # if green is ABOVE ref diamond, go to the right of the green to find raw
                ratio_to_look = degree_offset_after_travel / 360
                idx = int(round(len(Util.EUROPEAN_WHEEL) * ratio_to_look))
                raw = Util.EUROPEAN_WHEEL[idx]
        except Exception as e:
            print(f"EXCEPTION: {e}")
            print(f"SPEED: {speed} degrees/second")
            print(f"Duration: {rotor_measure_duration}")
            print(f"degrees measured: {degrees}")
            print(f"degree_offset: {degree_offset}")
            print(f"degrees_green_travels: {degrees_green_travels}")
            print(f"degree_offset_after_travel: {degree_offset_after_travel}")
            print(f"ratio_to_look: {ratio_to_look}")
            print(f"idx: {idx}")

            return 0

        '''
        print(f"SPEED: {speed} degrees/second")
        print(f"Duration: {rotor_measure_duration}")
        print(f"degrees measured: {degrees}")
        print(f"degree_offset: {degree_offset}")
        print(f"degrees_green_travels: {degrees_green_travels}")
        print(f"FULL degrees green travels: {full_degrees_green_travels}")
        print(f"degree_offset_after_travel: {degree_offset_after_travel}")
        print(f"ratio_to_look: {ratio_to_look}")
        print(f"idx: {idx}")
        print(f"Rotor accel: {rotor_acceleration}")
        '''

        return {"raw" : raw,
                "green_calculated_offset" : green_calculated_offset}
