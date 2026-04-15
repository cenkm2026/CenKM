import numpy as np
import pandas as pd
from lifelines import KaplanMeierFitter
from typing import List, Dict, Tuple, Optional, Union, Any, Iterable

def _km_survival_at(times: np.ndarray, events: np.ndarray, t0: float) -> float:
    """ 
    Calculates the Kaplan–Meier survival estimate
    events: 1 = event (death), 0 = right-censored
    times: array of observed times (events or censoring)
    events: array of 1=event (death), 0=censor
    t0: the time at which we want S(t0)
    """

    mask_event = (events == 1) # select only event (death) times
    event_times = np.unique(times[mask_event]) # unique event times
    event_times = event_times[event_times <= t0] # keep the events that occur before or at t0
    if event_times.size == 0:
        return 1.0 # if no event, survival = 1.0
    S = 1.0
    # Loop through each event time (u) up to t0
    for u in np.sort(event_times):
        r_u = np.sum(times >= u) # number at risk at u
        d_u = np.sum((times == u) & (events == 1)) # number of death at u
        if r_u > 0:
            S *= (1.0 - d_u / r_u) # update KM survival
    return float(S)

def _try_add_censors_in_bin(
    base_t: np.ndarray,
    base_e: np.ndarray,
    p0: int,
    n: int,
    S_target: float,
    t_prev: float,
    t_i: float,
    bin_cens_times: np.ndarray,
    tol: float,
    cap: int,
    rng,
    debug: bool = True
) -> Tuple[np.ndarray, np.ndarray, int, float, int]:
    """
    Try to reduce |KM - S_target| by adding extra censors in [t_prev, t_i).
    If the cap is reached and the tolerance still not satisfied, 
    return the original arrays (no censors added).
    Returns (new_t, new_e, new_p, est_S, extras_added).
    """
    # Backup original
    t_orig = base_t.copy()
    e_orig = base_e.copy()
    p_orig = int(p0)
    est_orig = _km_survival_at(t_orig, e_orig, t_i)

    # Working copies
    t_work = t_orig.copy()
    e_work = e_orig.copy()
    p_work = p_orig
    est_curr = est_orig
    extras = 0
    can_sample = bin_cens_times.size > 0

    while (abs(est_curr - S_target) > tol) and (extras < cap) and (p_work < n):
        if not can_sample:
            break

        c_time = rng.choice(bin_cens_times)
        t_work[p_work] = c_time
        e_work[p_work] = 0
        p_work += 1
        extras += 1
        est_curr = _km_survival_at(t_work, e_work, t_i)

        if debug:
            print(f'Added censor at {c_time:.4f}, new est_S={est_curr:.6f}, error = {est_curr - S_target:.6f}')

    # If still outside tolerance after reaching cap, revert to original
    if (abs(est_curr - S_target) > tol) and (extras >= cap):
        if debug:
            print(f"Reached censor cap ({cap}) but |est_S - target|={abs(est_curr - S_target):.6f} > tol={tol:.6f}, reverting all.")
        return t_orig, e_orig, p_orig, est_orig, 0

    return t_work, e_work, p_work, est_curr, extras

# commit pointer already handled in branches/fallbacks; proceed to next bin
def _at_risk_count(t_arr: np.ndarray, tau: float, semantics: str = "left") -> int:
    if semantics == "right":
        return int(np.sum(t_arr > tau))
    return int(np.sum(t_arr >= tau))

def _nextbefore(x: float) -> float:
    # the largest float strictly less than x (tiny epsilon step)
    return float(np.nextafter(x, -np.inf))


def _nextafter(x: float) -> float:
    return float(np.nextafter(x, np.inf))


def _interval_mask(times: np.ndarray, prev_tau: float, tau: float, semantics: str, eps: float = 1e-9) -> np.ndarray:
    if semantics == "right":
        return (times > prev_tau + eps) & (times <= tau + eps)
    return (times >= prev_tau - eps) & (times < tau - eps)


def _included_boundary_time(tau: float, semantics: str) -> float:
    return _nextafter(tau) if semantics == "right" else float(tau)


