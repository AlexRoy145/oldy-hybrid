import time
from collections import deque


class BallSample:

    def __init__(self):
        # array of ints representing milliseconds of ball rev times
        self.max_samples = 3
        self.samples = deque(maxlen=self.max_samples)
        self.samples.append([567, 601, 673, 746, 884, 1083, 1268, 1402, 1502, 1652, 1735, 1885, 2052])
        self.averaged_sample = self.samples[0]
        self.vps = 13
        self.end_difference = 1000
        self.rev_tolerance = 50 # the MS that an observed_rev needs to be within a corresponding sample_rev in order to qualify to be predicted

    
    def get_fall_time(self, observed_rev):
        averaged_sample = self.averaged_sample
        differences = []
        for i, sample_rev in enumerate(averaged_sample):
            diff = abs(observed_rev - sample_rev)
            differences.append(diff)

        smallest_diff = min(differences)
        lowest_idx = differences.index(smallest_diff)

        if smallest_diff < self.rev_tolerance:
            return sum(averaged_sample[lowest_idx + 1:]) + self.end_difference
        else:
            return -1


    
    def update_sample(self, new_sample):
        # determine if monotonic
        l = new_sample
        if all(l[i] <= l[i+1] for i in range(len(l)-1)):

            # determine if sample is VPS correct
            if len(l) >= self.vps:
                if len(l) > self.vps:
                    self.samples.append(new_sample[len(l) - self.vps:])

                elif len(l) == self.vps:
                    self.samples.append(new_sample)

                self.update_averaged_sample()


    def update_averaged_sample(self):
        new_averaged_sample = []
        for j in range(len(self.samples[0])):
            averaged_rev = 0
            for i in range(len(self.samples)):
                averaged_rev += self.samples[i][j]

            averaged_rev /= len(self.samples)
            new_averaged_sample.append(averaged_rev)

        print(f"New averaged sample: {new_averaged_sample}")
        self.averaged_sample = new_averaged_sample


    def change_vps(self, new_vps):
        if new_vps > self.vps:
            print(f"Older samples with values fewer than {new_vps} will be deleted.")
            self.samples = [x for x in self.samples if len(x) < new_vps]

        elif new_vps < self.vps:
            print(f"Older samples with values greater than {new_vps} will be deleted.")
            self.samples = [x for x in self.samples if len(x) > new_vps]
            
        self.vps = new_vps
