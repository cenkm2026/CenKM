import os
import numpy as np
import pandas as pd
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
from lifelines import KaplanMeierFitter

from reconstruct.CEN_KM import get_ipd
from reconstruct.utils.cleaning import clean_curve
import ast

# =========================================================
#  RISK TABLE HELPERS (added)
# =========================================================
def parse_risk_table(risk_table):
    # Purpose: Parse risk table JSON into a validated dataframe.
    # Inputs:
    # - risk_table (list[dict] | None): List of {time, risk} dicts from frontend.
    # Outputs:
    # - pd.DataFrame | None: Parsed risk table or None if input is None.
    """
    risk_table comes from JSON passed by the frontend:
    [
      { "time": 0, "risk": 135 },
      { "time": 12, "risk": 112 }
    ]
    """
    if risk_table is None:
        return None
    df = pd.DataFrame(risk_table)
    if not {"time", "risk"}.issubset(df.columns):
        raise ValueError("Risk table must contain 'time' and 'risk' columns.")
    return df


def infer_n_from_risk(risk_df):
    # Purpose: Infer total sample size from the first risk table row.
    # Inputs:
    # - risk_df (pd.DataFrame | None): Risk table dataframe.
    # Outputs:
    # - int | None: Inferred total N or None if risk_df is None.
    if risk_df is None:
        return None
    # Typical: first risk number = total N
    return int(risk_df["risk"].iloc[0])


# -----------------------------------------------------------
# Normalize IPD columns from CEN_KM.get_ipd()
# -----------------------------------------------------------
def normalize_ipd_columns(ipd_df):
    # Purpose: Standardize IPD column names to "time" and "status".
    # Inputs:
    # - ipd_df (pd.DataFrame): IPD dataframe with varying column names.
    # Outputs:
    # - pd.DataFrame: Dataframe with standardized time/status columns.
    cols = {c.lower(): c for c in ipd_df.columns}

    # time column candidates
    time_candidates = ["time", "t", "times"]
    time_col = next((cols[c] for c in time_candidates if c in cols), None)
    if time_col is None:
        raise ValueError(f"No time column found. Available: {list(ipd_df.columns)}")

    # status/event column candidates
    status_candidates = ["status", "event", "d", "events", "event_observed"]
    status_col = next((cols[c] for c in status_candidates if c in cols), None)
    if status_col is None:
        raise ValueError(f"No status/event column found. Available: {list(ipd_df.columns)}")

    ipd_df = ipd_df.rename(columns={
        time_col: "time",
        status_col: "status"
    })

    return ipd_df[["time", "status"]]


# -----------------------------------------------------------
# No-overlay reconstruction (UPDATED WITH RISK TABLE)
# -----------------------------------------------------------
def reconstruct_no_overlay(n, curve_df, censor_df=None, output_dir="data", risk_table=None):
    # Purpose: Reconstruct IPD and KM plot without overlaying on the image.
    # Inputs:
    # - n (int | None): Total sample size, inferred from risk_table if None.
    # - curve_df (pd.DataFrame): Digitized curve points with time/survival.
    # - censor_df (pd.DataFrame | None): Censoring points dataframe.
    # - output_dir (str): Directory to save outputs.
    # - risk_table (list[dict] | None): Optional risk table data.
    # Outputs:
    # - tuple[str, str]: Paths to saved IPD CSV and KM PNG.

    os.makedirs(output_dir, exist_ok=True)

    # ----- NEW: risk table -----
    risk_df = parse_risk_table(risk_table)

    # Auto infer N if missing
    if n is None and risk_df is not None:
        n = infer_n_from_risk(risk_df)

    if n is None:
        raise ValueError("Total N must be provided OR risk table must contain first-row N.")


    # clean digitized curve
    t_raw = curve_df["time"].values
    S_raw = curve_df["survival"].values
    t_clean, S_clean = clean_curve(t_raw, S_raw)

    try:
        if censor_df.empty:
            raise ValueError("censor_points is Empty!")
        print(censor_df)
    except ValueError as e:
        raise e

    cens_t = censor_df["time"].values if censor_df is not None else None

    # get IPD
    ipd_df = get_ipd(
        n=int(n),
        t=t_clean,
        S=S_clean,
        cens_t=cens_t,
        match_tol=1e-6,
        max_extra_censors_per_bin=20
    )

    # standardize columns
    ipd_df = normalize_ipd_columns(ipd_df)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ipd_path = os.path.join(output_dir, f"IPD_no_overlay_{ts}.csv")
    ipd_df.to_csv(ipd_path, index=False)

    # KM plot
    kmf = KaplanMeierFitter()
    kmf.fit(ipd_df["time"], event_observed=ipd_df["status"])

    fig, ax = plt.subplots(figsize=(7, 5))
    kmf.plot(ax=ax, ci_show=False, color="red", show_censors=True)

    ax.set_title("Reconstructed KM Curve")
    ax.set_xlabel("Time")
    ax.set_ylabel("Survival Probability")
    ax.set_ylim(0, 1.05)

    km_path = os.path.join(output_dir, f"KM_no_overlay_{ts}.png")
    plt.savefig(km_path, dpi=300, bbox_inches="tight")
    plt.close()

    return f"/data/IPD_no_overlay_{ts}.csv", f"/data/KM_no_overlay_{ts}.png"


