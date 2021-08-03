import time
import matplotlib.pyplot as plt
import numpy.polynomial.polynomial as poly
from collections import deque

MINIMUM_REV_SPEED_FOR_DIFF = 750


class Sample:

    def __init__(self, full_sample, target_time, direction, averaged=False):
        self.target_time = target_time
        self.full_sample = full_sample
        self.direction = direction
        if averaged:
            self.adjusted_sample = full_sample
        else:
            self.adjust_sample()

    def get_trimmed_sample(self, vps):
        diff = len(self.adjusted_sample) - vps
        if diff > 0:
            return self.adjusted_sample[diff:]
        else:
            return self.adjusted_sample

    def adjust_sample(self):
        # TODO: miracle math to adjust sample to target time, then poly the result
        '''
            ratio = self.target_time / self.full_sample[-1] 
            self.adjusted_sample = [int(round(x * ratio)) for x in self.full_sample]
            '''

        '''
            poly_order = 5
            x = list(range(len(self.full_sample)))
            y = self.adjusted_sample
            coefs = poly.polyfit(x, y, poly_order)
            ffit = poly.polyval(x, coefs)
            self.adjusted_sample = [int(round(x)) for x in ffit]
            self.adjusted_sample[-1] = self.target_time
            '''

        # the below does simple translation
        '''
            delta = self.full_sample[-1] - self.target_time
            self.adjusted_sample = [x - delta for x in self.full_sample]
            '''

        self.adjusted_sample = self.full_sample
        # return

        # normal averaging
        '''
            poly_order = 5
            x = list(range(len(self.full_sample)))
            y = self.full_sample
            coefs = poly.polyfit(x, y, poly_order)
            ffit = poly.polyval(x, coefs)
            self.adjusted_sample = [int(round(x)) for x in ffit]
            '''

    def __len__(self):
        return len(self.full_sample)

    def __str__(self):
        return str(self.full_sample)


