import time
import matplotlib.pyplot as plt
import numpy.polynomial.polynomial as poly
from collections import deque

MINIMUM_REV_SPEED_FOR_DIFF = 750

'''
This version of the ball sample class assumes we're getting
default samples from steve's hybrid. therefore, it only handles
one sample at a time (the averaged one from steve's) and has
a prediction/association algorithm that accounts for the default
sample algorithm
'''


class Sample:

    def __init__(self, full_sample, target_time, averaged=False):
        self.full_sample = full_sample
        self.target_time = target_time
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
        # adjust sample to target time
        # The below uses multiplicative ratios
        """
            ratio = self.target_time / self.full_sample[-1]
            self.adjusted_sample = [int(round(x * ratio)) for x in self.full_sample]

            poly_order = 4
            length = len(self.full_sample)
            if length > 10:
                poly_order = 5

            x = list(range(len(self.full_sample)))
            y = self.adjusted_sample
            coefs = poly.polyfit(x, y, poly_order)
            ffit = poly.polyval(x, coefs)
            self.adjusted_sample = [int(round(x)) for x in ffit]
            self.adjusted_sample[-1] = self.target_time
        """

        # the below does simple translation
        delta = self.full_sample[-1] - self.target_time
        self.adjusted_sample = [x - delta for x in self.full_sample]

        '''
            self.adjusted_sample = self.full_sample
            return
            '''

        '''
            # normal averaging
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
        self.end_difference = 0
        initial_sample = [567, 601, 673, 746, 884, 1083, 1268, 1402, 1502, 1652, 1735, 1885, 2052]
        initial_sample = Sample(initial_sample, self.target_time)
        self.max_samples = 1
        self.samples = deque(maxlen=self.max_samples)
        self.samples.append(initial_sample)
        self.averaged_sample = self.samples[0]
        self.vps = 10
        self.rev_tolerance = 50

    def get_fall_time_averaged(self, observed_rev):
        if self.averaged_sample:
            averaged_sample = self.averaged_sample.get_trimmed_sample(self.vps)
            differences = []

            if observed_rev > averaged_sample[0]:
                '''
                first_diff = averaged_sample[0] - observed_rev
                if first_diff < self.rev_tolerance:
                    smallest_diff = first_diff
                    lowest_idx = -1
                else:
                '''
                for i, sample_rev in enumerate(averaged_sample):
                    diff = abs(sample_rev - observed_rev)
                    differences.append(diff)

                smallest_diff = min(differences)
                lowest_idx = differences.index(smallest_diff)

                '''
                associated_idx = lowest_idx + 1
                revs_left = len(averaged_sample) - associated_idx + 1
                associated_sample_timing = averaged_sample[associated_idx]
                true_diff = abs(associated_sample_timing - observed_rev)
                to_subtract = -true_diff * revs_left
                '''
                to_subtract = 0

                if smallest_diff < self.rev_tolerance:
                    print(
                        f"Associating observed timing {observed_rev} with sample timing {averaged_sample[lowest_idx]}")
                    return sum(averaged_sample[lowest_idx + 1:], to_subtract) + self.end_difference
                else:
                    return -1
            else:
                return -1
        else:
            return -1

    '''
    def get_fall_time_averaged(self, observed_rev):
        if self.averaged_sample:
            averaged_sample = self.averaged_sample.get_trimmed_sample(self.vps)
            if observed_rev < averaged_sample[0]:
                return -1
            differences = []
            for i, sample_rev in enumerate(averaged_sample):
                diff = abs(observed_rev - sample_rev)
                differences.append(diff)

            smallest_diff = min(differences)
            lowest_idx = differences.index(smallest_diff)

            actual_diff = observed_rev - averaged_sample[lowest_idx]
            revs_left = len(averaged_sample) - lowest_idx + 1

            if smallest_diff < self.rev_tolerance:
                print(f"Associating observed timing {observed_rev} with sample timing {averaged_sample[lowest_idx]}")
                return sum(averaged_sample[lowest_idx + 1:], revs_left * actual_diff)
            else:
                return -1
        else:
            return -1
    '''

    def get_fall_time(self, observed_rev):
        if self.samples:
            differences = []
            for sample in self.samples:
                sample_diffs = []
                trimmed_sample = sample.get_trimmed_sample(self.vps)
                for i, sample_rev in enumerate(trimmed_sample):
                    diff = abs(observed_rev - sample_rev)
                    sample_diffs.append(diff)

                differences.append(sample_diffs)

            results = []
            for i, sample_diff in enumerate(differences):
                smallest_diff = min(sample_diff)
                lowest_idx = sample_diff.index(smallest_diff)

                if smallest_diff < self.rev_tolerance:
                    results.append({"sample_idx": i,
                                    "smallest_diff": smallest_diff,
                                    "rev_idx": lowest_idx})

            results.sort(key=lambda x: x["smallest_diff"])
            if results:
                best_result = results[0]
                sample = self.samples[best_result["sample_idx"]].get_trimmed_sample(self.vps)
                sample_rev = best_result["rev_idx"]
                print(
                    f"Using sample #{best_result['sample_idx']}: {sample} and rev {sample[sample_rev]} for prediction.")
                return sum(sample[sample_rev + 1:]) + self.end_difference
            else:
                return -1
        else:
            return -1

    def update_sample(self, new_sample):
        # determine if monotonic
        l_sample = new_sample
        '''
        if l[-1] > self.target_time:
            print("Not updating ball sample because last timing is greater than target time.")
            print(f"Sample: {new_sample}")
            return
        '''

        if all(l_sample[i] <= l_sample[i + 1] for i in range(len(l_sample) - 1)):

            # determine if sample is VPS correct
            if len(l_sample) >= self.vps:
                self.samples.append(Sample(new_sample, self.target_time))
                print(f"Sample updated: {new_sample}")
                self.update_averaged_sample()
            else:
                print(f"Not updating ball sample because last spin had {len(l_sample)} vps, " +
                      f"but sample VPS is {self.vps}.")
                print(f"Sample: {new_sample}")

        else:
            print(f"Not updating ball sample because sample was not monotonically increasing.")
            print(f"Sample: {new_sample}")

    def update_averaged_sample(self):
        new_averaged_sample = []
        for i in self.samples:
            print(i)
        if len(self.samples) > 0:
            for j in range(self.vps):
                averaged_rev = 0
                for i in range(len(self.samples)):
                    current_sample = self.samples[i].get_trimmed_sample(self.vps)
                    averaged_rev += current_sample[j]

                averaged_rev = round(averaged_rev / len(self.samples))
                new_averaged_sample.append(averaged_rev)

            print(f"New averaged sample: {new_averaged_sample}")
            self.averaged_sample = Sample(new_averaged_sample, self.target_time)

        else:
            self.averaged_sample = []

    def change_vps(self, new_vps):
        if new_vps > self.vps:
            print(f"Older samples with values fewer than {new_vps} will be deleted.")
            new_samples = deque(maxlen=self.max_samples)
            for sample in self.samples:
                if len(sample.full_sample) >= new_vps:
                    new_samples.append(sample)
                else:
                    print(f"Deleted sample {sample.full_sample}.")

            self.samples = new_samples

        self.vps = new_vps
        self.update_averaged_sample()

    def change_max_samples(self, new_max_samples):
        new_deque = deque(maxlen=new_max_samples)
        new_deque.extend(self.samples)
        self.max_samples = new_max_samples
        self.samples = new_deque
        self.update_averaged_sample()

    def graph_samples(self):
        if self.samples:
            longest_sample_len = max([len(x.full_sample) for x in self.samples])
            for i, sample in enumerate(self.samples):
                x = list(range(longest_sample_len, longest_sample_len - len(sample.full_sample), -1))[::-1]
                y = sample.adjusted_sample
                plt.plot(x, y, label=f"Sample #{i}")
                plt.scatter(x, y)

            x = list(range(longest_sample_len, longest_sample_len - len(self.averaged_sample.full_sample), -1))[::-1]
            y = self.averaged_sample.adjusted_sample
            plt.plot(x, y, label=f"Averaged Sample")
            plt.scatter(x, y)

            plt.xticks(range(1, longest_sample_len + 1))
            plt.yticks(range(500, 4000, 100))
            plt.xlabel("Revs")
            plt.ylabel("Rev duration in MS")
            plt.title("Samples")
            plt.legend()
            plt.grid()
            plt.show()