# -----------------------------------------------------------
# Pixel → Data mapping
# -----------------------------------------------------------
def data_to_pixel(
    t, S,
    x_start_px, x_end_px,
    y_start_px, y_end_px,
    x_min, x_max,
    y_min, y_max
):
    # Purpose: Map data coordinates to pixel coordinates on the image.
    # Inputs:
    # - t (float | np.ndarray): Time value(s).
    # - S (float | np.ndarray): Survival value(s).
    # - x_start_px (float): Pixel x for data x_min.
    # - x_end_px (float): Pixel x for data x_max.
    # - y_start_px (float): Pixel y for data y_max (top).
    # - y_end_px (float): Pixel y for data y_min (bottom).
    # - x_min (float): Data x-axis minimum.
    # - x_max (float): Data x-axis maximum.
    # - y_min (float): Data y-axis minimum.
    # - y_max (float): Data y-axis maximum.
    # Outputs:
    # - tuple[np.ndarray, np.ndarray]: Pixel coordinates (x, y).
    """
    Correct mapping:
    - X: left → right
    - Y: top → bottom (PIL)
    """

    px = x_start_px + (t - x_min) / (x_max - x_min) * (x_end_px - x_start_px)

    # NOTE: PIL: y=0 is top, so invert
    py = y_start_px - (S - y_min) / (y_max - y_min) * (y_start_px - y_end_px)

    return px, py


# -----------------------------------------------------------
# Overlay KM on plot image
# -----------------------------------------------------------
def overlay_km_on_image(
    bg_path,
    t_km, S_km,
    x_start_px, x_end_px,
    y_start_px, y_end_px,
    x_min, x_max,
    y_min, y_max,
    censor_times=None,
    output_dir="data"
):
    # Purpose: Overlay a step KM curve (and censor marks) on a background image.
    # Inputs:
    # - bg_path (str): Path to the background plot image.
    # - t_km (np.ndarray): KM time points.
    # - S_km (np.ndarray): KM survival values.
    # - x_start_px (float): Pixel x for data x_min.
    # - x_end_px (float): Pixel x for data x_max.
    # - y_start_px (float): Pixel y for data y_max (top).
    # - y_end_px (float): Pixel y for data y_min (bottom).
    # - x_min (float): Data x-axis minimum.
    # - x_max (float): Data x-axis maximum.
    # - y_min (float): Data y-axis minimum.
    # - y_max (float): Data y-axis maximum.
    # - censor_times (np.ndarray | None): Censor times for marks.
    # - output_dir (str): Directory to save the overlay image.
    # Outputs:
    # - str: Path to the saved overlay PNG.

    os.makedirs(output_dir, exist_ok=True)

    # Load background
    bg = Image.open(bg_path)
    w, h = bg.size

    # Convert KM curve to pixel coords
    px, py = data_to_pixel(
        t_km, S_km,
        x_start_px, x_end_px,
        y_start_px, y_end_px,
        x_min, x_max,
        y_min, y_max
    )

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.imshow(bg)

    # --------------------------------------------------
    # 1) DRAW STEP KM CURVE  (instead of straight line)
    # --------------------------------------------------
    ax.plot(
        px, py,
        drawstyle="steps-post",   # <---- KEY FIX
        color="red",
        linewidth=2,
        zorder=10
    )

    # --------------------------------------------------
    # 2) CENSOR MARKS EXACTLY ON STEP CURVE
    # --------------------------------------------------
    if censor_times is not None and len(censor_times) > 0:

        # Find survival level at censor times (STEP FUNCTION VALUE)
        censor_times = np.asarray(censor_times)
        idx = np.searchsorted(t_km, censor_times, side="right") - 1
        idx = np.clip(idx, 0, len(S_km) - 1)
        S_cens = S_km[idx]     # <--- correct step height

        # Convert censor positions to pixels
        cens_px, cens_py = data_to_pixel(
            censor_times,
            S_cens,               # <---- use step value, not interpolation
            x_start_px, x_end_px,
            y_start_px, y_end_px,
            x_min, x_max,
            y_min, y_max
        )

        ax.scatter(
            cens_px,
            cens_py,
            marker="|",
            color="black",
            s=60,
            zorder=12
        )

    # --------------------------------------------------
    # 3) Remove axes and keep full-size canvas
    # --------------------------------------------------
    ax.set_axis_off()
    ax.set_xlim(0, w)
    ax.set_ylim(h, 0)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_png = os.path.join(output_dir, f"KM_overlay_{ts}.png")

    plt.savefig(out_png, dpi=300, bbox_inches="tight", pad_inches=0)
    plt.close()

    return out_png


