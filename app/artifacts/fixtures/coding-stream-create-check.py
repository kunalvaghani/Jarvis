import time
import winsound

def alarm(duration=5):
    """
    Play an alarm sound for a specified duration.
    
    Args:
        duration (int): Duration in seconds to play the alarm. Default is 5 seconds.
    """
    # Frequency of the alarm sound (Hz)
    frequency = 1000
    
    # Play the alarm sound
    for _ in range(duration):
        winsound.Beep(frequency, 1000)  # Beep for 1 second
        time.sleep(1)

if __name__ == "__main__":
    print("Starting alarm...")
    alarm()
    print("Alarm finished.")