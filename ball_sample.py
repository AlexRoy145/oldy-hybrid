import time
import matplotlib.pyplot as plt
import numpy.polynomial.polynomial as poly
from collections import deque

MINIMUM_REV_SPEED_FOR_DIFF = 750

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
            # TODO: miracle math to adjust sample to target time, then poly the result
            '''
            ratio = self.full_sample[-1] / self.target_time
            self.adjusted_sample = [int(round(x / ratio)) for x in self.full_sample]

            poly_order = 5
            x = list(range(len(self.full_sample)))
            y = self.adjusted_sample
            coefs = poly.polyfit(x, y, poly_order)
            ffit = poly.polyval(x, coefs)
            self.adjusted_sample = [int(round(x)) for x in ffit]
            self.adjusted_sample[-1] = self.target_time
            '''
            # normal averaging
            poly_order = 5
            x = list(range(len(self.full_sample)))
            y = self.full_sample
            coefs = poly.polyfit(x, y, poly_order)
            ffit = poly.polyval(x, coefs)
            self.adjusted_sample = [int(round(x)) for x in ffit]


        def __len__(self):
            return len(self.full_sample)


        def __str__(self):
            return str(self.full_sample)


class BallSample:

    REV_TOLERANCE = 20

    def __init__(self):
        # array of ints representing milliseconds of ball rev times
        self.target_time = 2250
        self.end_difference = 1000
        initial_sample = [567, 601, 673, 746, 884, 1083, 1268, 1402, 1502, 1652, 1735, 1885, 2052]
        initial_sample = Sample(initial_sample, self.target_time)
        self.max_samples = 4
        self.samples = deque(maxlen=self.max_samples)
        self.samples.append(initial_sample)
        self.averaged_sample = self.samples[0]
        self.vps = 13


    def get_associated_rev(self, timings, sample):
        trimmed_sample = sample.get_trimmed_sample(self.vps)
        total_errors = []
        for i in range(len(trimmed_sample) - len(timings) + 1):
            total_error = 0
            j = i
            for timing in timings:
                total_error += abs(timing - trimmed_sample[j])
                j += 1

            total_errors.append(total_error)

        smallest_error = min(total_errors)
        associated_rev = total_errors.index(smallest_error)
        #print(f"Smallest error: {smallest_error}, Associated rev: {associated_rev}")
        return associated_rev


    # uses all past samples and identifies closest match based on two given points
    def get_fall_time(self, timings):
        if self.samples:
            first_sample_rev = self.averaged_sample.get_trimmed_sample(self.vps)[0]
            if timings[0] < first_sample_rev and abs(timings[0] - first_sample_rev) > BallSample.REV_TOLERANCE:
                return -1
            '''Step 1: identify which revs in each sample lines up most closely with the observed timings'''
            ''' Algorithm:
                1) Given the input timings, calculate the total error starting with the first rev in the sample:
                    So if the sample is 500,600,700,800,etc and the input timings are 570, 600, then the total error for each rev is as follows:
                    Rev 1: abs(570 - 500) + abs(600 - 600) = 70
                    Rev 2: abs(570 - 600) + abs(600 - 700) = 130
                    Rev 3: abs(570 - 700) + abs(600 - 800) = 330

                    So as you can see, even though the starting input timing is 570 which is closer to 600, we actually want to associate the
                    input timing with rev 1, and not rev 2. The idea is that the observed ball timings are likelier to be associated with the
                    rev with the least total error, rather than just the rev that happens to be closest to the first timing.

                2) Once all total errors are calculated, find the rev with the least total error for each sample and append the sample/rev tuple
                    to the list that represents all of them.
            '''

            sample_rev_dict_list = []
            for sample in self.samples:
                sample_rev_dict_list.append({"sample" : sample, "associated_rev" : self.get_associated_rev(timings, sample)})

            #print(sample_rev_dict_list)
            #print(timings)

            '''Step 2: Compare the slopes of the observed timings with the slopes of each sample's associated revs'''
            ''' Algorithm:
                1) For each sample, calculate the slopes of the associated revs, where the number of slopes to calculate is the number of
                    input timings minus 1.

                2) Compare the slopes of the input timings to the slopes of the associated revs in the sample. Again, compute the total error
                    for the slopes as we did to determine the associated revs.

                3) Once all total errors are calculated, find the SAMPLE with the least total error for the slopes, and use that sample to
                    calculate fall time.
            '''

            total_slope_errors = []
            for idx, item in enumerate(sample_rev_dict_list):
                trimmed_sample = item["sample"].get_trimmed_sample(self.vps)
                associated_rev = item["associated_rev"]
                
                sample_slopes = []
                i = associated_rev
                while i < associated_rev + len(timings) - 1:
                    sample_slopes.append(trimmed_sample[i+1] - trimmed_sample[i])
                    i += 1

                timing_slopes = []
                for i in range(len(timings) - 1):
                    timing_slopes.append(timings[i+1] - timings[i])

                slope_error = 0
                for sample_slope, timing_slope in zip(timing_slopes, sample_slopes):
                    slope_error += abs(sample_slope - timing_slope)

                total_slope_errors.append({"trimmed_sample" : trimmed_sample, "slope_error" : slope_error, "associated_rev" : associated_rev, "sample_idx" : idx})

            #print(total_slope_errors)
                    
            least_slope_error_dict = min(total_slope_errors, key=lambda x : x["slope_error"])
            target_trimmed_sample = least_slope_error_dict["trimmed_sample"]
            target_associated_rev = least_slope_error_dict["associated_rev"]
            sample_idx = least_slope_error_dict["sample_idx"]
            target_rev = target_associated_rev + len(timings)

            print(f"Used sample #{sample_idx} and associated rev {target_associated_rev} to predict.")

            fall_time = sum(target_trimmed_sample[target_rev:])
            return fall_time + self.end_difference


    '''
    def get_fall_time(self, observed_revs):
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
    '''


    '''
    def get_fall_time_averaged(self, observed_rev):
        if self.averaged_sample:
            averaged_sample = self.averaged_sample.get_trimmed_sample(self.vps)
            target_idx = -1
            for i, sample_rev in enumerate(averaged_sample):
                if observed_rev < sample_rev:
                    target_idx = i - 1
                    break

            if target_idx >= 0:
                # also add the difference between observed and target to fall time, SHOULD ALWAYS BE POSITIVE
                diff = observed_rev - averaged_sample[target_idx]
                print(f"Associating observed timing {observed_rev} with sample timing {averaged_sample[target_idx]}")
                return sum(averaged_sample[target_idx + 1:]) + diff
            else:
                return -1
        else:
            return -1
    '''

    
    def get_fall_time_averaged(self, observed_rev):
        if self.averaged_sample:
            averaged_sample = self.averaged_sample.get_trimmed_sample(self.vps)
            differences = []
            for i, sample_rev in enumerate(averaged_sample):
                # the observed_rev must be GREATER than the sample rev if it's fast
                # the reason for this is that the algorithm will confuse seeing a 600 rev with a higher rev sometimes because
                # the differences between revs are smaller
                # so if observed_rev is smaller than sample_rev, it will be negative and we will ignore that when looking at smallest differences
                if observed_rev < MINIMUM_REV_SPEED_FOR_DIFF:
                    diff = observed_rev - sample_rev
                else:
                    diff = abs(observed_rev - sample_rev)

                differences.append(diff)

            smallest_diff = min(differences)
            lowest_idx = differences.index(smallest_diff)

            if smallest_diff < BallSample.REV_TOLERANCE and smallest_diff >= 0:
                print(f"Associating observed timing {observed_rev} with sample timing {averaged_sample[lowest_idx]}")
                return sum(averaged_sample[lowest_idx + 1:]) + self.end_difference
            else:
                return -1
        else:
            return -1

    
    def update_sample(self, new_sample):
        # determine if monotonic
        l = new_sample
        '''
        if l[-1] > self.target_time:
            print("Not updating ball sample because last timing is greater than target time.")
            print(f"Sample: {new_sample}")
            return
        '''

        if all(l[i] <= l[i+1] for i in range(len(l)-1)):

            # determine if sample is VPS correct
            if len(l) >= self.vps:
                self.samples.append(Sample(new_sample, self.target_time))
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
                plt.plot(x, y, label = f"Sample #{i}")
                plt.scatter(x, y)

            x = list(range(longest_sample_len, longest_sample_len - len(self.averaged_sample.full_sample), -1))[::-1]
            y = self.averaged_sample.adjusted_sample
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