def _sample_interval_censor_times(
    prev_tau: float,
    tau: float,
    count: int,
    *,
    known_censor_times: Optional[Iterable[float]] = None,
    semantics: str = "left",
    rng=None,
    eps: float = 1e-9,
) -> np.ndarray:
    if count <= 0:
        return np.array([], dtype=float)

    if rng is None:
        rng = np.random.default_rng()

    known = np.asarray(list(known_censor_times) if known_censor_times is not None else [], dtype=float)
    known = known[np.isfinite(known)] if known.size > 0 else known
    if known.size > 0:
        known = known[_interval_mask(known, prev_tau, tau, semantics, eps=eps)]
        if known.size > 0:
            sampled = rng.choice(known, size=count, replace=True)
            return np.sort(np.asarray(sampled, dtype=float))

    if semantics == "right":
        low = _nextafter(prev_tau)
        high = float(tau)
        fallback = float(tau)
    else:
        low = float(prev_tau)
        high = _nextbefore(tau)
        fallback = _nextbefore(tau)

    if not np.isfinite(low):
        low = float(prev_tau)
    if not np.isfinite(high):
        high = float(tau)
    if high <= low:
        return np.full(count, fallback, dtype=float)

    sampled = rng.uniform(low=low, high=high, size=count)
    return np.sort(np.asarray(sampled, dtype=float))


def _interval_drop_mask(times: np.ndarray, prev_tau: float, tau: float, semantics: str, eps: float = 1e-9) -> np.ndarray:
    if semantics == "right":
        return (times > prev_tau + eps) & (times <= tau + eps)
    return (times >= prev_tau - eps) & (times < tau - eps)


def _tail_mask(times: np.ndarray, start_tau: float, semantics: str, eps: float = 1e-9) -> np.ndarray:
    if semantics == "right":
        return times > start_tau + eps
    return times >= start_tau - eps


def _pick_evenly_spaced_subset(values: np.ndarray, count: int) -> np.ndarray:
    if count <= 0 or values.size == 0:
        return np.array([], dtype=float)
    if values.size <= count:
        return np.sort(values.astype(float))

    raw = np.linspace(0, values.size - 1, num=count)
    indexes = np.unique(np.round(raw).astype(int))
    if indexes.size < count:
        remaining = [idx for idx in range(values.size) if idx not in indexes]
        for idx in remaining:
            indexes = np.append(indexes, idx)
            if indexes.size >= count:
                break
    indexes = np.sort(indexes[:count])
    return np.sort(values[indexes].astype(float))


def _regular_interval_times(
    prev_tau: float,
    tau: float,
    count: int,
    semantics: str,
) -> np.ndarray:
    if count <= 0:
        return np.array([], dtype=float)

    if semantics == "right":
        low = _nextafter(prev_tau)
        high = float(tau)
        fallback = float(tau)
    else:
        low = _nextafter(prev_tau)
        high = _nextbefore(tau)
        fallback = _nextbefore(tau)

    if not np.isfinite(low):
        low = float(prev_tau)
    if not np.isfinite(high):
        high = float(tau)
    if high <= low:
        return np.full(count, fallback, dtype=float)

    fractions = (np.arange(count, dtype=float) + 1.0) / float(count + 1)
    return low + fractions * (high - low)


def _prepare_interval_censor_times(
    prev_tau: float,
    tau: float,
    total_count: int,
    explicit_times: np.ndarray,
    semantics: str,
) -> np.ndarray:
    if total_count <= 0:
        return np.array([], dtype=float)

    explicit_sorted = np.sort(explicit_times.astype(float)) if explicit_times.size > 0 else np.array([], dtype=float)
    explicit_used = _pick_evenly_spaced_subset(explicit_sorted, min(total_count, explicit_sorted.size))
    remaining = int(total_count - explicit_used.size)
    synthetic = _regular_interval_times(prev_tau, tau, remaining, semantics)
    if explicit_used.size == 0:
        return np.sort(synthetic)
    if synthetic.size == 0:
        return np.sort(explicit_used)
    return np.sort(np.concatenate([explicit_used, synthetic]))


