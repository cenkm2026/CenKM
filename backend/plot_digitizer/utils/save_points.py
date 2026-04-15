# backend/utils/save_points.py
import json
import os
from datetime import datetime

def save_points(data, output_dir="data"):
    # Purpose: Save digitized points to a timestamped JSON file.
    # Inputs:
    # - data (dict): Payload with a "points" list of {x, y} dicts.
    # - output_dir (str): Directory to save the JSON file.
    # Outputs:
    # - dict: Message indicating saved file path and point count.
    """
    Save digitized points data to a timestamped JSON file.

    Parameters
    ----------
    data : dict
        Dictionary with a key 'points' containing list of {x, y} dicts.
    output_dir : str
        Directory to save the output file.
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(output_dir, f"points_{timestamp}.json")

    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)

    return {"message": f"Saved {len(data['points'])} points to {file_path}"}
