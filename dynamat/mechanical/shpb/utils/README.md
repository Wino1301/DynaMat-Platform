# SHPB Re-Analysis Utility

Utility module for re-running SHPB analysis when parameters change. Supports two modes:

1. **Analysis-only mode** (fast): Re-run stress-strain calculation using existing aligned pulses
2. **Full re-alignment mode**: Re-run from raw data with updated alignment parameters

## Quick Start

```python
from dynamat.mechanical.shpb import SHPBReanalyzer
from dynamat.ontology import OntologyManager

# Initialize
manager = OntologyManager()
reanalyzer = SHPBReanalyzer(manager)

# Load existing test
reanalyzer.load_test("user_data/specimens/DYNML-SS316A356-0050/DYNML_SS316A356_0050_SHPBTest.ttl")

# Update parameters
reanalyzer.update_bar_property('incident', 'wave_speed', 5000.0)

# Recalculate
results = reanalyzer.recalculate(mode='analysis_only')

# Save results
csv_path, ttl_path = reanalyzer.save(version_suffix="_recalibrated")
```

## When to Use Each Mode

### Analysis-Only Mode (Default)

Use when you want to see how stress-strain curves change with:
- Bar properties (wave speed, elastic modulus, cross-section)
- Specimen properties (cross-section, height)
- Gauge parameters (gauge factor, resistance)

This mode is **fast** because it uses the existing aligned pulses from the processed CSV.

```python
results = reanalyzer.recalculate(mode='analysis_only')
```

### Full Re-Alignment Mode

Use when you need to change:
- Alignment search bounds
- Linear region fraction (k_linear)
- Optimization weights
- Detection parameters

This mode is **slower** because it re-runs pulse detection and alignment from raw data.

```python
reanalyzer.update_alignment_param('search_bounds_t', (3100, 3400))
reanalyzer.update_alignment_param('k_linear', 0.40)
results = reanalyzer.recalculate(mode='full')
```

## API Reference

### Loading

```python
reanalyzer.load_test(test_uri_or_path, specimens_dir=None)
```

Loads an existing SHPB test for re-analysis. Parses the TTL file, loads CSV data, and extracts equipment properties from the ontology.

### Parameter Updates

**Bar Properties:**
```python
reanalyzer.update_bar_property(bar_type, property_name, new_value)
# bar_type: 'striker', 'incident', or 'transmission'
# property_name: 'wave_speed', 'elastic_modulus', 'cross_section', 'density'
```

**Specimen Properties:**
```python
reanalyzer.update_specimen_property(property_name, new_value)
# property_name: 'cross_section', 'height'
```

**Gauge Properties:**
```python
reanalyzer.update_gauge_property(gauge_type, property_name, new_value)
# gauge_type: 'incident', 'transmission'
# property_name: 'gauge_factor', 'gauge_resistance', etc.
```

**Alignment Parameters:**
```python
reanalyzer.update_alignment_param(param_name, new_value)
# param_name: 'k_linear', 'search_bounds_t', 'search_bounds_r',
#             'weight_corr', 'weight_u', 'weight_sr', 'weight_e'
```

### Inspection

```python
# View current parameters
params = reanalyzer.get_current_parameters()

# View original parameters (as loaded)
original = reanalyzer.get_original_parameters()

# See what changed
changes = reanalyzer.get_parameter_changes()
# Returns: {'incident_bar.wave_speed': (4953.321, 5000.0), ...}

# View alignment parameters
align = reanalyzer.get_alignment_parameters()
```

### Execution

```python
# Fast: uses existing aligned pulses
results = reanalyzer.recalculate(mode='analysis_only')

# Slow: re-runs from raw data
results = reanalyzer.recalculate(mode='full')

# Get results and metrics
results = reanalyzer.get_results()  # Dict with stress, strain, etc.
metrics = reanalyzer.get_metrics()  # Dict with FBC, DSUF, SEQI, SOI
```