def _choose_event_count(
    n_before: int,
    current_surv: float,
    target_surv: float,
) -> tuple[int, float]:
    if n_before <= 0:
        return 0, float(current_surv)

    current_surv = float(max(min(current_surv, 1.0), 0.0))
    target_surv = float(max(min(target_surv, current_surv), 0.0))
    if current_surv <= 1e-12:
        return 0, current_surv

    approx = n_before * (1.0 - (target_surv / max(current_surv, 1e-12)))
    center = int(round(approx))
    lo = max(0, center - 3)
    hi = min(n_before, center + 3)
    candidates = set(range(lo, hi + 1))
    candidates.update({0, min(n_before, int(np.floor(approx))), min(n_before, int(np.ceil(approx))), center})

    best_event_count = 0
    best_surv = current_surv
    best_score = None
    for event_count in sorted(candidates):
        surv_after = current_surv * (1.0 - (float(event_count) / float(n_before)))
        score = (
            abs(surv_after - target_surv),
            abs(event_count - approx),
            event_count,
        )
        if best_score is None or score < best_score:
            best_score = score
            best_event_count = int(event_count)
            best_surv = float(surv_after)
    return best_event_count, best_surv


def _simulate_interval(
    start_n: int,
    start_surv: float,
    drop_times: np.ndarray,
    target_surv: np.ndarray,
    censor_times: np.ndarray,
) -> dict[str, Any]:
    current_n = int(start_n)
    current_surv = float(start_surv)
    censor_times = np.sort(censor_times.astype(float)) if censor_times.size > 0 else np.array([], dtype=float)
    cursor = 0
    events: list[tuple[float, int]] = []
    sq_error = 0.0

    for drop_time, drop_surv in zip(drop_times.astype(float), target_surv.astype(float)):
        while cursor < censor_times.size and censor_times[cursor] < drop_time:
            if current_n <= 0:
                break
            current_n -= 1
            cursor += 1

        if current_n <= 0:
            events.append((float(drop_time), 0))
            sq_error += float((current_surv - drop_surv) ** 2)
            continue

        event_count, surv_after = _choose_event_count(current_n, current_surv, float(drop_surv))
        current_n -= int(event_count)
        current_surv = float(surv_after)
        events.append((float(drop_time), int(event_count)))
        sq_error += float((current_surv - float(drop_surv)) ** 2)

    while cursor < censor_times.size and current_n > 0:
        current_n -= 1
        cursor += 1

    rmse = float(np.sqrt(sq_error / max(len(drop_times), 1))) if len(drop_times) else 0.0
    return {
        "end_n": int(current_n),
        "end_surv": float(current_surv),
        "events": events,
        "curve_rmse": rmse,
    }


def _interval_candidate_score(
    end_n: int,
    target_end_n: int,
    curve_rmse: float,
    censor_count: int,
    guess_censor_count: int,
) -> tuple[float, float, int, int]:
    end_diff = abs(int(end_n) - int(target_end_n))
    risk_penalty = max(0, end_diff - 2)
    return (
        float(risk_penalty),
        float(curve_rmse),
        int(end_diff),
        abs(int(censor_count) - int(guess_censor_count)),
    )


