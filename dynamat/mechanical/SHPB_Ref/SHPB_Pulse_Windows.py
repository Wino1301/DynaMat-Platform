"""SHPB_Pulse_Windows.py
A collection of pulse‑detection helpers for SHPB preprocessing.

Functions
---------
half_sine_template        – build a unit‑energy half sine.
matched_pulses            – matched‑filter detector for one kσ.
find_pulse_window         – test *all* kσ, return window with max |amp|.
segment_and_center_pulse  – expand window, centre on energy, mask noise.
"""
from __future__ import annotations

from typing import List, Tuple, Dict, Sequence
import numpy as np
from scipy.signal import fftconvolve

__all__ = [
    "half_sine_template",
    "matched_pulses",
    "find_incident_window",
    "segment_and_center_pulse",
    "find_pulse_window",
]

# -----------------------------------------------------------------------------
# Helper
# -----------------------------------------------------------------------------

def _amp(metric: str, sig: np.ndarray) -> float:
    """Return amplitude measure selected by *metric*."""
    if metric == "peak":
        return float(np.max(np.abs(sig)))
    if metric == "median":
        return float(np.median(np.abs(sig)))
    raise ValueError(f"unknown metric '{metric}' – use 'peak' or 'median'")

# -----------------------------------------------------------------------------
# 1. Template & single‑threshold detector
# -----------------------------------------------------------------------------

def half_sine_template(n_points: int, polarity: str = "compressive"):
    """Return a length-n half-sine with unit energy."""
    t = np.linspace(-np.pi*0.2, np.pi*0.8, n_points, endpoint=False)
    h = np.sin(t)
    if polarity == "compressive":   # negative front
        h = -h
    return h / np.linalg.norm(h)    # unit L2 norm

