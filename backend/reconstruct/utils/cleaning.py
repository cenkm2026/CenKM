import numpy as np

def clean_curve(t_raw, S_raw):
    # Purpose: Clean digitized KM curve by sorting, deduplicating, and enforcing monotonicity.
    # Inputs:
    # - t_raw (array-like): Raw time values.
    # - S_raw (array-like): Raw survival values.
    # Outputs:
    # - tuple[np.ndarray, np.ndarray]: (t_drop, S_drop) cleaned time and survival arrays.
    """
    Clean digitized KM curve into t_drop and S_drop:
    - sort by time
    - remove duplicates
    - enforce monotonic decreasing survival
    """
    # sort
    order = np.argsort(t_raw)
    t_sorted = t_raw[order]
    S_sorted = S_raw[order]

    # remove duplicate times
    t_unique, idx = np.unique(t_sorted, return_index=True)
    t_drop = t_sorted[idx]
    S_drop = S_sorted[idx]

    # enforce non-increasing survival
    S_drop = np.maximum.accumulate(S_drop[::-1])[::-1]

    return t_drop, S_drop
