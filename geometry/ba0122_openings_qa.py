import json
from pathlib import Path

OPENINGS_PATH = Path("geometry/master/BA0122.openings.v1.json")

def main():
    data=json.loads(OPENINGS_PATH.read_text(encoding="utf-8"))
    print("--- BA0122 OPENINGS QA ---")
    for o in data["openings"]:
        print(f"{o['id']}: {o['type']} / {o['subtype']} / width={o['width_m']:.3f} m / {o['qa']}")
    print("Summary:", data["summary"]["qa"])

if __name__=="__main__":
    main()
