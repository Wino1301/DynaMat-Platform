"""Pulse detection and segmentation for SHPB signals.

This module provides tools for locating and extracting stress pulses from
noisy Hopkinson bar gauge traces using matched-filter (cross-correlation)
techniques.

Classes
-------
PulseDetector : Configurable pulse detection and segmentation

"""
from __future__ import annotations
from typing import Tuple, List, Dict, Sequence, Literal
import numpy as np
from scipy.signal import fftconvolve


class PulseDetector:
    """Detect and segment stress pulses in SHPB gauge signals.

    Uses matched-filter (cross-correlation) approach with a half-sine
    template to locate pulse windows, then centers and cleans the extracted
    segments.

    Parameters
    ----------
    pulse_points : int
        Nominal pulse duration in samples (Np).
    k_trials : Sequence[float], optional
        Detection thresholds to test (σ multipliers). Higher values first
        is recommended. Defaults to (6.0, 4.0, 2.0).
    polarity : {'compressive', 'tensile'}, default 'compressive'
        Sign convention for the pulse front.
    min_separation : int, optional
        Minimum allowed distance between detected peaks in samples.
        Defaults to ``0.8 * pulse_points``.

    Examples
    --------
    >>> detector = PulseDetector(
    ...     pulse_points=15000,
    ...     k_trials=(5000, 2000, 1000),
    ...     polarity="compressive"
    ... )
    >>> window = detector.find_window(signal, lower_bound=10000)
    >>> segment = detector.segment_and_center(signal, window, n_points=25000)
    """

    def __init__(
        self,
        pulse_points: int,
        k_trials: Sequence[float] = (6.0, 4.0, 2.0),
        polarity: Literal["compressive", "tensile"] = "compressive",
        min_separation: int | None = None
    ):
        self.pulse_points = pulse_points
        self.k_trials = k_trials
        self.polarity = polarity
        self.min_separation = min_separation or int(0.8 * pulse_points)

        # Build template once
        self._template = self._build_half_sine_template(pulse_points, polarity)

    @staticmethod
    def _build_half_sine_template(
        n_points: int,
        polarity: Literal["compressive", "tensile"]
    ) -> np.ndarray:
        """Build a unit-energy half-sine template.

        Parameters
        ----------
        n_points : int
            Template length in samples.
        polarity : {'compressive', 'tensile'}
            Sign convention (compressive = negative front).

        Returns
        -------
        np.ndarray
            Unit L2-norm half-sine template.
        """
        t = np.linspace(-np.pi * 0.2, np.pi * 0.8, n_points, endpoint=False)
        h = np.sin(t)
        if polarity == "compressive":
            h = -h
        return h / np.linalg.norm(h)  # unit energy

    def _matched_filter(
        self,
        signal: np.ndarray,
        k_sigma: float,
        debug: bool = False
    ) -> List[Tuple[int, int]]:
        """Run matched-filter detector for a single k_sigma threshold.

        Parameters
        ----------
        signal : np.ndarray
            Raw gauge trace (1D).
        k_sigma : float
            Detection threshold (multiples of noise std).
        debug : bool
            Print diagnostics.

        Returns
        -------
        List[Tuple[int, int]]
            Detected pulse windows as (start_idx, end_idx).
        """
        # Correlate with template
        corr = fftconvolve(signal, self._template[::-1], mode="same")

        # Noise estimate from first 10% of signal
        sigma = np.std(corr[:max(1, len(corr) // 10)])
        thr = k_sigma * sigma
        peaks = np.where(corr > thr)[0]

        if debug:
            print(f"[matched] σ={sigma:.2e} thr={thr:.2e} peaks={len(peaks)}")

        if peaks.size == 0:
            return []

        # Keep isolated peaks only
        peaks = np.sort(peaks)
        selected = [peaks[0]]
        for p in peaks[1:]:
            if p - selected[-1] >= self.min_separation:
                selected.append(p)

        # Convert peaks to windows
        windows = []
        for pk in selected:
            start = max(0, int(pk - self.pulse_points // 2))
            end = min(len(signal), int(pk + self.pulse_points // 2))
            windows.append((start, end))
            if debug:
                print(f"  window: pk={pk} idx=({start},{end}) len={end-start}")

        return windows

    def find_window(
        self,
        signal: np.ndarray,
        lower_bound: int | None = None,
        upper_bound: int | None = None,
        metric: Literal["median", "peak"] = "median",
        debug: bool = False
    ) -> Tuple[int, int]:
        """Detect the best pulse window in the signal.

        Tries all k_sigma thresholds and selects the window with highest
        amplitude (measured by metric) within the specified bounds.

        Parameters
        ----------
        signal : np.ndarray
            Full gauge trace (1D).
        lower_bound : int, optional
            Discard windows starting before this index.
        upper_bound : int, optional
            Discard windows ending after this index.
        metric : {'median', 'peak'}, default 'median'
            Amplitude measure for selection.
        debug : bool
            Print diagnostics.

        Returns
        -------
        Tuple[int, int]
            Best (start_idx, end_idx) window.

        Raises
        ------
        RuntimeError
            If no valid window is found.
        """
        windows_by_k: Dict[float, List[Tuple[int, int]]] = {}

        # Run detector for all k_sigma values
        for k in self.k_trials:
            if debug:
                print(f"\n[find_window] k_sigma = {k}")
            win_list = self._matched_filter(signal, k, debug=debug)
            windows_by_k[k] = win_list
            if debug:
                print(f"  → {len(win_list)} window(s)")

        # Select best window across all thresholds
        best_win = None
        best_val = -np.inf

        for wlist in windows_by_k.values():
            for s, e in wlist:
                # Apply bounds filter
                if lower_bound is not None and s < lower_bound:
                    continue
                if upper_bound is not None and e > upper_bound:
                    continue

                # Measure amplitude
                seg = signal[s:e]
                val = (
                    np.max(np.abs(seg)) if metric == "peak"
                    else np.median(np.abs(seg))
                )

                if val > best_val:
                    best_val = val
                    best_win = (s, e)

        if best_win is None:
            raise RuntimeError("No pulse window found within bounds")

        if debug:
            bounds_str = (
                f" (bounds [{lower_bound},{upper_bound}])"
                if lower_bound is not None else ""
            )
            print(
                f"[window] selected idx={best_win} "
                f"{metric}={best_val:.4e}{bounds_str}"
            )

        return best_win

    def segment_and_center(
        self,
        signal: np.ndarray,
        window: Tuple[int, int],
        n_points: int,
        polarity: Literal["compressive", "tensile"] | None = None,
        thresh_ratio: float = 0.01,
        debug: bool = False
    ) -> np.ndarray:
        """Expand window, center on energy median, and clean noise.

        Takes a detected pulse window and:
        1. Expands to n_points with padding
        2. Centers on energy-weighted median
        3. Suppresses low-amplitude and opposite-sign noise

        Parameters
        ----------
        signal : np.ndarray
            Full raw trace.
        window : Tuple[int, int]
            (start_idx, end_idx) from pulse detector.
        n_points : int
            Desired output length.
        polarity : {'compressive', 'tensile'}, optional
            Override class polarity for this segment.
        thresh_ratio : float, default 0.01
            Zero samples with |ε| < thresh_ratio * max(|ε|).
        debug : bool
            Print shift information.

        Returns
        -------
        np.ndarray
            Length n_points pulse segment, centered and cleaned.
        """
        if polarity is None:
            polarity = self.polarity

        i0, i1 = window
        L = i1 - i0
        half_pad = max(0, (n_points - L) // 2)

        # 1. Enlarge window with context
        start = max(0, i0 - half_pad)
        end = start + n_points
        seg = signal[start:end]

        # Pad right if too short
        if len(seg) < n_points:
            seg = np.pad(seg, (0, n_points - len(seg)))

        # 2. Center on energy median
        idx = np.arange(len(seg))
        energy = seg ** 2
        c = int(np.round(np.sum(idx * energy) / np.sum(energy)))
        shift = (n_points // 2) - c
        seg = np.roll(seg, shift)

        if debug:
            print(f"[segment_and_center] shift = {shift:+d} points")

        # 3. Noise suppression
        mag_max = np.max(np.abs(seg))

        # Auto-detect polarity if needed
        if polarity is None:
            polarity = (
                "compressive" if seg[np.argmax(np.abs(seg))] < 0
                else "tensile"
            )

        # Amplitude mask
        mask = np.abs(seg) >= thresh_ratio * mag_max

        # Sign mask
        mask &= seg < 0 if polarity == "compressive" else seg > 0

        seg = seg * mask

        return seg[:n_points]  # ensure exact length

    def calculate_rise_time(
        self,
        pulse: np.ndarray,
        time: np.ndarray,
        low_pct: float = 0.10,
        high_pct: float = 0.85
    ) -> float:
        """Calculate pulse rise time between percentage thresholds.

        Measures the time interval between the pulse crossing the low and high
        percentage thresholds of its peak value.

        Parameters
        ----------
        pulse : np.ndarray
            Pulse signal (1D).
        time : np.ndarray
            Time array corresponding to pulse (same length).
        low_pct : float, default 0.10
            Lower threshold as fraction of peak (e.g., 0.10 for 10%).
        high_pct : float, default 0.85
            Upper threshold as fraction of peak (e.g., 0.85 for 85%).

        Returns
        -------
        float
            Rise time in same units as time array.

        Raises
        ------
        ValueError
            If pulse doesn't cross both thresholds.

        Examples
        --------
        >>> detector = PulseDetector(pulse_points=15000)
        >>> rise_time = detector.calculate_rise_time(pulse, time)
        """
        # Normalize to max absolute peak (positive or negative)
        peak_val = (
            np.min(pulse) if np.abs(np.min(pulse)) > np.max(pulse)
            else np.max(pulse)
        )

        val_low = low_pct * peak_val
        val_high = high_pct * peak_val

        if peak_val < 0:
            # For negative pulses (compressive)
            idx_low_arr = np.where(pulse <= val_low)[0]
            idx_high_arr = np.where(pulse <= val_high)[0]
        else:
            # For positive pulses (tensile)
            idx_low_arr = np.where(pulse >= val_low)[0]
            idx_high_arr = np.where(pulse >= val_high)[0]

        if len(idx_low_arr) == 0 or len(idx_high_arr) == 0:
            raise ValueError(
                f"Pulse does not cross {low_pct*100:.0f}% and {high_pct*100:.0f}% thresholds"
            )

        idx_low = idx_low_arr[0]
        idx_high = idx_high_arr[0]

        rise_time = time[idx_high] - time[idx_low]

        return rise_time