### Saving Results

```python
# Save with version suffix (default - creates new files)
csv_path, ttl_path = reanalyzer.save(version_suffix="_recalibrated")

# Overwrite original files (use with caution)
csv_path, ttl_path = reanalyzer.save(overwrite=True)
```

## Example: Parameter Sensitivity Study

```python
from dynamat.mechanical.shpb import SHPBReanalyzer
from dynamat.ontology import OntologyManager

manager = OntologyManager()

# Study effect of wave speed variation
wave_speed_variations = [0.98, 0.99, 1.00, 1.01, 1.02]  # -2% to +2%
results_by_variation = {}

for factor in wave_speed_variations:
    reanalyzer = SHPBReanalyzer(manager)
    reanalyzer.load_test("path/to/test.ttl")

    # Get original wave speed and apply variation
    original_ws = reanalyzer.get_current_parameters()['incident_bar']['wave_speed']
    new_ws = original_ws * factor

    reanalyzer.update_bar_property('incident', 'wave_speed', new_ws)
    reanalyzer.update_bar_property('transmission', 'wave_speed', new_ws)

    results = reanalyzer.recalculate(mode='analysis_only')
    results_by_variation[factor] = results

    print(f"Wave speed {(factor-1)*100:+.0f}%: Peak stress = {results['stress_1w'].max():.2f} MPa")
```

## Example: Bar Recalibration

After recalibrating your bars, update the wave speed and re-analyze all affected tests:

```python
from dynamat.mechanical.shpb import SHPBReanalyzer
from dynamat.ontology import OntologyManager
from pathlib import Path

manager = OntologyManager()

# New calibrated wave speed
NEW_WAVE_SPEED = 5000.0  # mm/ms

# Find all test files
specimens_dir = Path("user_data/specimens")
test_files = list(specimens_dir.glob("*/*_SHPBTest.ttl"))

for test_file in test_files:
    print(f"Processing: {test_file.name}")

    reanalyzer = SHPBReanalyzer(manager)
    reanalyzer.load_test(test_file)

    # Update wave speed
    reanalyzer.update_bar_property('incident', 'wave_speed', NEW_WAVE_SPEED)
    reanalyzer.update_bar_property('transmission', 'wave_speed', NEW_WAVE_SPEED)

    # Recalculate
    results = reanalyzer.recalculate(mode='analysis_only')
    metrics = reanalyzer.get_metrics()

    print(f"  FBC: {metrics['FBC']:.4f}, DSUF: {metrics['DSUF']:.4f}")

    # Save with version suffix
    reanalyzer.save(version_suffix="_recalibrated_2026")
```

## Data Flow

### Analysis-Only Mode
```
Processed CSV (aligned pulses) + Ontology (equipment properties)
    |
    v
Load aligned pulses (incident, transmitted, reflected)
Query bar/specimen properties from ontology
    |
    v
User updates parameters (bar, specimen, gauge)
    |
    v
StressStrainCalculator.calculate()
    |
    v
calculate_equilibrium_metrics()
    |
    v
Save new processed CSV + TTL
```

### Full Re-Alignment Mode
```
Raw CSV + TTL (detection params) + Ontology (equipment properties)
    |
    v
Load raw signals (time, incident, transmitted)
Read detection and alignment parameters from TTL
    |
    v
User updates alignment parameters
    |
    v
PulseDetector.find_window() + segment_and_center()
    |
    v
PulseAligner.align() with updated params
    |
    v
StressStrainCalculator.calculate()
    |
    v
calculate_equilibrium_metrics()
    |
    v
Save new processed CSV + TTL
```

## See Also

- `notebooks/shpb/SHPB_Reanalysis_Example.ipynb` - Interactive examples
- `dynamat/mechanical/shpb/core/` - Core analysis classes
- `dynamat/mechanical/shpb/io/` - Data loading and writing utilities
