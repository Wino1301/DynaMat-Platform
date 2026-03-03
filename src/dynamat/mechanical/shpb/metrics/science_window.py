"""Science window computation: 30%-85% peak stress window.

The science window defines the regime where SHPB data is most informative
for constitutive model calibration. Below 30% is the loading ramp (non-equilibrium).
Above 85% is rapid unloading (wave mechanics, not material behavior).
"""

import numpy as np

from .dataclasses import ScienceWindow


def compute_science_window(
    stress: np.ndarray,
    pulse_start_idx: int,
    pulse_end_idx: int,
    low_fraction: float = 0.30,
    high_fraction: float = 0.85,
) -> ScienceWindow | None:
    """Compute the 30%-85% peak stress science window.

    Args:
        stress: Stress array (1-wave or 3-wave).
        pulse_start_idx: Start index of detected pulse.
        pulse_end_idx: End index of detected pulse.
        low_fraction: Lower stress threshold as fraction of peak (default 0.30).
        high_fraction: Upper stress threshold as fraction of peak (default 0.85).

    Returns:
        ScienceWindow or None if window cannot be determined.
    """
    if stress is None or len(stress) == 0:
        return None

    # Work within pulse boundaries
    end_idx = min(pulse_end_idx, len(stress))
    start_idx = max(pulse_start_idx, 0)
    pulse_stress = np.abs(stress[start_idx:end_idx])

    if len(pulse_stress) == 0:
        return None

    peak_stress = np.max(pulse_stress)
    if peak_stress <= 0:
        return None

    low_threshold = low_fraction * peak_stress
    high_threshold = high_fraction * peak_stress

    # Find indices where stress is within the window
    above_low = pulse_stress >= low_threshold
    below_high = pulse_stress <= high_threshold
    in_window = above_low & below_high

    if not np.any(in_window):
        # Fallback: at least find the region above low threshold
        if np.any(above_low):
            in_window = above_low
        else:
            return None

    window_indices = np.where(in_window)[0]
    if len(window_indices) == 0:
        return None

    # Convert back to absolute indices
    win_start = int(window_indices[0]) + start_idx
    win_end = int(window_indices[-1]) + start_idx

    return ScienceWindow(
        start_idx=win_start,
        end_idx=win_end,
        stress_threshold_low=low_threshold,
        stress_threshold_high=high_threshold,
    )
