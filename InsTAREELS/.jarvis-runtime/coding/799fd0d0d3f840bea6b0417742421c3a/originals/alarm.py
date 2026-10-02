import time
import winsound  # For Windows sound alerts

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

if __name__ == "__main__":
    alarm(5)