class BallSample:

    def __init__(self):
        # array of ints representing milliseconds of ball rev times
        self.target_time = 2120
        self.end_difference_anti = 0
        self.end_difference_clock = 0

        initial_sample = [567, 601, 673, 746, 884, 1083, 1268, 1402, 1502, 1652, 1735, 1885, 2052]
        initial_sample_anti = Sample(initial_sample, self.target_time, "anticlockwise")
        initial_sample_clock = Sample(initial_sample, self.target_time, "clockwise")

        self.max_samples_anti = 4
        self.max_samples_clock = 4
        self.samples_anti = deque(maxlen=self.max_samples_anti)
        self.samples_clock = deque(maxlen=self.max_samples_clock)

        self.samples_anti.append(initial_sample_anti)
        self.samples_clock.append(initial_sample_clock)
        self.averaged_sample_anti = self.samples_anti[0]
        self.averaged_sample_clock = self.samples_clock[0]

        self.vps_anti = 10
        self.vps_clock = 10
        self.rev_tolerance_anti = 50
        self.rev_tolerance_clock = 50

    def get_fall_time_averaged(self, observed_rev, direction):
        if "a" in direction:
            averaged_sample = self.averaged_sample_anti.get_trimmed_sample(self.vps_anti)
            end_diff = self.end_difference_anti
            rev_tolerance = self.rev_tolerance_anti
        else:
            averaged_sample = self.averaged_sample_clock.get_trimmed_sample(self.vps_clock)
            end_diff = self.end_difference_clock
            rev_tolerance = self.rev_tolerance_clock

        if averaged_sample:
            if observed_rev < averaged_sample[0]:
                return -1

            sample_idx = -1
            for i, sample_rev in enumerate(averaged_sample):
                if i < len(averaged_sample) - 1:
                    if sample_rev <= observed_rev <= averaged_sample[i + 1]:
                        sample_idx = i
                        break
                else:
                    return -1

            sample_start_timing = averaged_sample[sample_idx]
            sample_end_timing = averaged_sample[sample_idx + 1]

            sample_diff = sample_end_timing - sample_start_timing
            observed_diff = observed_rev - sample_start_timing

            ball_ratio = observed_diff / sample_diff
            print(f"Ball ratio: {ball_ratio:.2f}")

            first_add = int(round(sample_end_timing * (1 - ball_ratio)))
            print(f"Added timing sum {first_add} instead of the next timing {sample_end_timing}")

            # print(f"Associating observed timing {observed_rev} with sample timing {averaged_sample[lowest_idx]}")
            print(f"Summing the following: {averaged_sample[sample_idx + 2:]} as well as {first_add}")
            return sum(averaged_sample[sample_idx + 2:], first_add) + end_diff
        else:
            return -1

    def update_sample(self, new_sample, direction):
        # determine if monotonic
        l_sample = new_sample
        '''
        if l[-1] > self.target_time:
            print("Not updating ball sample because last timing is greater than target time.")
            print(f"Sample: {new_sample}")
            return
        '''

        if "a" in direction:
            samples = self.samples_anti
            vps = self.vps_anti
        else:
            samples = self.samples_clock
            vps = self.vps_clock

        if all(l_sample[i] <= l_sample[i + 1] for i in range(len(l_sample) - 1)):

            # determine if sample is VPS correct
            if len(l_sample) >= vps:
                samples.append(Sample(new_sample, self.target_time, direction))
                print(f"Sample updated: {new_sample}")
                self.update_averaged_sample(direction)
            else:
                print(f"Not updating ball sample because last spin had {len(l_sample)} vps, but sample VPS is {vps}.")
                print(f"Sample: {new_sample}")

        else:
            print(f"Not updating ball sample because sample was not monotonically increasing.")
            print(f"Sample: {new_sample}")

    def update_averaged_sample(self, direction):
        if "a" in direction:
            vps = self.vps_anti
            samples = self.samples_anti
        else:
            vps = self.vps_clock
            samples = self.samples_clock

        new_averaged_sample = []
        for i in samples:
            print(i)
        if len(samples) > 0:
            for j in range(vps):
                averaged_rev = 0
                for i in range(len(samples)):
                    current_sample = samples[i].get_trimmed_sample(vps)
                    averaged_rev += current_sample[j]

                averaged_rev = round(averaged_rev / len(samples))
                new_averaged_sample.append(averaged_rev)

            print(f"New averaged sample: {new_averaged_sample}")
            averaged_sample = Sample(new_averaged_sample, self.target_time, direction, averaged=True)

        else:
            averaged_sample = []

        if "a" in direction:
            self.averaged_sample_anti = averaged_sample
        else:
            self.averaged_sample_clock = averaged_sample

    def change_vps(self, new_vps, direction):
        if "a" in direction:
            vps = self.vps_anti
            samples = self.samples_anti
            max_samples = self.max_samples_anti
        else:
            vps = self.vps_clock
            samples = self.samples_clock
            max_samples = self.max_samples_clock

        if new_vps > vps:
            print(f"Older samples with values fewer than {new_vps} will be deleted.")
            new_samples = deque(maxlen=max_samples)
            for sample in samples:
                if len(sample.full_sample) >= new_vps:
                    new_samples.append(sample)
                else:
                    print(f"Deleted sample {sample.full_sample}.")

            if "a" in direction:
                self.samples_anti = new_samples
            else:
                self.samples_clock = new_samples

        if "a" in direction:
            self.vps_anti = new_vps
        else:
            self.vps_clock = new_vps

        self.update_averaged_sample(direction)

    def change_max_samples(self, new_max_samples, direction):
        if "a" in direction:
            samples = self.samples_anti
        else:
            samples = self.samples_clock

        new_deque = deque(maxlen=new_max_samples)
        new_deque.extend(samples)

        if "a" in direction:
            self.max_samples_anti = new_max_samples
            self.samples_anti = new_deque
        else:
            self.max_samples_clock = new_max_samples
            self.samples_clock = new_deque

        self.update_averaged_sample(direction)

    def graph_samples(self, direction):
        if "a" in direction:
            samples = self.samples_anti
            averaged_sample = self.averaged_sample_anti
        else:
            samples = self.samples_clock
            averaged_sample = self.averaged_sample_clock

        if samples:
            longest_sample_len = max([len(x.full_sample) for x in samples])
            for i, sample in enumerate(samples):
                x = list(range(longest_sample_len, longest_sample_len - len(sample.full_sample), -1))[::-1]
                y = sample.adjusted_sample
                plt.plot(x, y, label=f"Sample #{i}")
                plt.scatter(x, y)

            x = list(range(longest_sample_len, longest_sample_len - len(averaged_sample.full_sample), -1))[::-1]
            y = averaged_sample.adjusted_sample
            plt.plot(x, y, label=f"Averaged Sample")
            plt.scatter(x, y)

            plt.xticks(range(1, longest_sample_len + 1))
            plt.yticks(range(500, 2300, 100))
            plt.xlabel("Revs")
            plt.ylabel("Rev duration in MS")
            plt.title(f"Samples for {direction}")
            plt.legend()
            plt.grid()
            plt.show()