def _reconstruct_intervalwise_ipd(
    n: int,
    drop_times: np.ndarray,
    drop_surv: np.ndarray,
    censor_candidates: np.ndarray,
    risk_table: pd.DataFrame,
    risk_semantics: str,
    debug: bool = False,
) -> pd.DataFrame:
    rt = risk_table.copy()
    rt = rt.sort_values("time").reset_index(drop=True)
    if rt.empty:
        raise ValueError("Risk table is required for interval-wise reconstruction")

    if float(rt.iloc[0]["time"]) > 0.0:
        rt = pd.concat(
            [
                pd.DataFrame([{"time": 0.0, "n_at_risk": int(n)}]),
                rt,
            ],
            ignore_index=True,
        )
    else:
        rt.loc[0, "n_at_risk"] = int(n)

    drop_times = np.asarray(drop_times, dtype=float)
    drop_surv = np.asarray(drop_surv, dtype=float)
    order = np.argsort(drop_times, kind="mergesort")
    drop_times = drop_times[order]
    drop_surv = np.minimum.accumulate(drop_surv[order]) if drop_surv.size > 0 else drop_surv

    censor_candidates = np.asarray(censor_candidates, dtype=float)
    censor_candidates = censor_candidates[np.isfinite(censor_candidates)] if censor_candidates.size > 0 else censor_candidates
    censor_candidates = np.sort(censor_candidates)

    event_times: list[float] = []
    censor_times: list[float] = []
    current_n = int(rt.iloc[0]["n_at_risk"])
    current_surv = 1.0

    for interval_index in range(len(rt) - 1):
        prev_tau = float(rt.iloc[interval_index]["time"])
        tau = float(rt.iloc[interval_index + 1]["time"])
        target_end_n = int(rt.iloc[interval_index + 1]["n_at_risk"])

        drop_mask = _interval_drop_mask(drop_times, prev_tau, tau, risk_semantics)
        interval_drop_times = drop_times[drop_mask]
        interval_drop_surv = drop_surv[drop_mask]
        explicit_mask = _interval_mask(censor_candidates, prev_tau, tau, risk_semantics)
        explicit_interval = censor_candidates[explicit_mask]

        min_censors = int(explicit_interval.size)
        max_censors = max(0, current_n - target_end_n)
        last_target_surv = float(interval_drop_surv[-1]) if interval_drop_surv.size > 0 else float(current_surv)
        approx_events = int(round(max(0.0, current_n * (1.0 - (last_target_surv / max(current_surv, 1e-12))))))
        guess_censors = int(np.clip(current_n - target_end_n - approx_events, 0, max_censors))

        best: dict[str, Any] | None = None
        best_score = None
        upper_censor_count = max(max_censors, min_censors)
        for censor_count in range(min_censors, upper_censor_count + 1):
            candidate_censor_times = _prepare_interval_censor_times(
                prev_tau,
                tau,
                censor_count,
                explicit_interval,
                risk_semantics,
            )
            candidate = _simulate_interval(
                current_n,
                current_surv,
                interval_drop_times,
                interval_drop_surv,
                candidate_censor_times,
            )
            score = _interval_candidate_score(
                candidate["end_n"],
                target_end_n,
                candidate["curve_rmse"],
                censor_count,
                guess_censors,
            )
            if best_score is None or score < best_score:
                best_score = score
                best = {
                    **candidate,
                    "censor_times": candidate_censor_times,
                    "censor_count": int(censor_count),
                }

        if best is None:
            raise RuntimeError(f"Failed to build interval candidate for ({prev_tau}, {tau})")

        if debug:
            print(
                f"[interval] {interval_index} {prev_tau:.4f}->{tau:.4f} "
                f"start_n={current_n} target_end={target_end_n} "
                f"explicit_censors={explicit_interval.size} "
                f"chosen_censors={best['censor_count']} end_n={best['end_n']} rmse={best['curve_rmse']:.6f}"
            )

        for event_time, event_count in best["events"]:
            if event_count <= 0:
                continue
            event_times.extend([float(event_time)] * int(event_count))
        censor_times.extend(float(value) for value in np.asarray(best["censor_times"], dtype=float))

        current_n = int(best["end_n"])
        current_surv = float(best["end_surv"])

    if len(rt) > 0:
        tail_start = float(rt.iloc[-1]["time"])
    else:
        tail_start = 0.0
    tail_mask = _tail_mask(drop_times, tail_start, risk_semantics)
    tail_drop_times = drop_times[tail_mask]
    tail_drop_surv = drop_surv[tail_mask]

    if censor_candidates.size > 0:
        if risk_semantics == "right":
            explicit_tail = censor_candidates[censor_candidates > tail_start]
        else:
            explicit_tail = censor_candidates[censor_candidates >= tail_start]
    else:
        explicit_tail = np.array([], dtype=float)

    tail_sim = _simulate_interval(
        current_n,
        current_surv,
        tail_drop_times,
        tail_drop_surv,
        explicit_tail,
    )
    for event_time, event_count in tail_sim["events"]:
        if event_count <= 0:
            continue
        event_times.extend([float(event_time)] * int(event_count))
    censor_times.extend(float(value) for value in explicit_tail.astype(float))

    remaining_n = int(max(0, tail_sim["end_n"]))
    max_follow_up = 0.0
    if drop_times.size > 0:
        max_follow_up = max(max_follow_up, float(drop_times.max()))
    if censor_candidates.size > 0:
        max_follow_up = max(max_follow_up, float(censor_candidates.max()))
    max_follow_up = max(max_follow_up, tail_start)
    if remaining_n > 0:
        censor_times.extend([float(max_follow_up)] * remaining_n)

    rows: list[dict[str, Any]] = []
    rows.extend({"time": float(time_value), "event": 1} for time_value in event_times)
    rows.extend({"time": float(time_value), "event": 0} for time_value in censor_times)

    ipd = pd.DataFrame(rows, columns=["time", "event"])
    if ipd.empty:
        ipd = pd.DataFrame({"time": [0.0] * int(n), "event": [0] * int(n)})
    ipd = ipd.sort_values(["time", "event"], ascending=[True, False]).reset_index(drop=True)

    if len(ipd) < int(n):
        filler_time = float(max_follow_up)
        filler = pd.DataFrame({"time": [filler_time] * (int(n) - len(ipd)), "event": [0] * (int(n) - len(ipd))})
        ipd = pd.concat([ipd, filler], ignore_index=True).sort_values(["time", "event"], ascending=[True, False]).reset_index(drop=True)
    elif len(ipd) > int(n):
        ipd = ipd.iloc[: int(n)].copy().reset_index(drop=True)

    return ipd

