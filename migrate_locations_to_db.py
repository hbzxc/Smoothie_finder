"""Migrate legacy location text files into flask_app/smoothie_locations.db."""

from flask_app.db import migrate_from_text_files

if __name__ == "__main__":
    summary = migrate_from_text_files("flask_app")
    total = sum(summary.values())
    print("Migrated locations into flask_app/smoothie_locations.db")
    for franchise, count in summary.items():
        print(f"  {franchise}: {count}")
    print(f"Total: {total}")
