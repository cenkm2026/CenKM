"""
reconstruct_v1.py

Now supports:
 - curve_*.csv
 - censor_*.csv (optional)
 - risk_*.csv (optional)
 - sample size n (optional if risk table available)

This corresponds to:
    get_ipd(n, t_drop, S_drop, cens_t, ...)
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime
from reconstruct.CEN_KM import get_ipd
from reconstruct.utils.cleaning import clean_curve


# ------------------------------------------------------------
# Save helper for CSV upload case
# ------------------------------------------------------------
def reconstruct_v1_from_arrays(n, t, S, cens_t=None):
    # Purpose: Reconstruct IPD from array inputs and save to CSV.
    # Inputs:
    # - n (int): Total sample size.
    # - t (array-like): Time values.
    # - S (array-like): Survival values.
    # - cens_t (array-like | None): Censor times, if available.
    # Outputs:
    # - str: Path to the saved IPD CSV file.
    ipd = get_ipd(
        n=n,
        t=np.array(t),
        S=np.array(S),
        cens_t=None if cens_t is None else np.array(cens_t),
        match_tol=1e-6,
        max_extra_censors_per_bin=20,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = f"data/IPD_from_csv_{timestamp}.csv"
    ipd.to_csv(out_file, index=False)
    return out_file


# ------------------------------------------------------------
# Helper: find latest file by prefix
# ------------------------------------------------------------
def find_latest_file(prefix, folder="data"):
    # Purpose: Find the latest file in a folder by prefix (lexicographic order).
    # Inputs:
    # - prefix (str): Filename prefix to match.
    # - folder (str): Folder to search.
    # Outputs:
    # - str | None: Path to the latest matching file, or None if not found.
    files = [f for f in os.listdir(folder) if f.startswith(prefix)]
    if not files:
        return None
    return os.path.join(folder, sorted(files)[-1])


# ------------------------------------------------------------
# Main reconstruction function
# ------------------------------------------------------------
def reconstruct_v1(output_dir="data", n=None):
    # Purpose: Reconstruct IPD from latest curve/censor/risk CSV files.
    # Inputs:
    # - output_dir (str): Directory to save output IPD CSV.
    # - n (int | None): Total sample size, inferred from risk table if None.
    # Outputs:
    # - str: Path to the saved IPD CSV file.
    """
    Extended reconstruction workflow:
      - loads latest curve_*.csv
      - loads latest censor_*.csv (optional)
      - loads latest risk_*.csv (optional)
      - if n not supplied → auto-detect from risk table
      - cleans digitized curve
      - calls get_ipd()
      - saves IPD_*.csv
    """

    # -----------------------------
    # Load curve CSV
    # -----------------------------
    curve_csv = find_latest_file("curve_")
    if not curve_csv:
        raise ValueError("No curve CSV found (curve_*.csv).")

    print(f"Using curve file: {curve_csv}")
    curve_df = pd.read_csv(curve_csv)
    t_raw = curve_df["time"].to_numpy()
    S_raw = curve_df["survival"].to_numpy()

    # Clean → drop duplicates / enforce monotonicity
    t_drop, S_drop = clean_curve(t_raw, S_raw)

    # -----------------------------
    # Load censor CSV (optional)
    # -----------------------------
    censor_csv = find_latest_file("censor_")
    if censor_csv and os.path.exists(censor_csv):
        print(f"Using censor file: {censor_csv}")
        censor_df = pd.read_csv(censor_csv)
        cens_t = censor_df["time"].to_numpy()
    else:
        cens_t = None
        print("⚠ No censor CSV detected.")

    # -----------------------------
    # Load risk table CSV (optional)
    # -----------------------------
    risk_csv = find_latest_file("risk_")
    risk_n = None

    if risk_csv and os.path.exists(risk_csv):
        print(f"Using risk table file: {risk_csv}")
        risk_df = pd.read_csv(risk_csv)

        # Must contain: time, n_risk
        if "n_risk" in risk_df.columns:
            # The first value in a KM risk table is typically N
            risk_n = int(risk_df["n_risk"].iloc[0])
            print(f"Detected N from risk table: {risk_n}")
        else:
            print("⚠ Risk table found, but missing column n_risk")

    # -----------------------------
    # Determine final N
    # -----------------------------
    if n is None:
        if risk_n is not None:
            print(f"Using N={risk_n} (from risk table)")
            n_final = risk_n
        else:
            raise ValueError(
                "Sample size N is required because no usable risk table was supplied."
            )
    else:
        n_final = n
        print(f"Using N={n_final} (user supplied)")

    # -----------------------------
    # Call get_ipd()
    # -----------------------------
    ipd_df = get_ipd(
        n=n_final,
        t=t_drop,
        S=S_drop,
        cens_t=cens_t,
        match_tol=1e-6,
        max_extra_censors_per_bin=20,
        random_state=123,
    )

    # -----------------------------
    # Save results
    # -----------------------------
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = os.path.join(output_dir, f"IPD_v1_{timestamp}.csv")
    ipd_df.to_csv(out_csv, index=False)

    print(f"IPD saved to: {out_csv}")
    return out_csv
