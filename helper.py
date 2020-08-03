import sys
import pynput
import pytesseract

# index is raw prediction, value is (x,y) pixel coordinates of the clickbot numbers
coords = []

def on_click(x, y, button, pressed):
    global coords
    if pressed:
        coords.append((x, y))
        length = len(coords)
        print(f"Clicked {length-1}, now click {length}.")
        #debug
        print(f"{length-1} is at {x},{y}")

def main():
    global coords
    print("Click the clickbot's buttons in order from 0-36 to set the coordinates. Start at 0, end at 36.")
    listener = mouse.Listener(on_click=on_click)
    listener.start()

    # wait until all coords is populated
    while len(coords) != 36:
        pass

    print("FINISHED")
    print(coords)

main()
