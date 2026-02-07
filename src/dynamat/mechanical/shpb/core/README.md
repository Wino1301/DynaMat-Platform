# SHPB Core Module

This module provides the core signal processing pipeline for Split Hopkinson Pressure Bar (SHPB) analysis. It handles the complete workflow from raw oscilloscope signals to stress-strain curves.

## Architecture Overview

```
Raw Oscilloscope Data
        |
        v
+-------------------+     +-------------------+     +-------------------+
|   PulseDetector   | --> |   TukeyWindow     | --> |   PulseAligner    |
| (Find & Segment)  |     |  (Signal Taper)   |     |  (Equilibrium     |
|                   |     |                   |     |   Optimization)   |
+-------------------+     +-------------------+     +-------------------+
                                                            |
                                                            v
                                              +-------------------------+
                                              | StressStrainCalculator  |
                                              |  (1-wave & 3-wave)      |
                                              +-------------------------+
                                                            |
                                                            v
                                              Stress-Strain Curves +
                                              Equilibrium Metrics
```

## Module Exports

```python
from dynamat.mechanical.shpb.core import (
    PulseDetector,          # Pulse detection and segmentation
    PulseAligner,           # Multi-criteria pulse alignment
    StressStrainCalculator, # Stress-strain computation
    TukeyWindow,            # Signal tapering
)
```

---

## Classes

### PulseDetector

Detects and segments stress pulses in SHPB gauge signals using matched-filter (cross-correlation) techniques with a half-sine template.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pulse_points` | int | required | Nominal pulse duration in samples |
| `k_trials` | Sequence[float] | (6.0, 4.0, 2.0) | Detection thresholds (sigma multipliers) |
| `polarity` | 'compressive' or 'tensile' | 'compressive' | Sign convention for pulse front |
| `min_separation` | int | 0.8 * pulse_points | Minimum distance between detected peaks |

**Key Methods:**

- `find_window(signal, lower_bound, upper_bound, metric, debug)` - Detect the best pulse window
- `segment_and_center(signal, window, n_points, polarity, thresh_ratio, debug)` - Extract and center pulse segment
- `calculate_rise_time(pulse, time, low_pct, high_pct)` - Calculate pulse rise time

**Example:**

```python
from dynamat.mechanical.shpb.core import PulseDetector
import numpy as np

# Initialize detector
detector = PulseDetector(
    pulse_points=15000,
    k_trials=(5000, 2000, 1000),
    polarity="compressive"
)

# Find pulse window in incident bar signal
window = detector.find_window(
    signal=incident_trace,
    lower_bound=10000,
    upper_bound=None,
    debug=True
)
print(f"Window found: {window}")  # (start_idx, end_idx)

# Extract and center the pulse
segment = detector.segment_and_center(
    signal=incident_trace,
    window=window,
    n_points=25000,
    thresh_ratio=0.01
)
print(f"Segment length: {len(segment)}")

# Calculate rise time (10% to 85% of peak)
rise_time = detector.calculate_rise_time(
    pulse=segment,
    time=time_vector,
    low_pct=0.10,
    high_pct=0.85
)
print(f"Rise time: {rise_time:.2e} ms")
```

**Raises:**

- `RuntimeError`: If no valid pulse window is found within bounds
- `ValueError`: If pulse doesn't cross threshold percentages for rise time

---

### PulseAligner

Aligns transmitted and reflected pulses to the incident pulse using multi-criteria differential evolution optimization. Maximizes physical equilibrium between 1-wave and 3-wave analysis.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `bar_wave_speed` | float | required | Wave speed in bar (mm/ms) |
| `specimen_height` | float | required | Initial specimen height (mm) |
| `k_linear` | float | 0.35 | Fraction of steepest slope for linear region |
| `weights` | dict | {'corr': 0.3, 'u': 0.3, 'sr': 0.3, 'e': 0.1} | Fitness component weights |

**Fitness Components:**

| Key | Weight | Description |
|-----|--------|-------------|
| `corr` | 0.3 | Pearson correlation (incident vs. transmitted - reflected) |
| `u` | 0.3 | Bar displacement equilibrium (1-wave vs 2-wave RMSE) |
| `sr` | 0.3 | Strain rate equilibrium (1-wave vs 3-wave RMSE) |
| `e` | 0.1 | Strain equilibrium (1-wave vs 3-wave RMSE) |

**Example:**

```python
from dynamat.mechanical.shpb.core import PulseAligner

