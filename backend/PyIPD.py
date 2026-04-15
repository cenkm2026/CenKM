import math
import numpy as np
import pandas as pd

import matplotlib.pyplot as plt
from lifelines import KaplanMeierFitter
from scipy import stats
import itertools

# assumes you already defined preprocess() and getIPD() in Python

def preprocess(dat, trisk=None, nrisk=None, totalpts=None, maxy=100):
    # Purpose: Preprocess digitized KM data and risk table inputs for reconstruction.
    # Inputs:
    # - dat (pd.DataFrame | array-like): Two-column time/survival data.
    # - trisk (array-like | None): Time points for risk table rows.
    # - nrisk (array-like | None): Numbers at risk corresponding to trisk.
    # - totalpts (int | None): Total points if no risk table is available.
    # - maxy (int | float): Max survival scale (100 for percent, 1 for proportion).
    # Outputs:
    # - dict: Preprocessed data and interval indices for downstream reconstruction.
    """
    Python mirror of IPDfromKM::preprocess (CRAN 0.1.10).
    Returns keys: preprocessdat, intervalIndex, endpts, inputdat
    """
    # ---- Input checks & naming ----
    if isinstance(dat, (list, tuple, np.ndarray)):
        dat = pd.DataFrame(dat)
    if not isinstance(dat, pd.DataFrame):
        raise ValueError("dat must be a DataFrame or table-like with 2 columns.")
    if dat.shape[1] != 2:
        raise ValueError("The dataset should have exactly two columns.")
    if len(dat) < 5:
        raise ValueError("Not enough read in points")

    dat = dat.copy()
    dat.columns = ["time", "sur"]
    inputdat = dat.copy()

    # rescale if percentages
    if maxy == 100:
        dat["sur"] = dat["sur"] / 100.0

    # drop NA and order by time
    dat = dat.dropna().sort_values("time").reset_index(drop=True)

    # ---- Outlier removal (Tukey fences on step size, k=0.5) ----
    # survspan = |surv - lag(surv)| with first lag = first surv
    surv = dat["sur"].to_numpy()
    survspan = np.abs(surv - np.r_[surv[0], surv[:-1]])
    q1, q3 = np.quantile(survspan, [0.25, 0.75])
    iqr = q3 - q1
    k = 0.5
    is_outliers = (survspan <= (q1 - k * iqr)) | (survspan >= (q3 + k * iqr))

    # takeaway = is_outliers & (lag==False) & (lead==True)
    lag_out = np.r_[False, is_outliers[:-1]]
    lead_out = np.r_[is_outliers[1:], True]
    takeaway = is_outliers & (~lag_out) & (lead_out)

    subdat = dat.loc[~takeaway, ["time", "sur"]].copy()

    # ---- Enforce non-increasing survival ----
    if len(subdat) >= 2:
        s = subdat["sur"].to_numpy()
        for i in range(1, len(s)):
            if s[i] > s[i - 1]:
                s[i] = s[i - 1]
        subdat["sur"] = s
    subdat = subdat.drop_duplicates().reset_index(drop=True)

    # ---- At most two reads per time: keep max and min ----
    g = subdat.sort_values(["time", "sur"], ascending=[True, False])
    kept = (
        g.groupby("time", group_keys=False)
         .apply(lambda df: pd.concat([df.iloc[[0]], df.iloc[[-1]]]).drop_duplicates()))
    subdat = kept.drop_duplicates().reset_index(drop=True)

    # ---- Formalize: valid ranges, sorted; ensure start (0,1) ----
    subdat = subdat[(subdat["sur"].between(0, 1)) & (subdat["time"] >= 0)]
    subdat = subdat.sort_values("time").reset_index(drop=True)
    if not (np.isclose(subdat.iloc[0, 0], 0.0) and np.isclose(subdat.iloc[0, 1], 1.0)):
        subdat = pd.concat([pd.DataFrame({"time": [0.0], "sur": [1.0]}), subdat],
                           ignore_index=True)
    # add id (1-based)
    subdat["id"] = np.arange(1, len(subdat) + 1, dtype=int)

    # ---- Format nrisk/trisk and nint ----
    if (nrisk is not None) and (trisk is not None):
        nrisk = np.asarray(nrisk, dtype=float).copy()
        trisk = np.asarray(trisk, dtype=float).copy()
        nint = len(nrisk)
        while nint >= 2 and nrisk[nint - 1] == 0 and nrisk[nint - 2] == 0:
            nint -= 1
        nrisk = nrisk[:nint]
        trisk = trisk[:nint]
    elif totalpts is None:
        raise ValueError("If there is no nrisk vector available, you must provide totalpts.")
    else:
        nrisk = np.asarray([float(totalpts)], dtype=float)
        trisk = np.asarray([0.0], dtype=float)
        nint = 1

    # ---- Interval index for each point (1-based intervals like R) ----
    # locate_interval: number of trisk <= time
    trisk_sorted = np.asarray(trisk, dtype=float)
    interval = np.searchsorted(trisk_sorted, subdat["time"].to_numpy(), side="right")
    interval[interval < 1] = 1  # safeguard for times < first trisk
    subdat["interval"] = interval.astype(int)

    # ---- riskmat by interval present in data ----
    riskmat_rows = []
    for iv, grp in subdat.groupby("interval", sort=True):
        lower = int(grp["id"].iloc[0])
        upper = int(grp["id"].iloc[-1])
        # iv is 1-based; align to arrays
        idx = iv - 1
        if idx < 0 or idx >= len(trisk_sorted):
            continue
        riskmat_rows.append({
            "interval": iv,
            "lower": lower,
            "upper": upper,
            "t.risk": float(trisk_sorted[idx]),
            "n.risk": float(nrisk[idx]),
        })
    riskmat = pd.DataFrame(riskmat_rows)[["t.risk", "lower", "upper", "n.risk"]]

    # ---- endpts (patients alive at end) ----
    if len(trisk_sorted) > 0 and len(riskmat) > 0:
        if riskmat["t.risk"].max() < trisk_sorted.max():
            endpts = float(np.min(nrisk))
        else:
            endpts = None
    else:
        endpts = None

    # ---- Console output (like R) ----
    print(f"Total points read from Kaplan-Meier curve= {len(inputdat)}")
    print(f"Points left after preprocess = {len(subdat)}")
    print("The indexes for each reported interval")
    print(riskmat)

    # ---- Return (R-compatible keys) ----
    return {
        "preprocessdat": subdat.reset_index(drop=True),   # time, surv, id, interval
        "intervalIndex": riskmat.reset_index(drop=True),  # t.risk, lower, upper, n.risk
        "endpts": endpts,
        "inputdat": inputdat.reset_index(drop=True),
        # convenience aliases if your downstream expects them:
        "newdat": subdat.reset_index(drop=True),
        "originaldat": inputdat.reset_index(drop=True),
    }



