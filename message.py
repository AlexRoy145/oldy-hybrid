class Message:
    direction = "n"
    test_mode = False
    raw_prediction = -1
    tuned_predictions = []
    error = False
    seq_num = 0

    def __str__(self):
        s = f"Direction: {self.direction}\nTest Mode: {self.test_mode}\nRaw Prediction: {self.raw_prediction}\nTuned Predictions: {self.tuned_predictions}\nError: {self.error}\nSequence number: {self.seq_num}\n"
        return s
