class Message:
    direction = "n"
    test_mode = False
    prediction = -1
    error = False
    seq_num = 0

    def __str__(self):
        s = f"Direction: {self.direction}\nTest Mode: {self.test_mode}\nPrediction: {self.prediction}\nError: {self.error}\nSequence number: {self.seq_num}\n"
        return s