def getIPD(prep, armind=1, tot_events=None, n_boot=1000, random_state=0):
    # Purpose: Reconstruct IPD from preprocessed KM data and risk tables.
    # Inputs:
    # - prep (dict | list | tuple): Preprocess output or R-style list.
    # - armind (int): Treatment arm index assigned to reconstructed rows.
    # - tot_events (int | None): Total events if known; otherwise inferred.
    # - n_boot (int): Number of bootstrap samples for t-test p-value.
    # - random_state (int): RNG seed for reproducible bootstrap sampling.
    # Outputs:
    # - dict: Reconstructed IPD, risk matrices, tests, and summary metrics.
    """
    Python mirror of the R getIPD() you posted.
    Accepts:
      - prep as list/tuple: [dat, riskmat, endpts, ori_dat]
      - prep as dict: {'preprocessdat': df, 'intervalIndex': df, 'endpts': x, 'inputdat': df}

    dat columns: time, sur (or surv)
    riskmat columns: t.risk, lower, upper, n.risk (lower/upper are 1-based like R)
    """
    rng = np.random.default_rng(random_state)

    # ---- Unpack prep ----
# ---- Unpack prep (safe for DataFrames) ----
    def _pick(d, *keys):
        for k in keys:
            if k in d and d[k] is not None:
                return d[k]
        return None
    
    if isinstance(prep, dict):
        dat = _pick(prep, "preprocessdat", "newdat", "dat")
        riskmat = _pick(prep, "intervalIndex", "riskmat")
        endpts = prep.get("endpts", None)
        # handle numpy scalars (e.g., np.int64)
        if isinstance(endpts, (np.generic,)):
            endpts = endpts.item()
        ori_dat = _pick(prep, "inputdat", "originaldat", "dat")
    
        if dat is None or riskmat is None:
            raise ValueError("prep must include dat/preprocessdat and riskmat/intervalIndex.")
    else:
        # R-style list/tuple: [dat, riskmat, endpts, ori_dat]
        dat, riskmat, endpts, ori_dat = prep


    # ---- dat columns ----
    if "sur" in dat.columns:
        surv_col = "sur"
    elif "surv" in dat.columns:
        surv_col = "surv"
    else:
        raise ValueError("dat must contain 'sur' or 'surv' column.")

    TT = dat["time"].to_numpy(float)
    SS = dat[surv_col].to_numpy(float)
    total = len(dat)

    # ---- riskmat columns (prefer names, then positions) ----
    def _col(df, names, pos):
        for n in names:
            if n in df.columns:
                return df[n].to_numpy()
        return df.iloc[:, pos].to_numpy()

    t_risk = _col(riskmat, ["t.risk", "trisk", "t_risk"], 0).astype(float)
    lower_1b = _col(riskmat, ["lower"], 1).astype(int)
    upper_1b = _col(riskmat, ["upper"], 2).astype(int)
    n_risk = _col(riskmat, ["n.risk", "nrisk", "n_risk"], 3).astype(float)

    # Convert to 0-based for Python indexing
    lower = lower_1b - 1
    upper = upper_1b - 1

    ninterval = riskmat.shape[0]
    # In R: ncensor=rep(0, ninterval-1), but they later write ncensor[ninterval]
    ncensor = np.zeros(ninterval, dtype=float)
    lasti = np.zeros(ninterval, dtype=int)  # R used 1; we store 0-based

    cen = np.zeros(total, dtype=float)
    nhat = np.full(total + 1, n_risk[0] + 1.0, dtype=float)
    d = np.zeros(total, dtype=float)
    KM_hat = np.ones(total, dtype=float)

    # ---- intervals 1..(ninterval-1) ----
    if ninterval > 1:
        for i in range(ninterval - 1):
            # First approximation
            ncensor[i] = np.round(n_risk[i] * SS[lower[i + 1]] / SS[lower[i]] - n_risk[i + 1])

            # Adjust ncensor until nhat at start of next interval matches n_risk[i+1]
            while (
                (nhat[lower[i + 1]] > n_risk[i + 1] and ncensor[i] < (n_risk[i] - n_risk[i + 1] + 1))
                or (nhat[lower[i + 1]] < n_risk[i + 1] and ncensor[i] > 0)
            ):
                if ncensor[i] <= 0:
                    cen[lower[i]:upper[i] + 1] = 0.0
                    ncensor[i] = 0.0

                if ncensor[i] > 0:
                    ncen = int(ncensor[i])
                    cen_t = TT[lower[i]] + (np.arange(1, ncen + 1) *
                                            (TT[lower[i + 1]] - TT[lower[i]]) / (ncen + 1))
                    for k in range(lower[i], upper[i] + 1):
                        cen[k] = np.sum((TT[k] <= cen_t) & (cen_t < TT[k + 1]))

                nhat[lower[i]] = n_risk[i]
                last = lasti[i]

                for k in range(lower[i], upper[i] + 1):
                    if i == 0 and k == lower[i]:
                        d[k] = 0.0
                        KM_hat[k] = 1.0
                    else:
                        if KM_hat[last] != 0:
                            d[k] = np.round(nhat[k] * (1.0 - (SS[k] / KM_hat[last])))
                        else:
                            d[k] = 0.0
                        KM_hat[k] = KM_hat[last] * (1.0 - (d[k] / max(nhat[k], 1e-12)))
                    nhat[k + 1] = nhat[k] - d[k] - cen[k]
                    if d[k] != 0:
                        last = k

                # update ncensor for interval i by discrepancy
                ncensor[i] = ncensor[i] + (nhat[lower[i + 1]] - n_risk[i + 1])

            # prepare for next interval
            n_risk[i + 1] = nhat[lower[i + 1]]
            lasti[i + 1] = last

    # ---- last interval ----
    if ninterval > 1:
        if tot_events is None:
            leftd = 0.0
        else:
            temp = float(np.sum(d[: lower[ninterval - 1]])) if lower[ninterval - 1] > 0 else 0.0
            leftd = max(float(tot_events) - temp, 0.0)

        mm = 0.0 if endpts is None else float(endpts)

        mean_prev = np.mean(ncensor[: (ninterval - 1)]) if (ninterval - 1) > 0 else 0.0
        numer = (TT[total - 1] - t_risk[ninterval - 1])
        denom = (t_risk[ninterval - 1] - t_risk[ninterval - 2]) if ninterval >= 2 else 1.0
        ncensor[ninterval - 1] = min(mean_prev * (numer / denom), (n_risk[ninterval - 1] - mm - leftd))

    if ninterval == 1:
        ncensor[0] = 0.0 if tot_events is None else (n_risk[0] - float(tot_events))

    # distribute last-interval censors
    # distribute last-interval censors
    i_last = ninterval - 1
    if ncensor[i_last] <= 0:
        cen[lower[i_last]:upper[i_last] + 1] = 0.0
        ncensor[i_last] = 0.0
    elif upper[i_last] > lower[i_last]:
        ncen = int(ncensor[i_last])
        cen_t = TT[lower[i_last]] + (np.arange(1, ncen + 1) *
                                     (TT[upper[i_last]] - TT[lower[i_last]]) / (ncen + 1))
        for k in range(lower[i_last], upper[i_last] + 1):
            if k + 1 < len(TT):
                cen[k] = np.sum((TT[k] <= cen_t) & (cen_t < TT[k + 1]))
            else:
                # mirror R's "TT[k+1] is NA" behavior: treat as open-ended right tail
                cen[k] = np.sum(TT[k] <= cen_t)
        cen[np.isnan(cen)] = 0.0
    else:
        cen[upper[i_last]] = ncensor[i_last]

    # events & risk for last interval
    nhat[lower[i_last]] = n_risk[i_last]
    last = lasti[i_last]
    for k in range(lower[i_last], upper[i_last] + 1):
        if k == 0:
            d[k] = 0.0
            KM_hat[k] = 1.0
        else:
            if KM_hat[last] != 0:
                d[k] = np.round(nhat[k] * (1.0 - (SS[k] / KM_hat[last])))
            else:
                d[k] = 0.0
            KM_hat[k] = KM_hat[last] * (1.0 - (d[k] / max(nhat[k], 1e-12)))
        nhat[k + 1] = nhat[k] - d[k] - cen[k]
        if nhat[k + 1] < 0:
            nhat[k + 1] = 0.0
            cen[k] = nhat[k] - d[k]
        if d[k] != 0:
            last = k

    # ---- summaries per interval ----
    event_hat = np.zeros(ninterval, float)
    n_risk_hat = np.zeros(ninterval, float)
    censor_hat = np.zeros(ninterval, float)
    for i in range(ninterval):
        censor_hat[i] = np.sum(cen[lower[i]:upper[i] + 1])
        n_risk_hat[i] = nhat[lower[i]]
        event_hat[i] = np.sum(d[lower[i]:upper[i] + 1])

    riskmat_out = riskmat.copy()
    riskmat_out = pd.concat(
        [riskmat_out,
         pd.DataFrame({"n.risk.hat": n_risk_hat, "censor.hat": censor_hat, "event.hat": event_hat})],
        axis=1,
    )

    Points = pd.DataFrame({"time": TT, "surv": SS, "risk": nhat[:total], "censor": cen, "event": d})

    # ---- reconstruct IPD ----
    ipd_rows = []
    for i in range(total):
        if d[i] > 0:
            cnt = int(d[i])
            ipd_rows.append(pd.DataFrame({
                "time": np.full(cnt, TT[i]),
                "status": np.ones(cnt, int),
                "treat": np.full(cnt, armind, int)
            }))
        if cen[i] > 0:
            cnt = int(cen[i])
            tmid = (TT[i] + TT[i + 1]) / 2.0 if i < total - 1 else TT[i]
            ipd_rows.append(pd.DataFrame({
                "time": np.full(cnt, tmid),
                "status": np.zeros(cnt, int),
                "treat": np.full(cnt, armind, int)
            }))
    if nhat[total] > 0:
        cnt = int(nhat[total])
        ipd_rows.append(pd.DataFrame({
            "time": np.full(cnt, TT[-1]),
            "status": np.zeros(cnt, int),
            "treat": np.full(cnt, armind, int)
        }))
    IPD = pd.concat(ipd_rows, ignore_index=True) if ipd_rows else pd.DataFrame(columns=["time","status","treat"])

    # ---- compare survival (estimated vs read-in) ----
    kmf = KaplanMeierFitter()
    if len(IPD) > 0:
        kmf.fit(IPD["time"].values, event_observed=IPD["status"].values)
        # build tt & ss1 exactly like R (skip consecutive equal TT)
        tt, ss1 = [], []
        for i in range(total - 1):
            if TT[i] != TT[i + 1]:
                tt.append(TT[i]); ss1.append(SS[i])
        tt = np.array(tt, float); ss1 = np.array(ss1, float)
        ss2 = kmf.predict(tt).to_numpy() if tt.size > 0 else np.array([], float)
    else:
        tt = np.array([], float); ss1 = np.array([], float); ss2 = np.array([], float)

    # differences & RMSE
    if ss1.size <= 1:
        diff_s = ss2 - ss1
        rmse = float(np.abs(diff_s).mean()) if diff_s.size else 0.0
    else:
        diff_s = ss2 - ss1
        rmse = float((np.sum(diff_s ** 2) / (ss1.size - 1)) ** 0.5)

    del_s = 1.0 / 500.0
    var_surv = rmse ** 2 + del_s ** 2

    # Mann-Whitney (two-sided)
    if ss1.size > 0:
        mw = stats.mannwhitneyu(ss1, ss2, alternative="two-sided")
        mwtest = {"statistic": float(mw.statistic), "pvalue": float(mw.pvalue)}
    else:
        mwtest = {"statistic": np.nan, "pvalue": np.nan}

    # Bootstrap t-test p-value (Welch t)
    if ss1.size > 1:
        t0 = stats.ttest_ind(ss1, ss2, equal_var=False).statistic
        if np.isnan(t0):
            bootp = np.nan
        else:
            gt = 0
            n = ss1.size
            bootdat = np.column_stack([ss1, ss2])
            for _ in range(n_boot):
                idx = rng.integers(0, n, size=n)
                s1b, s2b = bootdat[idx, 0], bootdat[idx, 1]
                tb = stats.ttest_ind(s1b, s2b, equal_var=False).statistic
                if tb > t0:
                    gt += 1
            bootp = gt / n_boot
    else:
        bootp = np.nan

    # Summary table
    dtab = pd.DataFrame({
        "ResultSummary": [
            "Total Number of Patients",
            "Root Mean Square Error",
            "Variance of Survival Rates from the Reconstruction",
            "Mann-Whiteney Test P-value",
            "Bootstrap T Test P-value",
        ],
        "value": [
            int(IPD.shape[0]),
            round(rmse, 3),
            round(var_surv, 3),
            round(mwtest["pvalue"], 3) if not np.isnan(mwtest["pvalue"]) else np.nan,
            round(bootp, 3) if not np.isnan(bootp) else np.nan,
        ],
    })

    # Optional: print like R's cat/print
    print("\n")
    print(f"              Total number of patients is  {IPD.shape[0]}")
    print("  The summary of the estimation is as follow")
    print(riskmat_out)
    print(f"  The root mean square error(RMSE) of the estimations is {rmse}")
    print(f"  The max absolute error of the estimation is  {np.max(np.abs(diff_s)) if diff_s.size else 0.0}")
    print(f"  The variance of survival rates introduced by the reconstruction procedure is   {var_surv}\n")

    # Return
    return {
        "IPD": IPD,
        "Points": Points,
        "riskmat": riskmat_out,
        "endpts": endpts,
        "mwtest": mwtest,
        "bootp": bootp,
        "var_surv": var_surv,
        "dt": dtab,
    }


