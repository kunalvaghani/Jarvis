# Jarvis draft: simple_pseudocode_game.py. Waiting for generated code.
# Simple Pseudocode Game
# This script implements a basic text-based game using pseudocode logic

def main():
    print("Welcome to the Simple Pseudocode Game!")
    print("You are in a mysterious forest. You can go north, south, east, or west.")
    
    # Initialize player position
    x = 0
    y = 0
    
    # Game loop
    while True:
        print(f"\nYou are at position ({x}, {y})")
        print("Where do you want to go?")
        print("1. North (↑)")
        print("2. South (↓)")
        print("3. East (→)")
        print("4. West (←)")
        print("5. Quit game")
        
        choice = input("Enter your choice (1-5): ")
        
        if choice == "1":
            y += 1
            print("You moved north.")
        elif choice == "2":
            y -= 1
            print("You moved south.")
        elif choice == "3":
            x += 1
            print("You moved east.")
        elif choice == "4":
            x -= 1
            print("You moved west.")
        elif choice == "5":
            print("Thanks for playing!")
            break
        else:
            print("Invalid choice. Please enter a number between 1 and 5.")
        
        # Check if player reached a special location
        if x == 2 and y == 2:
            print("Congratulations! You found the treasure!")
        elif x == -2 and y == -2:
            print("Oh no! You fell into a trap!")
        
        # Boundary check
        if abs(x) > 5 or abs(y) > 5:
            print("You wandered too far and got lost in the forest.")
            print("Game Over!")
            break

if __name__ == "__main__":
    main()
