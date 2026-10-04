
import os
import sys

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python list_dir_contents.py <directory_path>")
        sys.exit(1)

    directory_path = sys.argv[1]

    try:
        print(f"Contents of {directory_path}:")
        for item in os.listdir(directory_path):
            full_path = os.path.join(directory_path, item)
            if os.path.isdir(full_path):
                print(f"  [DIR] {item}")
            else:
                print(f"  [FILE] {item}")
    except FileNotFoundError:
        print(f"Error: Directory not found at {directory_path}")
    except Exception as e:
        print(f"An error occurred: {e}")
