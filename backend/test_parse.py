import drama_store
from pathlib import Path

def test_parse():
    print("Testing PDF Parsing...")
    programmes = drama_store.list_programmes()
    if not programmes:
        print("No programmes found in directory.")
        return
    
    first = programmes[0]['name']
    print(f"Parsing: {first}")
    try:
        entries = drama_store.parse_programme(first)
        if entries:
            print(f"Found {len(entries)} entries.")
            e = entries[0]
            print(f"Sample Entry: {e.get('Name and Surname')} - Venue: {e.get('Venue')} - Date: {e.get('Date')}")
        else:
            print("No entries parsed.")
    except Exception as exc:
        print(f"Error: {exc}")

if __name__ == "__main__":
    test_parse()
