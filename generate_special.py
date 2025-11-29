# generate_special.py
import pickle
from random import randint

# This script generates the data for the 'special' boxes and saves it to a .pkl file.
# It will be run once when the Docker image is built.

FILENAME = 'special.pkl'

if __name__ == "__main__":
    # Create a dictionary of 2000 random special boxes
    special_data = {randint(0, 999999): randint(0, 3) for _ in range(2000)}
    with open(FILENAME, 'wb') as file:
        pickle.dump(special_data, file)
    print(f"Successfully generated and saved data to {FILENAME}")