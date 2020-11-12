import time


class BallSample:

    def __init__(self):
        # array of ints representing milliseconds of ball rev times
        self.sample = [501, 567, 601, 673, 746, 884, 1083, 1268, 1402, 1502, 1652, 1735, 1885, 2052]
        self.end_difference = 0
        self.rev_tolerance = 50 # the MS that an observed_rev needs to be within a corresponding sample_rev in order to qualify to be predicted

    
    def get_fall_time(self, observed_rev):
        target_rev = -1
        for i, sample_rev in enumerate(self.sample):
            if abs(observed_rev - sample_rev) < self.rev_tolerance:
                target_rev = i
                break

        if target_rev != -1:
            fall_time = sum(self.sample[target_rev + 1:]) + self.end_difference
            return fall_time
        else:
            return -1

    
    def update_sample(self, new_sample):
        pass
