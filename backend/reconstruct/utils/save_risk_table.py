import os
import csv
from datetime import datetime


def save_risk_table(data, output_dir="data"):
    # Purpose: Save a risk table payload to a CSV file.
    # Inputs:
    # - data (dict): Payload containing a "risk_table" list of rows.
    # - output_dir (str): Directory to write the CSV file.
    # Outputs:
    # - dict: Message and path to the saved risk table CSV.
    """
    Save risk table as risk_*.csv with columns: time, n_risk.
    Skips blank rows.
    """

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    risk_table = data.get("risk_table", [])
    risk_csv = os.path.join(output_dir, f"risk_{timestamp}.csv")

    with open(risk_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["time", "n_risk"])
        writer.writeheader()

        for r in risk_table:
            time_str = r.get("time", "")
            n_str = r.get("n_risk", "")

            # skip rows with empty time or n_risk
            if time_str == "" or n_str == "":
                continue

            writer.writerow({
                "time": float(time_str),
                "n_risk": int(n_str),
            })

    return {
        "message": f"Saved {len(risk_table)} risk table rows.",
        "risk_csv": risk_csv,
    }