def match_best_ipd(
    df_digitized: pd.DataFrame,
    df_risk: pd.DataFrame,
    trisk,
    tot_events_list=None,      # usually None unless you truly know totals
    maxy=None,                 # let preprocess() decide scaling
    verbose: bool = True,
    w_start: float = 10.0,     # weight for |est0-orig0|/orig0
    w_surv: float = 1e-4       # tiny tiebreak from survival RMSE
):
    # Purpose: Match digitized curves to risk-table groups by minimizing mismatch.
    # Inputs:
    # - df_digitized (pd.DataFrame): Digitized curve points with curve IDs.
    # - df_risk (pd.DataFrame): Risk table values indexed by group.
    # - trisk (array-like): Time points for risk table rows.
    # - tot_events_list (list | dict | None): Optional total events per group.
    # - maxy (int | float | None): Survival scale for preprocess (100 or 1).
    # - verbose (bool): Whether to print diagnostic progress.
    # - w_start (float): Weight for initial risk mismatch penalty.
    # - w_surv (float): Weight for survival RMSE tiebreaker.
    # Outputs:
    # - tuple[pd.DataFrame, tuple, dict]: (best_ipd, best_mapping, diagnostics).
    """Map curves to groups by minimizing risk-table mismatch."""
    # --- helpers ---
    def _get_survival_series(df_curve):
        for col in ("sur", "St", "Survival"):
            if col in df_curve.columns:
                return pd.to_numeric(df_curve[col], errors="coerce")
        raise ValueError("df_digitized must have 'sur', 'St', or 'Survival'.")

    def _resolve_tot_events(group, curve_idx):
        if isinstance(tot_events_list, dict):
            return tot_events_list.get(group)
        if isinstance(tot_events_list, (list, tuple, np.ndarray)):
            return int(tot_events_list[curve_idx]) if curve_idx < len(tot_events_list) else None
        return None

    # keep original curve order of appearance (not lexicographic)
    first_order = df_digitized.drop_duplicates('curve')['curve'].tolist()
    curve_ids = first_order
    risk_groups = df_risk.index.tolist()
    trisk = np.asarray(trisk, float)

    best_score = float('inf')
    best_ipd = None
    best_mapping = None
    best_diag = None

    for perm in itertools.permutations(risk_groups, len(curve_ids)):
        ipd_all = []
        total_score = 0.0
        per_curve = []
        ok = True

        for i, curve_id in enumerate(curve_ids):
            group = perm[i]
            if verbose:
                print(f"Trying curve {curve_id} ↔ '{group}'")

            cols_sur = [c for c in ['sur','St','Survival'] if c in df_digitized.columns]
            df_curve = df_digitized.loc[df_digitized['curve'] == curve_id, ['time'] + cols_sur].copy()
            df_curve['time'] = pd.to_numeric(df_curve['time'], errors='coerce')
            S = _get_survival_series(df_curve)
            df_curve = pd.DataFrame({'time': df_curve['time'], 'sur': S}).dropna()
            if df_curve.empty:
                ok = False
                total_score += 1e6
                if verbose: print("  empty after cleaning → penalize")
                continue

            nrisk_vec = df_risk.loc[group].to_numpy(float)

            # preprocess (handles scaling; outputs 0..1 in 'sur')
            prep = preprocess(
                dat=df_curve[['time','sur']],
                trisk=trisk,
                nrisk=nrisk_vec,
                totalpts=None,
                maxy=maxy
            )

            # reconstruct (do not force tot_events unless known)
            tot_ev = _resolve_tot_events(group, i)
            res = getIPD(prep, armind=i+1, tot_events=tot_ev)

            ipd_df = res['IPD'].copy()
            ipd_df['Group'] = group
            ipd_df['curve'] = curve_id
            ipd_all.append(ipd_df)

            # ---- risk-table mismatch (align by t.risk) ----
            orig_df = prep['intervalIndex'][['t.risk','n.risk']].copy()
            if 'n.risk.hat' in res['riskmat'].columns:
                est_df = res['riskmat'][['t.risk','n.risk.hat']].rename(columns={'n.risk.hat':'est'})
            else:
                est_df = res['riskmat'].iloc[:, [0, -3]].copy()
                est_df.columns = ['t.risk','est']
            m = pd.merge(orig_df, est_df, on='t.risk', how='inner')

            orig = m['n.risk'].to_numpy(float)
            est  = m['est'].to_numpy(float)

            # normalized RMSE over the risk table (scale-free)
            risk_norm = float(np.sqrt(np.mean(((orig - est) / np.maximum(orig, 1.0))**2)))
            start_pen = float(abs(est[0] - orig[0]) / max(orig[0], 1.0))

            # tiny survival tiebreaker (optional)
            rmse_surv = 0.0
            if len(ipd_df) > 0:
                newdat = prep['preprocessdat']
                TT = newdat['time'].to_numpy(float)
                SS = newdat['sur'].to_numpy(float)   # already 0..1
                tt, ss1 = [], []
                for k in range(len(TT) - 1):
                    if TT[k] != TT[k+1]:
                        tt.append(TT[k]); ss1.append(SS[k])
                if tt:
                    kmf = KaplanMeierFitter().fit(ipd_df['time'].values, event_observed=ipd_df['status'].values)
                    ss2 = kmf.predict(np.asarray(tt, float)).to_numpy()
                    rmse_surv = float(np.sqrt(np.mean((ss2 - np.asarray(ss1, float))**2))) if ss1 else 0.0

            score = risk_norm + w_start * start_pen + w_surv * rmse_surv
            total_score += score

            if verbose:
                print(f"  risk_norm={risk_norm:.5f}  start_pen={start_pen:.5f}  survRMSE={rmse_surv:.5f}  "
                      f"=> score={score:.5f}")

            per_curve.append({
                'curve_id': curve_id, 'group': group,
                'risk_norm': risk_norm, 'start_pen': start_pen, 'rmse_surv': rmse_surv,
                'orig_nrisk': orig, 'est_nrisk': est, 'score': score
            })

        if ok and len(ipd_all) == len(curve_ids) and total_score < best_score:
            best_score = total_score
            best_ipd = pd.concat(ipd_all, ignore_index=True)
            best_mapping = perm
            best_diag = {
                'per_curve': per_curve,
                'score_total': best_score,
                'nrisk_orig_by_group': {d['group']: d['orig_nrisk'] for d in per_curve},
                'nrisk_est_by_group': {d['group']: d['est_nrisk'] for d in per_curve},
            }

    if verbose:
        print(f"\nBest match: {best_mapping} with total score {best_score:.6f}")
        if best_diag:
            for d in best_diag['per_curve']:
                print(f"  {d['curve_id']} -> {d['group']}: score={d['score']:.5f} "
                      f"(risk {d['risk_norm']:.5f}, start {d['start_pen']:.5f}, surv {d['rmse_surv']:.5f})")

    return best_ipd, best_mapping, best_diag
