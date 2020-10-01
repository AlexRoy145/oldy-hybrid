import os.path
import mss
import time
import pickle
from pynput import mouse
from pynput import keyboard

class Macro:

    RED_THRESH = 150

    class MacroEvent:
        def __init__(self, x, y, duration, button):
            self.x = x
            self.y = y
            self.duration = duration
            self.button = button


    def __init__(self):
        self.m = mouse.Controller()
        self.k = keyboard.Controller()
        self.sct = mss.mss()
        self.macros = {}
        self.screen_condition = None


    def load_profile(self, data_file):
        if os.path.isfile(data_file):
            with open(data_file, "rb") as f:
                self.__dict__.update(pickle.load(f))
            return True
        else:
            return False


    def save_profile(self, data_file):
        with open(data_file, "wb") as f:
            d = {"screen_condition" : self.screen_condition, "macros" : self.macros}
            pickle.dump(d, f)

    
    def set_screen_condition(self):
        input("Hover over the red outside bet and press ENTER:")
        self.screen_condition = m.position


    def is_screen_condition_true(self):
        sct_img = self.sct.grab({"left": self.screen_condition[0], "top": self.screen_condition[1], "width": 1, "height": 1, "mon":0})
        pixel = sct_img.pixel(0, 0)
        return pixel[0] < Macro.RED_THRESH


    def on_click(self, x, y, button, pressed):
        if pressed:
            duration = time.perf_counter() - self.macro_start_time
            self.macros[self.current_macro_name].append(self.MacroEvent(x, y, duration, button))
            self.macro_start_time = time.perf_counter()


    def record_macro(self, macro_name):
        input(f"Record the macro {macro_name}. Only records mouse clicks for now. Press ENTER to start:")
        mouse_listener = mouse.Listener(on_click=self.on_click)
        mouse_listener.start()
        self.current_macro_name = macro_name
        self.macros[macro_name] = []
        self.macro_start_time = time.perf_counter()
        input("Press ENTER when you are done recording:")
        mouse_listener.stop()


    def execute_macro(self, macro_name):
        try:
            for event in self.macros[macro_name]:
                time.sleep(event.duration)
                self.m.position = event.x, event.y
                self.m.click(event.button)
        except KeyError:
            print("That macro doesn't exist.")
