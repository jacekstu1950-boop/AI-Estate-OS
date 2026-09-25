import json
from pathlib import Path

MASTER = Path("geometry/master/BA0122.room-polygons.v1.json")

def polygon_area(points):
    return abs(sum(
        points[i][0] * points[(i + 1) % len(points)][1]
        - points[(i + 1) % len(points)][0] * points[i][1]
        for i in range(len(points))
    )) / 2

def main():
    data = json.loads(MASTER.read_text(encoding="utf-8"))
    scale = data["meters_per_svg_unit"]
    print("--- BA0122 ROOM POLYGON QA ---")
    max_err = 0.0
    for room in data["rooms"]:
        vector_area = polygon_area(room["polygon_svg"])
        calc = vector_area * scale * scale
        err_pct = (calc - room["source_area_m2"]) / room["source_area_m2"] * 100
        max_err = max(max_err, abs(err_pct))
        status = "PASS" if abs(err_pct) <= 0.5 else "REVIEW"
        print(f"{room['name']}: source={room['source_area_m2']:.2f} m2 calc={calc:.3f} m2 error={err_pct:+.3f}% {status}")
    print(f"Max |error|: {max_err:.3f}%")
    print("Overall:", "PASS" if max_err <= 0.5 else "REVIEW")

if __name__ == "__main__":
    main()