def _align_single_boundary(
    IPD_t: np.ndarray,
    IPD_e: np.ndarray,
    tau: float,
    target_at_risk: int,
    prev_tau: float,
    p: int,
    known_censor_times: Optional[Iterable[float]] = None,
    semantics: str = "left",
    eps: float = 1e-9,
    rng: Optional[np.random.Generator] = None,
    interval_length: float = 0.1,
    debug: bool = False
):
    """
    Adjust censor times (only) to match target at-risk at time `tau`.

    Uses censor-only edits to steer the reconstructed at-risk count toward the risk table.
    - If the current at-risk count is too low, move previously assigned censors from the
      current interval onto the boundary so they are counted at `tau`.
    - If the current at-risk count is too high, allocate new censor rows inside the interval
      `(prev_tau, tau]` / `[prev_tau, tau)` depending on the requested semantics.

    Returns
    -------
    IPD_t, IPD_e, p, n_adjusted
      - `p` is the next free row after any newly allocated censor rows.
      - `n_adjusted` is positive when rows were moved onto the boundary and negative when
        new censor rows were allocated before the boundary.
    """
    if rng is None:
        rng = np.random.default_rng()

    current = _at_risk_count(IPD_t, tau, semantics=semantics)
    delta = target_at_risk - current

    if delta == 0:
        return IPD_t, IPD_e, p, 0

    cens_idx = np.where(IPD_e == 0)[0]
    donors = cens_idx[_interval_mask(IPD_t[cens_idx], prev_tau, tau, semantics, eps=eps)]

    if delta > 0:
        need = delta
        if donors.size == 0:
            if debug:
                print(f"No existing censors in interval for tau={tau:.4f}; cannot raise at-risk count by {need}")
            return IPD_t, IPD_e, p, 0

        move_count = int(min(need, donors.size))
        donor_order = donors[np.argsort(IPD_t[donors], kind="mergesort")]
        move_ids = donor_order[-move_count:]
        IPD_t[move_ids] = _included_boundary_time(tau, semantics)
        if debug:
            updated = _at_risk_count(IPD_t, tau, semantics=semantics)
            print(f"Moved {move_count} censors onto boundary tau={tau:.4f}; at-risk now {updated}")
        return IPD_t, IPD_e, p, move_count

    need = int(min(-delta, len(IPD_t) - p))
    if need <= 0:
        if debug:
            print(f"No free rows available to reduce at-risk at tau={tau:.4f}")
        return IPD_t, IPD_e, p, 0

    new_times = _sample_interval_censor_times(
        prev_tau,
        tau,
        need,
        known_censor_times=known_censor_times,
        semantics=semantics,
        rng=rng,
        eps=eps,
    )
    end = p + len(new_times)
    IPD_t[p:end] = new_times
    IPD_e[p:end] = 0
    p = end
    if debug:
        updated = _at_risk_count(IPD_t, tau, semantics=semantics)
        print(f"Added {len(new_times)} censors before tau={tau:.4f}; at-risk now {updated}")
    return IPD_t, IPD_e, p, -int(len(new_times))
    
