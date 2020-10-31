import ctypes
import os.path
import os
import mss
import time
import pickle
import autoit
from pathlib import Path
from pynput import mouse
from pynput import keyboard


class Macro:

    RED_THRESH = 150
    GREEN_THRESH = 200

    class MacroEvent:
        def __init__(self, x, y, duration, button):
            self.x = x
            self.y = y
            self.duration = duration
            self.button = button


    def __init__(self, profile_dir):
        self.m = mouse.Controller()
        self.k = keyboard.Controller()
        self.sct = mss.mss()
        self.macro = []
        self.screen_condition = None
        self.profile_dir = profile_dir
        if not os.path.isdir(self.profile_dir):
            os.mkdir(self.profile_dir)


    def load_profile(self, data_file):
        path = os.path.join(self.profile_dir, data_file)
        if os.path.isfile(path):
            with open(path, "rb") as f:
                self.__dict__.update(pickle.load(f))
            return True
        else:
            return False


    def save_profile(self, data_file):
        path = os.path.join(self.profile_dir, data_file)
        with open(path, "wb") as f:
            d = {"screen_condition" : self.screen_condition, "macro" : self.macro}
            pickle.dump(d, f)

    
    def set_screen_condition(self, green=False):
        if green:
            input("Hover over the green area for 'Place your bets' and press ENTER:")
        else:
            input("Hover over the red outside bet and press ENTER:")
        self.screen_condition = self.m.position


    def is_screen_condition_true(self, green=False):
        sct_img = self.sct.grab({"left": self.screen_condition[0], "top": self.screen_condition[1], "width": 1, "height": 1, "mon":0})
        pixel = sct_img.pixel(0, 0)
        if green:
            #print(f"pixel 0: {pixel[0]}, pixel 1: {pixel[1]}, pixel 2: {pixel[2]}")
            return pixel[1] > Macro.GREEN_THRESH and pixel[1] < 240
        return pixel[0] < Macro.RED_THRESH


    def on_click(self, x, y, button, pressed):
        if pressed:
            duration = time.perf_counter() - self.macro_start_time
            self.macro.append(self.MacroEvent(x, y, duration, button))
            self.macro_start_time = time.perf_counter()


    def record_macro(self):
        input(f"Record the macro. Only records mouse clicks for now. Press ENTER to start:")
        mouse_listener = mouse.Listener(on_click=self.on_click)
        mouse_listener.start()
        self.macro = []
        self.macro_start_time = time.perf_counter()
        input("Press ENTER when you are done recording:")
        mouse_listener.stop()


    def execute_macro(self, delay=None):
        try:
            for event in self.macro:
                if delay:
                    time.sleep(delay)
                else:
                    time.sleep(event.duration)
                self.m.position = event.x, event.y
                # use autoit.mouse_down("left") and autoit.mouse_up("left") along with sleep to do longer presses
                if event.button == mouse.Button.left:
                    autoit.mouse_click("left", event.x, event.y, 1) 
                elif event.button == mouse.Button.right:
                    autoit.mouse_click("right", event.x, event.y, 1) 
        except KeyError:
            print("That macro doesn't exist.")