# Initialize aligner with bar and specimen properties
aligner = PulseAligner(
    bar_wave_speed=4953.3,    # mm/ms
    specimen_height=6.5,      # mm
    k_linear=0.35,
    weights={'corr': 0.3, 'u': 0.3, 'sr': 0.3, 'e': 0.1}
)

# Align pulses with specified search bounds
inc_aligned, trs_aligned, ref_aligned, shift_t, shift_r = aligner.align(
    incident=inc_segment,
    transmitted=trs_segment,
    reflected=ref_segment,
    time_vector=time_segment,
    search_bounds_t=(1200, 1800),   # transmitted shift range (samples)
    search_bounds_r=(-2800, -2400), # reflected shift range (samples)
    debug=True
)

print(f"Transmitted shift: {shift_t:+d} samples")
print(f"Reflected shift: {shift_r:+d} samples")
```

**Raises:**

- `ValueError`: If input arrays have different lengths

---

### StressStrainCalculator

Computes engineering and true stress-strain curves from aligned SHPB pulses using both 1-wave and 3-wave analysis methods.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `bar_area` | float | required | Bar cross-sectional area (mm^2) |
| `bar_wave_speed` | float | required | Elastic wave speed in bar (mm/ms) |
| `bar_elastic_modulus` | float | required | Bar elastic modulus (GPa) |
| `specimen_area` | float | required | Specimen cross-sectional area (mm^2) |
| `specimen_height` | float | required | Initial specimen height (mm) |
| `strain_scale_factor` | float | 1e4 | Scale factor for input strain signals |
| `use_voltage_input` | bool | False | If True, convert voltage to strain first |
| `incident_reflected_gauge_params` | dict | None | Gauge params for voltage conversion |
| `transmitted_gauge_params` | dict | None | Gauge params for voltage conversion |

**Output Dictionary Keys:**

| Key | Description | Unit |
|-----|-------------|------|
| `time` | Time vector | ms |
| `incident` | Normalized incident pulse | dimensionless |
| `transmitted` | Normalized transmitted pulse | dimensionless |
| `reflected` | Normalized reflected pulse | dimensionless |
| `bar_displacement_1w`, `_3w` | Bar displacement | mm |
| `bar_force_1w`, `_3w` | Bar force | N |
| `strain_rate_1w`, `_3w` | Engineering strain rate | 1/s |
| `strain_1w`, `_3w` | Engineering strain | dimensionless |
| `stress_1w`, `_3w` | Engineering stress | MPa |
| `true_strain_rate_1w`, `_3w` | True strain rate | 1/s |
| `true_strain_1w`, `_3w` | True strain | dimensionless |
| `true_stress_1w`, `_3w` | True stress | MPa |

**Example:**

```python
from dynamat.mechanical.shpb.core import StressStrainCalculator

# Initialize calculator with bar and specimen properties
calculator = StressStrainCalculator(
    bar_area=283.53,           # mm^2
    bar_wave_speed=4953.3,     # mm/ms
    bar_elastic_modulus=199.99,# GPa
    specimen_area=126.68,      # mm^2
    specimen_height=6.5,       # mm
    strain_scale_factor=1e4    # input strains scaled by 10000
)

# Calculate stress-strain curves
results = calculator.calculate(
    incident=inc_aligned,
    transmitted=trs_aligned,
    reflected=ref_aligned,
    time_vector=time_vector
)

# Access 1-wave and 3-wave results
stress_1w = results['stress_1w']
strain_1w = results['strain_1w']
stress_3w = results['stress_3w']
strain_3w = results['strain_3w']

