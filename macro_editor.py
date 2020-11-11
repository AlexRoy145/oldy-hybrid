import argparse
import pickle
from macro import Macro

def main():
    parser = argparse.ArgumentParser(description="Edit a macro file.")
    parser.add_argument("macro_file", type=str, help="The macro file that ends in .dat that you want to edit delay for")
    args = parser.parse_args()

    macro = Macro(REFRESH_MACRO_DIR)
        if not self.refresh_macro.load_profile(self.refresh_macro_name):
            self.refresh_macro.set_screen_condition()
            self.refresh_macro.save_profile(self.refresh_macro_name)

