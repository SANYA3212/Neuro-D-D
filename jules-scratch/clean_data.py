import json
import shutil
from pathlib import Path

def clean_test_data():
    """
    Cleans up test data by removing test users and rooms.
    """
    print("--- Starting Data Cleanup ---")

    data_dir = Path("data")
    if not data_dir.exists():
        print("Data directory not found. Nothing to clean.")
        return

    # Clean user data
    users_dir = data_dir / "users"
    index_file = data_dir / "index.json"

    if index_file.exists():
        print(f"Cleaning user index: {index_file}")
        with open(index_file, 'r+') as f:
            try:
                index_data = json.load(f)
                users_to_delete = []

                if 'users' in index_data:
                    for email, user_info in index_data['users'].items():
                        if "@example.com" in email:
                            users_to_delete.append((email, user_info['user_code']))

                    for email, user_code in users_to_delete:
                        print(f"Removing test user: {email} ({user_code})")
                        del index_data['users'][email]
                        user_dir = users_dir / f"user_{user_code}"
                        if user_dir.exists():
                            print(f"Deleting directory: {user_dir}")
                            shutil.rmtree(user_dir)

                # Reset the file pointer and write the cleaned data
                f.seek(0)
                json.dump(index_data, f, indent=2)
                f.truncate()
                print("User index cleaned.")

            except (json.JSONDecodeError, KeyError) as e:
                print(f"Could not process index.json: {e}. Resetting file.")
                f.seek(0)
                json.dump({"users": {}, "campaigns": {}}, f, indent=2)
                f.truncate()

    # Clean rooms data
    rooms_file = data_dir / "rooms.json"
    if rooms_file.exists():
        print(f"Clearing rooms file: {rooms_file}")
        with open(rooms_file, 'w') as f:
            json.dump([], f) # Write an empty list
        print("Rooms file cleared.")

    print("--- Data Cleanup Complete ---")

if __name__ == "__main__":
    clean_test_data()