def get_ipd(
    n: int,
    t: Iterable[float],
    S: Iterable[float],
    cens_t: Optional[Iterable[float]] = None,
    match_tol: float = 5e-3,               # tolerance for |est_S - S_target|
    max_extra_censors_per_bin: int = 100,  # guardrail per bin
    random_state: Optional[int] = None,
    risk_table: Optional[pd.DataFrame] = None,  # for reproducible sampling,
    risk_semantics: str = "left",
    debug: bool = False
) -> pd.DataFrame:
    """
    Reconstruct individual patient data (IPD) from digitized KM data, allowing
    multiple patients to share the same censor time.

    NEW: When deciding whether to keep the last placed death or revert it, we
    branch two candidates ("after" vs "before"), try adding extra censors within
    the bin for both branches (up to a cap), then pick the branch with the lower
    absolute error to the target survival at the drop time.
    """
    rng = np.random.RandomState(random_state)

    # ---- Preprocessing ----
    t = np.asarray(list(t), dtype=float)  # event (drop) times
    S = np.asarray(list(S), dtype=float)  # survival proportions

    if cens_t is None:
        cens = np.array([], dtype=float)
        has_cens = False
    else:
        cens = np.asarray(list(cens_t), dtype=float)
        cens = cens[~np.isnan(cens)]
        has_cens = cens.size > 0

    # Sorts
    t = np.sort(t) if t.size > 0 else np.array([], dtype=float)
    S = np.sort(S)[::-1] if S.size > 0 else np.array([], dtype=float)
    if has_cens:
        cens = np.sort(cens)

    # Clamp invalids
    if t.size > 0:
        t = np.where(t < 0, 0.0, t)
    if S.size > 0:
        S = np.where(S > 1, 1.0, S)

    # Initialize KM curve with origin
    t = np.concatenate(([0.0], t))
    S = np.concatenate(([1.0], S))

    if risk_table is not None and len(risk_table) > 0:
        return _reconstruct_intervalwise_ipd(
            n=int(n),
            drop_times=t,
            drop_surv=S,
            censor_candidates=cens if has_cens else np.array([], dtype=float),
            risk_table=risk_table,
            risk_semantics=risk_semantics,
            debug=debug,
        )

    # Determine max follow-up
    maxFU_candidates = [np.max(t)] if t.size > 0 else []
    if has_cens and cens.size > 0:
        maxFU_candidates.append(np.max(cens))
    maxFU = float(np.max(maxFU_candidates)) if maxFU_candidates else 0.0

    # Prepare risk times if provided
    if risk_table is not None and len(risk_table) > 0:
        rt = risk_table.copy()
        # enforce monotone increasing times
        rt = rt.sort_values("time").reset_index(drop=True)
        risk_times = rt["time"].to_numpy(dtype=float)
        risk_targets = rt["n_at_risk"].to_numpy(dtype=int)
        diffs = np.diff(risk_times)
        positive_diffs = diffs[diffs > 0]
        interval_length = float(np.median(positive_diffs)) if positive_diffs.size > 0 else 0.1
    else:
        risk_times = None
        risk_targets = None
        interval_length = 0.1

    risk_idx = 0

    # Allocate shells
    IPD_t = np.full(n, maxFU, dtype=float)   # default: censored at maxFU
    IPD_e = np.zeros(n, dtype=int)           # default: censored
    p = 0                                    # next free slot

    last_avail_censor_bin = np.array([cens[0]], dtype=float)
    # Main loop over bins between consecutive drops
    for i in range(1, len(t)):
        if debug:
            print(f"Processing bin {i}/{len(t)-1}, p={p}/{n}", 'Target S:', S[i] if i < len(S) else (S[-1] if len(S) > 0 else 1.0))

        t_prev, t_i = t[i - 1], t[i]
        S_target = S[i] if i < len(S) else (S[-1] if len(S) > 0 else 1.0)

        # --- Risk-table alignment: fix all risk times τ with τ <= t_i and not yet aligned ---
        if risk_times is not None:
            while risk_idx < len(risk_times) and risk_times[risk_idx] <= t_i:
                tau = risk_times[risk_idx]
                target = risk_targets[risk_idx]
                prev_tau = 0.0 if risk_idx == 0 else float(risk_times[risk_idx - 1])
                boundary_censors = np.array([], dtype=float)
                if has_cens:
                    boundary_censors = cens[_interval_mask(cens, prev_tau, tau, risk_semantics)]
                output = _align_single_boundary(
                    IPD_t,
                    IPD_e,
                    tau,
                    target,
                    prev_tau,
                    p,
                    known_censor_times=boundary_censors,
                    semantics=risk_semantics,
                    interval_length=interval_length,
                    rng=rng,
                    debug=debug,
                )
                IPD_t, IPD_e, p, n_adjusted = output
                risk_idx += 1
                if debug:
                    print(
                        'After alignment:',
                        _at_risk_count(IPD_t, risk_times[risk_idx - 1], semantics=risk_semantics)
                        if risk_times is not None and risk_idx > 0
                        else "N/A",
                    )

        # Start Processing
        if debug:
            print(f"Processing bin {i}/{len(t)-1} with p={p}/{n} at time {t[i]:.4f}", 'Target S:', S_target)
        # ---- 1) Place known censors in this bin ----
        bin_mask = np.array([], dtype=bool)
        bin_cens_times = np.array([], dtype=float)
        if has_cens:
            bin_mask = (cens >= t_prev) & (cens < t_i)
            bin_cens_times = cens[bin_mask]  # may be empty, may contain duplicates

            if bin_cens_times.size > 0 and p < n:
                n_cens_place = int(min(bin_cens_times.size, n - p))
                if n_cens_place > 0:
                    csel = bin_cens_times[:n_cens_place]
                    IPD_t[p:p + n_cens_place] = csel
                    IPD_e[p:p + n_cens_place] = 0
                    p += n_cens_place
            
            # Update the rolling "last available" bin if this bin has censors
            if bin_cens_times.size > 0:
                last_avail_censor_bin = bin_cens_times

        # ---- 2) Add deaths at the drop to match target survival ----
        n_died = 0
        est_S = _km_survival_at(IPD_t, IPD_e, t_i)
        diff = est_S - S_target

        death_indices_this_bin = []   # absolute indices in IPD arrays

        # Iteratively add deaths until we cross or meet the target
        while (diff > 0.0) and (p + n_died < n):
            idx = p + n_died
            IPD_t[idx] = t_i
            IPD_e[idx] = 1
            death_indices_this_bin.append(idx)
            n_died += 1
            est_S = _km_survival_at(IPD_t, IPD_e, t_i)
            diff = est_S - S_target
            if debug:
                print(f'  Placed death at {t_i:.4f}, new est_S={est_S:.6f}, error = {diff:.6f}')

        # ---- 2.5) Branch-and-compare with extra censors (AFTER: m+1, BEFORE: m, WAY_BEFORE: m-1) ----
        # We now decide among three candidates:
        #   AFTER      -> keep all deaths placed in this bin (n_died = m+1)
        #   BEFORE     -> revert the last placed death          (n_died = m)
        #   WAY_BEFORE -> revert the last TWO placed deaths     (n_died = m-1), if n_died >= 2
        if n_died > 0:
            # ---------- AFTER (m+1) ----------
            IPD_t_after = IPD_t.copy()
            IPD_e_after = IPD_e.copy()
            p_after = p + n_died
            est_after = _km_survival_at(IPD_t_after, IPD_e_after, t_i)
            IPD_t_after2, IPD_e_after2, p_after2, est_after2, extras_after = _try_add_censors_in_bin(
                IPD_t_after, IPD_e_after, p_after, n, S_target, t_prev, t_i,
                bin_cens_times, match_tol, max_extra_censors_per_bin, rng, debug=debug
            )
            err_after = abs(est_after2 - S_target)

            # ---------- BEFORE (m) ----------
            last_idx = death_indices_this_bin[-1]
            IPD_t_before = IPD_t.copy()
            IPD_e_before = IPD_e.copy()
            # revert the last death to a tail censor at maxFU
            IPD_t_before[last_idx] = maxFU
            IPD_e_before[last_idx] = 0
            p_before = p + (n_died - 1)
            est_before = _km_survival_at(IPD_t_before, IPD_e_before, t_i)
            IPD_t_before2, IPD_e_before2, p_before2, est_before2, extras_before = _try_add_censors_in_bin(
                IPD_t_before, IPD_e_before, p_before, n, S_target, t_prev, t_i,
                bin_cens_times, match_tol, max_extra_censors_per_bin, rng, debug=debug
            )
            err_before = abs(est_before2 - S_target)

            # ---------- WAY_BEFORE (m-1), if available ----------
            have_way_before = (n_died >= 2)
            if have_way_before:
                last2_idx = death_indices_this_bin[-2]
                IPD_t_way = IPD_t_before.copy()
                IPD_e_way = IPD_e_before.copy()
                # also revert the second-to-last death
                IPD_t_way[last2_idx] = maxFU
                IPD_e_way[last2_idx] = 0
                p_way = p + (n_died - 2)
                est_way = _km_survival_at(IPD_t_way, IPD_e_way, t_i)
                IPD_t_way2, IPD_e_way2, p_way2, est_way2, extras_way = _try_add_censors_in_bin(
                    IPD_t_way, IPD_e_way, p_way, n, S_target, t_prev, t_i,
                    bin_cens_times, match_tol, max_extra_censors_per_bin, rng, debug=debug
                )
                err_way = abs(est_way2 - S_target)

            # ---------- Choose the best branch ----------
            # Build comparison table
            candidates = [
                ("after",  err_after,  IPD_t_after2,  IPD_e_after2,  p_after2,  est_after2,  0),  # pop 0
                ("before", err_before, IPD_t_before2, IPD_e_before2, p_before2, est_before2, 1),  # pop 1
            ]
            if have_way_before:
                candidates.append(
                    ("way_before", err_way, IPD_t_way2, IPD_e_way2, p_way2, est_way2, 2)        # pop 2
                )

            # Prefer the candidate with the smallest absolute error;
            # tie-breaker: more deaths first (after > before > way_before), you can change this if you prefer.
            # So we'll sort by (error, tie_rank) where AFTER has lowest tie_rank.
            tie_rank = {"after": 0, "before": 1, "way_before": 2}
            best = min(candidates, key=lambda c: (c[1], tie_rank[c[0]]))
            best_name, best_err, best_t, best_e, best_p, best_est, pops = best

            if debug:
                msg = [f"  AFTER:  extras={extras_after},  est_S={est_after2:.6f}, err={err_after:.6f}",
                       f"  BEFORE: extras={extras_before}, est_S={est_before2:.6f}, err={err_before:.6f}"]
                if have_way_before:
                    msg.append(f"  WAY_BEFORE: extras={extras_way}, est_S={est_way2:.6f}, err={err_way:.6f}")
                print("\n".join(msg))
                print(f"  >> Chosen branch: {best_name} (pop {pops}) with err={best_err:.6f}")

            # Apply the chosen branch
            IPD_t = best_t
            IPD_e = best_e
            p = best_p
            est_curr = best_est

            # Update death bookkeeping to reflect how many last deaths were reverted
            for _ in range(pops):
                if death_indices_this_bin:
                    death_indices_this_bin.pop()
                    n_died -= 1

            reverted_last_death = (best_name != "after")

        else:
            # No deaths placed; just attempt extra censors (single branch)
            IPD_t, IPD_e, p, est_curr, _ = _try_add_censors_in_bin(
                IPD_t, IPD_e, p, n, S_target, t_prev, t_i,
                bin_cens_times, match_tol, max_extra_censors_per_bin, rng, debug=debug
            )
            reverted_last_death = False  # nothing was placed
                
    # ---- Tail censors at/after the last drop time ----
    if has_cens and p < n:
        last_drop = np.max(t) if t.size > 0 else 0.0
        tail_mask = cens >= last_drop
        tail_times = cens[tail_mask]
        if tail_times.size > 0:
            n_tail = int(min(tail_times.size, n - p))
            IPD_t[p:p + n_tail] = tail_times[:n_tail]
            IPD_e[p:p + n_tail] = 0
            p += n_tail

    return pd.DataFrame({"time": IPD_t.astype(float), "event": IPD_e.astype(int)})
