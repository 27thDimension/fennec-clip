import numpy as np
import pandas as pd

# --- Assumptions: adjust with real flight data ---
RCIN_MANEUVER_CH = "C9"
RCIN_WORKLOAD_CH = "C10"
RCIN_TIMER_CH = "C11"

LEVEL_TOL = 25        # us: values within this of the current level count as the same level (jitter)
MIN_SAMPLES = 3       # a new level must persist this many samples to count (ignores glitches)
PULSE_DELTA = 300     # us: how far from the resting value counts as the timer switch being "on"

DEFAULT_TAG = "untagged"
MANEUVER_TAGS = ["hover", "straight-runs", "squares", "pirouettes"] # maneuver types
WORKLOAD_TAGS = ["none", "run", "vision impairment", "radio chatter", "verbal memory"]     # placeholder: your real workload conditions

# PWM level -> name. Fill these in once you know what the controller sends,
# e.g. {1100: "hover", 1300: "turn"}. Empty means "no names yet".
MANEUVER_LEVELS = {1100: "hover", 1300: "straight runs", 1500: "squares", 1700: "pirouettes"}
WORKLOAD_LEVELS = {1100: "none", 1250: "run", 1400: "vision impairment", 1550: "radio chatter", 1700: "verbal memory"}


def level_name(value, levels, tol=LEVEL_TOL):
    """Name of the nearest known level within tolerance, else None."""
    if not levels:
        return None
    nearest = min(levels, key=lambda k: abs(k - value))
    return levels[nearest] if abs(nearest - value) <= tol else None


def segment_channel(times, values, tol=LEVEL_TOL, min_samples=MIN_SAMPLES):
    """Run-length encode a discrete channel, ignoring jitter and brief glitches.
    Returns [{"start": t, "end": t, "value": v}, ...]."""
    if len(values) == 0:
        return []
    segments = []
    seg_start = float(times[0])
    current = float(values[0])
    cand_idx, cand_count = None, 0

    for i in range(1, len(values)):
        v = values[i]
        if abs(v - current) <= tol:
            cand_idx, cand_count = None, 0               # back at the current level: drop any candidate
            continue
        if cand_idx is not None and abs(v - values[cand_idx]) <= tol:
            cand_count += 1                               # still agrees with the candidate
        else:
            cand_idx, cand_count = i, 1                   # a new candidate level
        if cand_count >= min_samples:
            change_t = float(times[cand_idx])             # the change happened when the candidate FIRST appeared
            segments.append({"start": seg_start, "end": change_t, "value": round(current)})
            seg_start, current = change_t, float(values[cand_idx])
            cand_idx, cand_count = None, 0

    segments.append({"start": seg_start, "end": float(times[-1]), "value": round(current)})
    return segments


def pulse_events(times, values, delta=PULSE_DELTA):
    """Times where a momentary switch goes from its resting value to 'on'."""
    if len(values) == 0:
        return []
    resting = float(np.median(values))                    # the switch is off most of the time
    active = np.abs(values - resting) > delta
    previous = np.concatenate(([False], active[:-1]))
    rising = active & ~previous                           # start of each excursion
    return [float(t) for t in times[rising]]


def build_rcin_payload(rcin_df):
    """Turn a full-rate RCIN DataFrame into the compact summary the frontend needs."""
    empty = {
        "maneuver_segments": [],
        "workload_segments": [],
        "timer_events": [],
        "present": {"maneuver": False, "workload": False, "timer": False},
    }
    needed = ["Unix_Epoch_Time", RCIN_MANEUVER_CH, RCIN_WORKLOAD_CH, RCIN_TIMER_CH]
    if not isinstance(rcin_df, pd.DataFrame) or rcin_df.empty:
        return empty
    if any(c not in rcin_df.columns for c in needed):
        return empty

    df = rcin_df[needed].dropna().sort_values("Unix_Epoch_Time")
    t = df["Unix_Epoch_Time"].to_numpy(dtype=float)

    maneuver = segment_channel(t, df[RCIN_MANEUVER_CH].to_numpy(dtype=float))
    workload = segment_channel(t, df[RCIN_WORKLOAD_CH].to_numpy(dtype=float))
    for seg in maneuver:
        seg["name"] = level_name(seg["value"], MANEUVER_LEVELS)
    for seg in workload:
        seg["name"] = level_name(seg["value"], WORKLOAD_LEVELS)
    timer = pulse_events(t, df[RCIN_TIMER_CH].to_numpy(dtype=float))

    return {
        "maneuver_segments": maneuver,
        "workload_segments": workload,
        "timer_events": timer,
        # a channel that never changes means "not transmitted" (or never touched)
        "present": {
            "maneuver": len(maneuver) > 1,
            "workload": len(workload) > 1,
            "timer": len(timer) > 0,
        },
    }