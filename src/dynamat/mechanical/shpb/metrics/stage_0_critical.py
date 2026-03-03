"""Stage 0 — Critical Pre-Check: SCD (Signal Clipping) and PSC (Pulse Separation).

If SCD > 0 or PSC < 1.0, set critical_failure=True and skip signal-derived stages.
"""

import numpy as np

from .dataclasses import MetricValue
from . import thresholds as T


def detect_clipping(
    raw_signals: dict[str, np.ndarray],
    adc_full_scale: float | None = None,
    adc_bits: int | None = None,
    consecutive_threshold: int = 4,
) -> MetricValue:
    """Detect ADC clipping in raw signals.

    Checks each channel for consecutive samples at the ADC rail.
    If adc_full_scale/adc_bits are unavailable, checks for consecutive
    identical extreme values as a heuristic.

    Returns:
        MetricValue for SCD (count of clipped channels).
    """
    if adc_full_scale is None or adc_bits is None:
        # Without ADC metadata, use heuristic: check for runs of identical
        # values at the extremes (top/bottom 0.1% of signal range)
        clipped_channels = 0
        clipped_names = []
        for name, signal in raw_signals.items():
            if signal is None or len(signal) == 0:
                continue
            sig_range = np.ptp(signal)
            if sig_range == 0:
                continue
            threshold = 0.001 * sig_range
            # Check top rail
            top_val = np.max(signal)
            top_mask = np.abs(signal - top_val) < threshold
            if _has_consecutive_run(top_mask, consecutive_threshold):
                clipped_channels += 1
                clipped_names.append(name)
                continue
            # Check bottom rail
            bot_val = np.min(signal)
            bot_mask = np.abs(signal - bot_val) < threshold
            if _has_consecutive_run(bot_mask, consecutive_threshold):
                clipped_channels += 1
                clipped_names.append(name)

        return MetricValue(
            name="SCD",
            value=float(clipped_channels),
            unit=None,
            assessment="CriticalFail" if clipped_channels > 0 else "NoClipping",
            stage=0,
            category="SignalQuality",
            context={"clipped_channels": clipped_names} if clipped_names else None,
            skipped=False,
        )

    # With ADC metadata, check against rails
    adc_max = adc_full_scale / 2
    adc_min = -adc_full_scale / 2
    rail_tolerance = adc_full_scale / (2 ** adc_bits)

    clipped_channels = 0
    clipped_names = []
    for name, signal in raw_signals.items():
        if signal is None or len(signal) == 0:
            continue
        near_max = np.abs(signal - adc_max) < rail_tolerance
        near_min = np.abs(signal - adc_min) < rail_tolerance
        if (_has_consecutive_run(near_max, consecutive_threshold) or
                _has_consecutive_run(near_min, consecutive_threshold)):
            clipped_channels += 1
            clipped_names.append(name)

    return MetricValue(
        name="SCD",
        value=float(clipped_channels),
        unit=None,
        assessment="CriticalFail" if clipped_channels > 0 else "NoClipping",
        stage=0,
        category="SignalQuality",
        context={"clipped_channels": clipped_names} if clipped_names else None,
    )


def check_pulse_separation(
    gauge_to_specimen: float,
    bar_wave_speed: float,
    striker_length: float,
) -> MetricValue:
    """Check that incident and reflected pulses are temporally separable.

    PSC = t_separation / t_pulse where:
      t_separation = 2 * d_gauge / c_bar
      t_pulse = 2 * L_striker / c_bar  (assuming same bar material)

    Args:
        gauge_to_specimen: Distance from strain gauge to specimen (mm).
        bar_wave_speed: Bar longitudinal wave speed (m/s).
        striker_length: Striker bar length (mm).

    Returns:
        MetricValue for PSC.
    """
    if bar_wave_speed <= 0 or striker_length <= 0:
        return MetricValue(
            name="PSC", value=float('nan'), unit=None,
            assessment="Skipped", stage=0, category="SetupValidation",
            skipped=True, skip_reason="Invalid bar_wave_speed or striker_length",
        )

    # Both distances in mm, wave speed in m/s -> convert consistently
    # t = 2*d / c, but d in mm and c in m/s -> t = 2*d / (c * 1000) in seconds
    # Since ratio cancels units: PSC = d_gauge / L_striker
    psc = gauge_to_specimen / striker_length

    return MetricValue(
        name="PSC",
        value=psc,
        unit=None,
        assessment=T.assess_psc(psc),
        stage=0,
        category="SetupValidation",
    )


def _has_consecutive_run(mask: np.ndarray, threshold: int) -> bool:
    """Check if boolean mask has a run of True values >= threshold."""
    if not np.any(mask):
        return False
    # Find runs using diff
    changes = np.diff(mask.astype(int))
    starts = np.where(changes == 1)[0] + 1
    ends = np.where(changes == -1)[0] + 1
    # Handle edge cases
    if mask[0]:
        starts = np.concatenate(([0], starts))
    if mask[-1]:
        ends = np.concatenate((ends, [len(mask)]))
    if len(starts) == 0 or len(ends) == 0:
        return False
    run_lengths = ends[:len(starts)] - starts[:len(ends)]
    return np.any(run_lengths >= threshold)
