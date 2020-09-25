class Message:
    direction = ""
    test_mode = False
    prediction = -1
    error_msg = ""

    def __str__(self):
        s = f"Direction: {self.direction}\nTest Mode: {self.test_mode}\nPrediction: {self.prediction}\nError Message: {self.error_msg}"
        return s
