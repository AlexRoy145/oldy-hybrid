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

URL_TRANSLATION_FILE = "lobby_urls.txt"

class Macro:

    RED_THRESH = 150
    GREEN_THRESH = 200

    class MacroEvent:
        def __init__(self, x, y, duration, button, keyboard_macro_type):
            self.x = x
            self.y = y
            self.duration = duration
            self.button = button

            # One of several predefined types. Depending on the type, a string for type X will be passed to
            # execute macro so that when the macro comes across it, it will type the given string
            # currently, this type can be "username" or "password" to represent username and password respectively
            self.keyboard_macro_type = keyboard_macro_type
        def __str__(self):
            return f"keyboard type: {self.keyboard_macro_type}"


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
            self.macro.append(self.MacroEvent(x, y, duration, button, None))
            self.macro_start_time = time.perf_counter()


    def record_macro(self):
        input(f"Record the macro. Only records mouse clicks for now. Press ENTER to start:")
        mouse_listener = mouse.Listener(on_click=self.on_click)
        mouse_listener.start()
        self.macro = []
        self.macro_start_time = time.perf_counter()
        input("Press ENTER when you are done recording:")
        mouse_listener.stop()

    
    def record_signin_macro(self):
        input(f"Record the signin macro. Start by closing the currently open browser, then opening the browser on the desktop. Perform all the steps necessary to bring up the Firefox web browser and click inside the URL bar. Then click back here after you're done. Press ENTER to start: ")
        mouse_listener = mouse.Listener(on_click=self.on_click)
        mouse_listener.start()
        self.macro = []
        self.macro_start_time = time.perf_counter()
        input(f"Press ENTER in this window once you finished clicking inside the URL box: ")
        mouse_listener.stop()

        # delete the event to click back in the cmd window
        del self.macro[-1]

        # insert the URL entry event into the macro events. At this point, the last event was clicking inside the URL bar.
        self.macro.append(self.MacroEvent(None, None, .5, None, "site"))

        input(f"At this time, put the site URL into the URL bar. Then perform all the steps necessary to bring up the log in prompt for the website, starting with clicking the go button to go to the website. After that, click in the username box, then click in the password box, then click back into this window. Press ENTER to start: ")
        mouse_listener = mouse.Listener(on_click=self.on_click)
        mouse_listener.start()
        self.macro_start_time = time.perf_counter()
        input(f"Press ENTER in this window once you finished clicking inside the username box, and then the password box: ")
        mouse_listener.stop()
        
        # delete the last event in the macro as that was used to get back to the CMD window.
        del self.macro[-1]

        # now we need to insert the username/password into the macro events. at this point, the last two events were clicks in the username box and password box
        self.macro.insert(-1, self.MacroEvent(None, None, .5, None, "username"))

        self.macro.append(self.MacroEvent(None, None, .5, None, "password"))

        input(f"At this time, put the correct username and password into the log in prompt for the website so you're ready to sign in. Press ENTER to start recording the rest of the macro, starting with clicking the log in button and ending with the betting interface pulled up: ")
        mouse_listener = mouse.Listener(on_click=self.on_click)
        mouse_listener.start()
        self.macro_start_time = time.perf_counter()
        input(f"Press ENTER when you are done recording: ")
        mouse_listener.stop()


    def execute_macro(self, delay=None, site=None, username=None, password=None):
        if site:
            with open(URL_TRANSLATION_FILE, "r") as f:
                urls = f.read().split("\n")
            for url in urls:
                if site in url:
                    site = url
                    break

        for event in self.macro:
            if delay:
                time.sleep(delay)
            else:
                time.sleep(event.duration)
            try:
                if event.keyboard_macro_type == "username":
                    self.k.type(username)
                elif event.keyboard_macro_type == "password":
                    self.k.type(password)
                elif event.keyboard_macro_type == "site":
                    self.k.type(site)
                else:
                    self.m.position = event.x, event.y
                    # use autoit.mouse_down("left") and autoit.mouse_up("left") along with sleep to do longer presses
                    if event.button == mouse.Button.left:
                        autoit.mouse_click("left", event.x, event.y, 1) 
                    elif event.button == mouse.Button.right:
                        autoit.mouse_click("right", event.x, event.y, 1) 
            except AttributeError:
                self.m.position = event.x, event.y
                # use autoit.mouse_down("left") and autoit.mouse_up("left") along with sleep to do longer presses
                if event.button == mouse.Button.left:
                    autoit.mouse_click("left", event.x, event.y, 1) 
                elif event.button == mouse.Button.right:
                    autoit.mouse_click("right", event.x, event.y, 1) 

