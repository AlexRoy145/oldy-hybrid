import time
import matplotlib.pyplot as plt
import numpy.polynomial.polynomial as poly
from collections import deque

class Sample:
        
        def __init__(self, full_sample):
            self.full_sample = full_sample
            self.update_poly_sample()


        def get_trimmed_sample(self, vps):
            diff = len(self.poly_sample) - vps
            if diff > 0:
                return self.poly_sample[diff:]
            else:
                return self.poly_sample

        def update_poly_sample(self):
            poly_order = 5
            x = list(range(len(self.full_sample)))
            y = self.full_sample
            coefs = poly.polyfit(x, y, poly_order)
            ffit = poly.polyval(x, coefs)
            self.poly_sample = [int(round(x)) for x in ffit]

        def __len__(self):
            return len(self.full_sample)


        def __str__(self):
            return str(self.full_sample)


class BallSample:

    REV_TOLERANCE = 100

    def __init__(self):
        # array of ints representing milliseconds of ball rev times
        initial_sample = [567, 601, 673, 746, 884, 1083, 1268, 1402, 1502, 1652, 1735, 1885, 2052]
        initial_sample = Sample(initial_sample)
        self.max_samples = 5
        self.samples = deque(maxlen=self.max_samples)
        self.samples.append(initial_sample)
        self.averaged_sample = self.samples[0]
        self.vps = 13
        self.end_difference = 1000


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

                if smallest_diff < BallSample.REV_TOLERANCE:
                    results.append({"sample_idx" : i,
                                    "smallest_diff" : smallest_diff,
                                    "rev_idx" : lowest_idx})

            results.sort(key=lambda x: x["smallest_diff"])
            if results:
                best_result = results[0]
                sample = self.samples[best_result["sample_idx"]].get_trimmed_sample(self.vps)
                sample_rev = best_result["rev_idx"]
                print(f"Using sample #{best_result['sample_idx']}: {sample} and rev {sample[sample_rev]} for prediction.")
                return sum(sample[sample_rev + 1:]) + self.end_difference
            else:
                return -1
        else:
            return -1


    
    def get_fall_time_averaged(self, observed_rev):
        if self.averaged_sample:
            averaged_sample = self.averaged_sample.get_trimmed_sample(self.vps)
            differences = []
            for i, sample_rev in enumerate(averaged_sample):
                diff = abs(observed_rev - sample_rev)
                differences.append(diff)

            smallest_diff = min(differences)
            lowest_idx = differences.index(smallest_diff)

            if smallest_diff < BallSample.REV_TOLERANCE:
                return sum(averaged_sample[lowest_idx + 1:]) + self.end_difference
            else:
                return -1
        else:
            return -1

    
    def update_sample(self, new_sample):
        # determine if monotonic
        l = new_sample
        if all(l[i] <= l[i+1] for i in range(len(l)-1)):

            # determine if sample is VPS correct
            if len(l) >= self.vps:
                self.samples.append(Sample(new_sample))
                print(f"Sample updated: {new_sample}")
                self.update_averaged_sample()
            else:
                print(f"Not updating ball sample because last spin had {len(l)} vps, but sample VPS is {self.vps}.")
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
            self.averaged_sample = Sample(new_averaged_sample)

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
                y = sample.poly_sample
                plt.plot(x, y, label = f"Sample #{i}")
                plt.scatter(x, y)

            x = list(range(longest_sample_len, longest_sample_len - len(self.averaged_sample.full_sample), -1))[::-1]
            y = self.averaged_sample.poly_sample
            plt.plot(x, y, label = f"Averaged Sample")
            plt.scatter(x, y)

            plt.xticks(range(1, longest_sample_len + 1))
            plt.yticks(range(500, 2300, 100))
            plt.xlabel("Revs")
            plt.ylabel("Rev duration in MS")
            plt.title("Samples")
            plt.legend()
            plt.grid()
            plt.show()