# -----------------------------------------------------------
# Load pixel coordinates (unchanged)
# -----------------------------------------------------------
def load_x(val):
    # Purpose: Parse an x-coordinate from various input formats.
    # Inputs:
    # - val (int | float | dict | str): Value containing an x coordinate.
    # Outputs:
    # - float: Parsed x coordinate.
    if isinstance(val, (int, float)): return float(val)
    if isinstance(val, dict): return float(val["x"])
    if isinstance(val, str):
        obj = ast.literal_eval(val)
        return float(obj["x"])
    raise ValueError(f"Cannot parse x from: {val}")


def load_y(val):
    # Purpose: Parse a y-coordinate from various input formats.
    # Inputs:
    # - val (int | float | dict | str): Value containing a y coordinate.
    # Outputs:
    # - float: Parsed y coordinate.
    if isinstance(val, (int, float)): return float(val)
    if isinstance(val, dict): return float(val["y"])
    if isinstance(val, str):
        obj = ast.literal_eval(val)
        return float(obj["y"])
    raise ValueError(f"Cannot parse y from: {val}")


# -----------------------------------------------------------
# FULL OVERLAY RECONSTRUCTION (UPDATED)
# -----------------------------------------------------------
def reconstruct_with_overlay(
    curve_df,
    censor_df,
    calib_df,
    plot_path,
    n,
    output_dir="data",
    risk_table=None   # <--- NEW
):
    # Purpose: Reconstruct IPD and overlay KM curve onto the original plot image.
    # Inputs:
    # - curve_df (pd.DataFrame): Digitized curve points with time/survival.
    # - censor_df (pd.DataFrame): Censoring points dataframe.
    # - calib_df (pd.DataFrame): Calibration pixels and axis values.
    # - plot_path (str): Path to the original plot image.
    # - n (int | None): Total sample size, inferred if None.
    # - output_dir (str): Directory to save outputs.
    # - risk_table (list[dict] | None): Optional risk table data.
    # Outputs:
    # - tuple[str, str]: Paths to saved IPD CSV and overlay PNG.

    os.makedirs(output_dir, exist_ok=True)

    # ---- risk table support ----
    risk_df = parse_risk_table(risk_table)
    if n is None and risk_df is not None:
        n = infer_n_from_risk(risk_df)

    if n is None:
        raise ValueError("Total N must be provided OR included in risk table.")

    # ---- calibration ----
    row = calib_df.iloc[0]

    x_start_px = load_x(row["x_start_px"])
    x_end_px   = load_x(row["x_end_px"])
    y_start_px = load_y(row["y_start_px"])
    y_end_px   = load_y(row["y_end_px"])

    x_min = float(row["x_start_value"])
    x_max = float(row["x_end_value"])
    y_min = float(row["y_start_value"])
    y_max = float(row["y_end_value"])

    # clean curve
    t_raw = curve_df["time"].values
    S_raw = curve_df["survival"].values
    t_clean, S_clean = clean_curve(t_raw, S_raw)

    cens_t = censor_df["time"].values if censor_df is not None else None

    # rebuild IPD
    ipd_df = get_ipd(
        n=int(n),
        t=t_clean,
        S=S_clean,
        cens_t=cens_t,
        match_tol=1e-6,
        max_extra_censors_per_bin=20
    )
    ipd_df = normalize_ipd_columns(ipd_df)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ipd_path = os.path.join(output_dir, f"IPD_overlay_{ts}.csv")
    ipd_df.to_csv(ipd_path, index=False)

    # KM reconstruction
    kmf = KaplanMeierFitter()
    kmf.fit(ipd_df["time"], event_observed=ipd_df["status"])

    t_km = kmf.survival_function_.index.values
    col = kmf.survival_function_.columns[0]
    S_km = kmf.survival_function_[col].values

    # overlay render
    overlay_png_abs = overlay_km_on_image(
        plot_path,
        t_km, S_km,
        x_start_px, x_end_px,
        y_start_px, y_end_px,
        x_min, x_max,
        y_min, y_max,
        censor_times=cens_t,
        output_dir=output_dir
    )

    overlay_png_web = f"/data/{os.path.basename(overlay_png_abs)}"

    # return f"/data/IPD_overlay_{ts}.csv", f"/data/KM_overlay_{ts}.png"
    return f"/data/{os.path.basename(ipd_path)}", overlay_png_web
