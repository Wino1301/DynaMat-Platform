"""Stage 1 — Signal Quality: BQI (Baseline Quality Index) and FSR (Full-Scale Range).

BQI assesses pre-trigger baseline offset and drift.
FSR assesses ADC range utilization per channel.
"""

import numpy as np

from .dataclasses import MetricValue
from . import thresholds as T


def assess_baseline_quality(
    raw_signals: dict[str, np.ndarray],
    pulse_start_idx: int,
    adc_full_scale: float | None = None,
) -> list[MetricValue]:
    """Compute BQI_offset and BQI_drift from the pre-trigger region.

    The pre-trigger region is everything before pulse_start_idx.
    If adc_full_scale is unavailable, normalize by signal peak instead.

    Returns:
        List of [BQI_offset, BQI_drift] MetricValues.
    """
    if adc_full_scale is None:
        # Skip if no ADC metadata — but try using signal range as proxy
        # Use max peak across all channels as normalization
        max_peak = 0.0
        for signal in raw_signals.values():
            if signal is not None and len(signal) > 0:
                max_peak = max(max_peak, np.max(np.abs(signal)))
        if max_peak <= 0:
            return [
                MetricValue(name="BQI_offset", value=float('nan'), unit=None,
                            assessment="Skipped", stage=1, category="SignalQuality",
                            skipped=True, skip_reason="No valid signals"),
                MetricValue(name="BQI_drift", value=float('nan'), unit=None,
                            assessment="Skipped", stage=1, category="SignalQuality",
                            skipped=True, skip_reason="No valid signals"),
            ]
        normalization = max_peak
    else:
        normalization = adc_full_scale

    # Aggregate across all channels (worst case)
    max_offset = 0.0
    max_drift = 0.0

    for name, signal in raw_signals.items():
        if signal is None or len(signal) == 0:
            continue

        pre_trigger = signal[:max(pulse_start_idx, 100)]
        if len(pre_trigger) < 10:
            continue

        # Offset: |mean(pre-trigger)| / normalization
        offset = abs(np.mean(pre_trigger)) / normalization
        max_offset = max(max_offset, offset)

        # Drift: |slope * T_pulse| / normalization
        x = np.arange(len(pre_trigger))
        if len(x) > 1:
            slope = np.polyfit(x, pre_trigger, 1)[0]
            # Extrapolate drift over estimated pulse duration
            pulse_duration_samples = max(10000, pulse_start_idx)
            drift = abs(slope * pulse_duration_samples) / normalization
            max_drift = max(max_drift, drift)

    # Assess
    offset_assessment = "Good" if max_offset < T.BQI_GOOD else (
        "Acceptable" if max_offset < T.BQI_ACCEPTABLE else "BaselineProblem")
    drift_assessment = "Good" if max_drift < T.BQI_GOOD else (
        "Acceptable" if max_drift < T.BQI_ACCEPTABLE else "DriftProblem")

    return [
        MetricValue(name="BQI_offset", value=max_offset, unit=None,
                    assessment=offset_assessment, stage=1, category="SignalQuality"),
        MetricValue(name="BQI_drift", value=max_drift, unit=None,
                    assessment=drift_assessment, stage=1, category="SignalQuality"),
    ]


def assess_range_utilization(
    raw_signals: dict[str, np.ndarray],
    adc_full_scale: float | None = None,
) -> list[MetricValue]:
    """Compute FSR (Full-Scale Range utilization) per channel.

    FSR_i = max(|V_i|) / V_full_scale

    Returns:
        List of FSR MetricValues (one per channel: inc, ref, trs).
    """
    if adc_full_scale is None:
        # Cannot compute FSR without ADC metadata
        results = []
        for suffix in ['inc', 'ref', 'trs']:
            results.append(MetricValue(
                name=f"FSR_{suffix}", value=float('nan'), unit=None,
                assessment="Skipped", stage=1, category="SignalQuality",
                skipped=True, skip_reason="ADC full-scale range unavailable",
            ))
        return results

    channel_map = {'incident': 'inc', 'reflected': 'ref', 'transmitted': 'trs'}
    results = []

    for channel_name, suffix in channel_map.items():
        signal = raw_signals.get(channel_name)
        if signal is None or len(signal) == 0:
            results.append(MetricValue(
                name=f"FSR_{suffix}", value=float('nan'), unit=None,
                assessment="Skipped", stage=1, category="SignalQuality",
                skipped=True, skip_reason=f"No {channel_name} signal",
            ))
            continue

        fsr = np.max(np.abs(signal)) / (adc_full_scale / 2)

        if fsr > 0.95:
            assessment = "NearClipping"
        elif fsr > 0.5:
            assessment = "GoodUtilization"
        elif fsr > 0.2:
            assessment = "LowUtilization"
        else:
            assessment = "VeryLowUtilization"

        results.append(MetricValue(
            name=f"FSR_{suffix}", value=fsr, unit=None,
            assessment=assessment, stage=1, category="SignalQuality",
        ))

    return results