# Plot comparison
import matplotlib.pyplot as plt
plt.plot(strain_1w, stress_1w, label='1-wave')
plt.plot(strain_3w, stress_3w, label='3-wave')
plt.xlabel('Engineering Strain')
plt.ylabel('Engineering Stress (MPa)')
plt.legend()
plt.show()
```

**Using Voltage Input:**

```python
# For raw voltage data from oscilloscope
calculator = StressStrainCalculator(
    bar_area=283.53,
    bar_wave_speed=4953.3,
    bar_elastic_modulus=199.99,
    specimen_area=126.68,
    specimen_height=6.5,
    use_voltage_input=True,
    incident_reflected_gauge_params={
        'gauge_res': 350,         # ohms
        'gauge_factor': 2.1,      # dimensionless
        'cal_voltage': 5.0,       # volts
        'cal_resistance': 100000  # ohms
    },
    transmitted_gauge_params={
        'gauge_res': 350,
        'gauge_factor': 2.1,
        'cal_voltage': 5.0,
        'cal_resistance': 100000
    }
)

# Now pass voltage arrays directly
results = calculator.calculate(inc_voltage, trs_voltage, ref_voltage, time)
```

**Equilibrium Metrics:**

```python
# Calculate equilibrium quality metrics
metrics = calculator.calculate_equilibrium_metrics(results)

print(f"Force Balance Coefficient (FBC): {metrics['FBC']:.3f}")
print(f"Stress Equilibrium Quality Index (SEQI): {metrics['SEQI']:.3f}")
print(f"Stress Oscillation Index (SOI): {metrics['SOI']:.3f}")
print(f"Dynamic Stress Uniformity Factor (DSUF): {metrics['DSUF']:.3f}")

# Windowed metrics by loading phase
print(f"Loading phase R^2: {metrics['windowed_DSUF_loading']:.3f}")
print(f"Plateau phase R^2: {metrics['windowed_DSUF_plateau']:.3f}")
```

**Raises:**

- `ValueError`: If input arrays have different lengths
- `ValueError`: If voltage input enabled but gauge parameters missing

---

### TukeyWindow

Generates Tukey (tapered cosine) windows for signal processing. Useful for reducing edge effects in frequency-domain operations and preparing signals for machine learning.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `alpha` | float | 0.5 | Taper fraction in [0, 1] |

**Alpha Values:**

| Value | Window Type | Use Case |
|-------|-------------|----------|
| 0.0 | Rectangular | No tapering (raw signal) |
| 0.5 | Half-tapered | Recommended for SHPB |
| 1.0 | Hann window | Full tapering |

**Example:**

```python
from dynamat.mechanical.shpb.core import TukeyWindow
import numpy as np

# Create window generator
tukey = TukeyWindow(alpha=0.5)

# Generate window weights
weights = tukey.generate(length=10000)
print(f"Window shape: {weights.shape}")

# Apply to signal (method 1)
tapered_signal = signal * weights

# Apply to signal (method 2 - convenience method)
tapered_signal = tukey.apply(signal)

# Compare different alpha values
windows = TukeyWindow.compare_alphas(
    length=1000,
    alphas=[0.0, 0.25, 0.5, 0.75, 1.0]
)

# Visualize
import matplotlib.pyplot as plt
for alpha, window in windows.items():
    plt.plot(window, label=f'alpha={alpha}')
plt.xlabel('Sample')
plt.ylabel('Window weight')
plt.legend()
plt.show()
```

**Raises:**

- `ValueError`: If alpha not in [0, 1]
- `ValueError`: If length not positive

---

## Equilibrium Metrics Reference

The `StressStrainCalculator.calculate_equilibrium_metrics()` method returns several quality metrics:

| Metric | Range | Good Value | Description |
|--------|-------|------------|-------------|
| FBC | 0-1 | > 0.95 | Force Balance Coefficient |
| SEQI | 0-1 | > 0.90 | Stress Equilibrium Quality Index |
| SOI | 0+ | < 0.05 | Stress Oscillation Index (lower is better) |
| DSUF | 0-1 | > 0.98 | Dynamic Stress Uniformity Factor (R^2) |

**Windowed Metrics** (by loading phase):
- `windowed_FBC_loading`, `windowed_DSUF_loading`: During 0-50% peak stress
- `windowed_FBC_plateau`, `windowed_DSUF_plateau`: During 50-100% peak stress
- `windowed_FBC_unloading`, `windowed_DSUF_unloading`: After peak stress

---

## Typical Workflow

```python
import numpy as np
from dynamat.mechanical.shpb.core import (
    PulseDetector,
    PulseAligner,
    StressStrainCalculator,
    TukeyWindow
)