def matched_pulses(sig_raw: np.ndarray,
                          pulse_points: int,
                          k_sigma: float = 6.0,
                          min_separation: int | None = None,
                          polarity: str = "compressive",
                          debug: bool = False):
    """
    Locate stress-pulse windows in a noisy Hopkinson-bar gauge trace using a
    matched-filter (cross-correlation) approach.

    The function constructs a half-sine template of length *pulse_points*
    (Np) and correlates it with the raw signal.  Peaks in the correlation
    that exceed *k_sigma* standard deviations of the pre-pulse noise are
    taken as pulse centres.  For each accepted peak *p*, the pulse window
    is defined as::

        start = p - Np // 2
        end   = p + Np // 2

    Peaks closer than *min_separation* samples are considered duplicates
    and only the first is kept.

    Parameters
    ----------
    sig_raw : np.ndarray
        One-dimensional voltage / strain series (incident or transmitted gauge).
    pulse_points : int
        Nominal pulse duration in samples (Np).
    k_sigma : float, default 6.0
        Detection threshold expressed as multiples of the correlation
        noise standard deviation σ.  Typical values: 5 – 7.
    min_separation : int, optional
        Minimum allowed distance (in samples) between two accepted peaks.
        Defaults to ``int(0.8 * pulse_points)``.
    polarity : {'compressive', 'tensile'}, default 'compressive'
        Sign convention for the pulse front.  For a compressive half-sine
        the template is negative; for a tensile pulse it is positive.
    debug : bool, default False
        If *True*, prints σ, threshold, number of candidate peaks, and the
        final window indices.

    Returns
    -------
    list[tuple[int, int]]
        Sorted list of ``(start_idx, end_idx)`` tuples delimiting each
        detected pulse window.  Indices are clipped to the valid range
        ``0 ≤ idx < len(sig_raw)``.

    Notes
    -----
    * Cross-correlation is computed with `scipy.signal.fftconvolve`
      (``mode='same'``) for O(*N* log *N*) complexity.
    * Baseline drift and low-frequency electrical hum do **not** affect
      detection, because the correlation template has zero mean.
    * For multi-pulse shots (incident + reflected) simply inspect
      ``windows[0]`` and ``windows[-1]`` after sorting.

    References
    ----------
    Dai, F., Xia, K., & Chen, R. (2015). *Dynamic behaviour of materials
    with Hopkinson techniques*. IJIE, 76, 192-204.
    """
    
    if min_separation is None:
        min_separation = int(0.8 * pulse_points)

    # build template
    h = half_sine_template(pulse_points, polarity=polarity)

    # fast correlation (same length as signal)
    corr = fftconvolve(sig_raw, h[::-1], mode="same")

    # threshold on correlation amplitude
    sigma = np.std(corr[:max(1, len(corr)//10)])   # noise estimate
    thr   = k_sigma * sigma
    peaks = np.where(corr > thr)[0]

    if debug:
        print(f"[matched] σ={sigma:.2e} thr={thr:.2e}  peaks={len(peaks)}")

    if peaks.size == 0:
        return []

    # keep only isolated peaks
    peaks = np.sort(peaks)
    selected = [peaks[0]]
    for p in peaks[1:]:
        if p - selected[-1] >= min_separation:
            selected.append(p)

    windows = []
    for pk in selected:
        start = max(0, int(pk - pulse_points//2))
        end   = min(len(sig_raw), int(pk + pulse_points//2))
        windows.append((start, end))
        if debug:
            print(f"  window: pk={pk}  idx=({start},{end})  len={end-start}")

    return windows

    from scripts.matched_pulses import matched_pulses

# -----------------------------------------------------------------------------
# 2. Multi‑threshold detector that returns *best* window
# -----------------------------------------------------------------------------

def find_pulse_window(
    signal: np.ndarray,
    pulse_points: int,
    k_trials: Sequence[float],
    polarity: str = "compressive",
    min_separation: int | None = None,
    lower_bound: int | None = None,
    upper_bound: int | None = None,
    metric: str = "median",
    return_all: bool = False,
    debug: bool = False,
) -> Tuple[int, int]:
    """Detect candidate windows for every *k_sigma* and select one.

    Parameters
    ----------
    signal : 1‑D ndarray
        Full gauge trace.
    pulse_points : int
        Nominal half‑sine width (Np).
    k_trials : list(float)
        Thresholds (*σ* multipliers) to test – highest value first is
        recommended.
    polarity : {'compressive','tensile'}
        Sign of the main pulse front.
    min_separation : int, optional
        Minimum distance between two detected peaks.  Defaults to
        ``0.8 * pulse_points``.
    lower_bound, upper_bound : int, optional
        Hard window boundaries.  Candidates whose *start* falls before
        ``lower_bound`` or whose *end* exceeds ``upper_bound`` are discarded.
    metric : {'median','peak'}
        Amplitude measure for choosing *best* window.
    return_all : bool, default False
        If *True*, the full ``{k: [(s,e), …]}`` dictionary is returned
        instead of a single window.
    debug : bool
        Verbose diagnostics.

    Returns
    -------
    (start, end)            – if *return_all* is False  (default)
    dict[float, list[win]]  – if *return_all* is True
    """
    if min_separation is None:
        min_separation = int(0.8 * pulse_points)

    windows_by_k: Dict[float, List[Tuple[int, int]]] = {}

    # ------------------------------------------------------------------
    # 1) Run matched‑filter detector for every k_sigma
    # ------------------------------------------------------------------
    for k in k_trials:
        if debug:
            print(f"\n[find_pulse_window] k_sigma = {k}")
        win_list = matched_pulses(
            sig_raw        = signal,
            pulse_points   = pulse_points,
            k_sigma        = k,
            min_separation = min_separation,
            polarity       = polarity,
            debug          = debug,
        )
        windows_by_k[k] = win_list
        if debug:
            print(f"  → {len(win_list)} window(s)")

    if return_all:
        return windows_by_k

    # ------------------------------------------------------------------
    # 2) Select the best window among *all* thresholds
    # ------------------------------------------------------------------
    best_win: Tuple[int, int] | None = None
    best_val: float = -np.inf

    for wlist in windows_by_k.values():
        for s, e in wlist:
            # bounds filter
            if lower_bound is not None and s < lower_bound:
                continue
            if upper_bound is not None and e > upper_bound:
                continue
            val = _amp(metric, signal[s:e])
            if val > best_val:
                best_val = val
                best_win = (s, e)

    if best_win is None:
        raise RuntimeError("No pulse window satisfied selection criteria.")

    if debug:
        print(
            f"[window] selected idx={best_win}  {metric}={best_val:.4e}" +
            (f"  (bounds [{lower_bound},{upper_bound}])" if lower_bound is not None else "")
        )
    return best_win

# -----------------------------------------------------------------------------
# 3. Segment, centre, mask helpers
# -----------------------------------------------------------------------------
def segment_and_center_pulse(
        signal: np.ndarray,
        win: tuple[int, int],
        n_points: int,
        polarity: str = "compressive",
        thresh_ratio: float = 0.01,
        debug: bool = False
                            ) -> np.ndarray:
    """
    Expand *win* to *n_points*, centre on energy-median, zero-pad, and
    suppress low-level / opposite-sign noise.

    Parameters
    ----------
    signal : np.ndarray
        Full raw trace.
    win : (int, int)
        (start_idx, end_idx) from pulse detector.
    n_points : int
        Desired output length.
    polarity : {'compressive','tensile'}, default 'compressive'
        Sign convention of the main front; used by the sign-mask.
    thresh_ratio : float, default 0.01
        Samples with |ε| < thresh_ratio·max(|ε|) are zeroed.
    debug : bool, default False
        Prints shift information.

    Returns
    -------
    np.ndarray
        Length-*n_points* pulse segment, centred and cleaned.
    """
    i0, i1 = win
    L = i1 - i0
    half_pad = max(0, (n_points - L) // 2)

    # 1. enlarge window with context ----------------------------------------
    start = max(0, i0 - half_pad)
    end   = start + n_points
    seg = signal[start:end]

    # If still shorter than n_points (ran off right edge), pad right.
    if len(seg) < n_points:
        seg = np.pad(seg, (0, n_points - len(seg)))

    # 2. centre on energy median -------------------------------------------
    idx = np.arange(len(seg))
    c   = int(np.round(np.sum(idx * seg**2) / np.sum(seg**2)))
    shift = (n_points // 2) - c
    seg = np.roll(seg, shift)
    if debug:
        print(f"[segment & center] shift = {shift:+d} points")

    # 3. noise & opposite sign suppression ---------------------------------
    mag_max = np.max(np.abs(seg))
    if polarity is None:        # auto-detect dominant sign
        polarity = "compressive" if seg[np.argmax(np.abs(seg))] < 0 else "tensile"
    
    mask = np.abs(seg) >= thresh_ratio * mag_max
    mask &= seg < 0 if polarity == "compressive" else seg > 0
    seg  = seg * mask


    return seg[:n_points]  # ensure exact length






