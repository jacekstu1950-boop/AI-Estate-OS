import json
import math
from pathlib import Path

MASTER_PATH = Path("geometry/master/BA0122.master.json")

ROOM = {
    "id": "living_kitchen",
    "name": "Pokój dzienny z aneksem kuchennym",
    "area_m2": 23.04,
    "x0": 162.589,
    "y0": 150.500,
    "x1": 405.900,
    "y1": 429.306,
}

def calibrate():
    width_svg = ROOM["x1"] - ROOM["x0"]
    depth_svg = ROOM["y1"] - ROOM["y0"]
    area_svg2 = width_svg * depth_svg
    meters_per_svg = math.sqrt(ROOM["area_m2"] / area_svg2)
    return {
        "width_svg": width_svg,
        "depth_svg": depth_svg,
        "area_svg2": area_svg2,
        "meters_per_svg_unit": meters_per_svg,
        "centimeters_per_svg_unit": meters_per_svg * 100,
        "svg_units_per_meter": 1 / meters_per_svg,
        "width_m": width_svg * meters_per_svg,
        "depth_m": depth_svg * meters_per_svg,
        "area_check_m2": width_svg * depth_svg * meters_per_svg**2,
    }

def main():
    result = calibrate()
    print("--- BA0122 SVG METRIC CALIBRATION ---")
    print(f"Basis room: {ROOM['name']} = {ROOM['area_m2']:.2f} m2")
    print(f"Vector bounds: {result['width_svg']:.3f} × {result['depth_svg']:.3f} SVG units")
    print(f"Scale: 1 SVG unit = {result['centimeters_per_svg_unit']:.9f} cm")
    print(f"Scale: 1 m = {result['svg_units_per_meter']:.9f} SVG units")
    print(f"Room dimensions: {result['width_m']:.4f} × {result['depth_m']:.4f} m")
    print(f"Area check: {result['area_check_m2']:.4f} m2")

if __name__ == "__main__":
    main()