# 1. Load raw oscilloscope data
time = np.load('time.npy')
incident_raw = np.load('incident.npy')
transmitted_raw = np.load('transmitted.npy')

# 2. Configure pulse detector
detector = PulseDetector(
    pulse_points=15000,
    k_trials=(5000, 2000, 1000),
    polarity="compressive"
)

# 3. Detect and extract pulses
inc_window = detector.find_window(incident_raw, lower_bound=10000)
trs_window = detector.find_window(transmitted_raw, lower_bound=50000)

inc_segment = detector.segment_and_center(incident_raw, inc_window, n_points=25000)
trs_segment = detector.segment_and_center(transmitted_raw, trs_window, n_points=25000)

# Calculate reflected = incident (inverted) from gauge trace
ref_segment = -inc_segment  # Simplified; actual extraction varies

# 4. Optional: Apply Tukey window for smoothing
tukey = TukeyWindow(alpha=0.3)
inc_segment = tukey.apply(inc_segment)
trs_segment = tukey.apply(trs_segment)

# 5. Align pulses
aligner = PulseAligner(
    bar_wave_speed=4953.3,
    specimen_height=6.5
)

inc_aligned, trs_aligned, ref_aligned, shift_t, shift_r = aligner.align(
    incident=inc_segment,
    transmitted=trs_segment,
    reflected=ref_segment,
    time_vector=time[:25000],
    search_bounds_t=(1200, 1800),
    search_bounds_r=(-2800, -2400)
)

# 6. Calculate stress-strain
calculator = StressStrainCalculator(
    bar_area=283.53,
    bar_wave_speed=4953.3,
    bar_elastic_modulus=199.99,
    specimen_area=126.68,
    specimen_height=6.5
)

results = calculator.calculate(inc_aligned, trs_aligned, ref_aligned, time[:25000])

# 7. Assess equilibrium quality
metrics = calculator.calculate_equilibrium_metrics(results)

print(f"Test quality: FBC={metrics['FBC']:.3f}, DSUF={metrics['DSUF']:.3f}")

if metrics['FBC'] > 0.95 and metrics['DSUF'] > 0.98:
    print("Excellent equilibrium achieved!")
elif metrics['FBC'] > 0.85:
    print("Acceptable equilibrium, review data carefully")
else:
    print("Poor equilibrium, consider re-testing")
```

---

## Logging Configuration

All classes use Python's standard logging module. Enable debug output:

```python
import logging

# Enable debug logging for the core module
logging.getLogger('dynamat.mechanical.shpb.core').setLevel(logging.DEBUG)

# Or enable globally
logging.basicConfig(level=logging.DEBUG)
```

Debug messages include:
- Pulse detection thresholds and peaks found
- Window selection criteria and bounds
- Alignment optimization progress
- Shift amounts and fitness scores

---

## References

1. Gray, G. T. (2000). Classic Split-Hopkinson Pressure Bar Testing.
   ASM Handbook, Vol. 8: Mechanical Testing and Evaluation.

2. Kolsky, H. (1949). An Investigation of the Mechanical Properties of
   Materials at very High Rates of Loading. Proceedings of the Physical
   Society. Section B, 62(11), 676.

3. Chen, W. W., & Song, B. (2011). Split Hopkinson (Kolsky) Bar: Design,
   Testing and Applications. Springer.

4. Harris, F. J. (1978). On the use of windows for harmonic analysis with
   the discrete Fourier transform. Proceedings of the IEEE, 66(1), 51-83.

5. Follansbee, P. S., & Frantz, C. (1983). Wave propagation in the
   split Hopkinson pressure bar. Journal of Engineering Materials
   and Technology, 105(1), 61-66.
