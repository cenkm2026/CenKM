import os
import json
import csv
from datetime import datetime
import pandas as pd


def save_points(data, output_dir="data"):
    # Purpose: Save digitized curve data, censor data, and calibration info to files.
    # Inputs:
    # - data (dict): Payload with curve_points, censor_points, and calibration info.
    # - output_dir (str): Directory to write output files.
    # Outputs:
    # - dict: Paths to saved JSON/CSV/XLSX files and a summary message.
    """
    Save:
      1. raw JSON file
      2. curve_*.csv (time, survival)
      3. censor_*.csv (time, survival)
      4. digitized_*.xlsx with:
         - sheet1: curve_points
         - sheet2: censor_points
         - sheet3: calibration pixel coordinates
    """

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    calibration = data.get("calibration", {})
    calib_pixels = calibration.get("calibPixels", {})
    calib_values = calibration.get("calibValues", {})

    curve_points = data.get("curve_points", [])
    censor_points = data.get("censor_points", [])

    # ------------------------------------------------------------
    # 1. Save raw JSON
    # ------------------------------------------------------------
    json_path = os.path.join(output_dir, f"points_{timestamp}.json")
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)

    # ------------------------------------------------------------
    # 2. Save curve CSV
    # ------------------------------------------------------------
    curve_csv = os.path.join(output_dir, f"curve_{timestamp}.csv")
    with open(curve_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["time", "survival"])
        writer.writeheader()

        for p in sorted(curve_points, key=lambda x: (x.get("x") or 0)):
            if p.get("x") is None or p.get("y") is None:
                continue
            writer.writerow({
                "time": round(p["x"], 6),
                "survival": round(p["y"], 6),
            })

    # ------------------------------------------------------------
    # 3. Save censor CSV
    # ------------------------------------------------------------
    censor_csv = os.path.join(output_dir, f"censor_{timestamp}.csv")
    with open(censor_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["time", "survival"])
        writer.writeheader()

        for p in sorted(censor_points, key=lambda x: (x.get("x") or 0)):
            if p.get("x") is None:
                continue
            # survival may be None for censor → store empty cell
            writer.writerow({
                "time": round(p["x"], 6),
                "survival": round(p["y"], 6) if p.get("y") is not None else "",
            })

    # ------------------------------------------------------------
    # 4. Save Excel with 3 sheets
    # ------------------------------------------------------------
    excel_path = os.path.join(output_dir, f"digitized_{timestamp}.xlsx")

    df_curve = pd.DataFrame(curve_points)
    df_censor = pd.DataFrame(censor_points)

    df_calib = pd.DataFrame([{
        "x_start_px": calib_pixels.get("x_start_px"),
        "x_end_px": calib_pixels.get("x_end_px"),
        "y_start_px": calib_pixels.get("y_start_px"),
        "y_end_px": calib_pixels.get("y_end_px"),
        "x_start_value": calib_values.get("x_start"),
        "x_end_value": calib_values.get("x_end"),
        "y_start_value": calib_values.get("y_start"),
        "y_end_value": calib_values.get("y_end"),
    }])

    with pd.ExcelWriter(excel_path) as writer:
        df_curve.to_excel(writer, sheet_name="curve_points", index=False)
        df_censor.to_excel(writer, sheet_name="censor_points", index=False)
        df_calib.to_excel(writer, sheet_name="calibration_pixels", index=False)

    # ------------------------------------------------------------
    # Return paths
    # ------------------------------------------------------------
    return {
        "message": (
            f"Saved {len(curve_points)} curve pts and "
            f"{len(censor_points)} censor pts."
        ),
        "json_file": json_path,
        "curve_csv": curve_csv,
        "censor_csv": censor_csv,
        "excel_file": excel_path,
    }
