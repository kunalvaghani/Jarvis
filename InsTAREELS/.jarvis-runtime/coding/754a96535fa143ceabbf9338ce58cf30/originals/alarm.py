import time
import winsound  # For Windows sound alerts
import tkinter as tk
from tkinter import messagebox

def alarm(duration=5):
    """
    Play an alarm sound for a specified duration.
    
    Args:
        duration (int): Duration in seconds to play the alarm.
    """
    print("Alarm triggered!")
    frequency = 1500  # Set frequency (Hz)
    for _ in range(duration):
        winsound.Beep(frequency, 1000)  # Beep for 1 second
        time.sleep(1)


def show_alarm_ui():
    """
    Display a simple UI for the alarm.
    """
    root = tk.Tk()
    root.title("Alarm")
    root.geometry("300x200")
    
    label = tk.Label(root, text="Alarm is ringing!", font=("Arial", 16))
    label.pack(pady=20)
    
    def close_window():
        root.destroy()
    
    button = tk.Button(root, text="Dismiss Alarm", command=close_window)
    button.pack(pady=20)
    
    root.mainloop()

if __name__ == "__main__":
    # Show UI
    show_alarm_ui()
    # Play alarm sound
    alarm(5)
