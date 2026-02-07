# SHPB IO Module

This module provides RDF data extraction and test ingestion functionality for Split Hopkinson Pressure Bar (SHPB) testing. It handles the complete workflow from raw oscilloscope data to semantically annotated RDF/TTL files.

## Architecture Overview

```
+-------------------+     +-------------------+     +-------------------+
|  CSVDataHandler   | --> |  SHPBTestWriter   | --> |   TTL Output      |
| (Data Validation) |     |   (Orchestrator)  |     |  (RDF/Turtle)     |
+-------------------+     +-------------------+     +-------------------+
                                   |
                                   v
         +------------------------------------------------+
         |              Supporting Modules                 |
         +------------------------------------------------+
         | - SHPBTestMetadata (120+ analysis parameters)  |
         | - FormDataConverter (metadata -> RDF)          |
         | - DataSeriesBuilder (DataFrame -> DataSeries)  |
         | - ValidityAssessor (equilibrium metrics)       |
         | - SpecimenLoader (RDF graph queries)           |
         +------------------------------------------------+
```

## Module Exports

```python
from dynamat.mechanical.shpb.io import (
    # Core classes
    SpecimenLoader,
    SHPBTestMetadata,
    CSVDataHandler,
    SHPBTestWriter,

    # Helper functions
    ensure_typed_literal,
    apply_type_conversion_to_dict,

    # Extracted modules
    ValidityAssessor,
    SERIES_METADATA,
    DataSeriesBuilder,
    FormDataConverter,
)
```

---

## Classes

### CSVDataHandler

Validates and saves pandas DataFrames containing SHPB raw signal data.

**Key Features:**
- Validates required columns (`time`, `incident`, `transmitted`)
- Checks data types, NaN/Inf values, and monotonic time
- Calculates sampling rate from time column
- Saves to CSV with proper encoding

**Example:**

```python
import pandas as pd
from dynamat.mechanical.shpb.io import CSVDataHandler

# Create sample data
df = pd.DataFrame({
    'time': [0.0, 1e-6, 2e-6, 3e-6, 4e-6, 5e-6, 6e-6, 7e-6, 8e-6, 9e-6],
    'incident': [0.0, 0.1, 0.3, 0.5, 0.4, 0.2, 0.0, -0.1, 0.0, 0.0],
    'transmitted': [0.0, 0.0, 0.05, 0.15, 0.25, 0.2, 0.1, 0.0, 0.0, 0.0]
})

# Initialize and validate
handler = CSVDataHandler(df)
handler.validate_structure()  # Raises ValueError if invalid

# Get data info
print(f"Data points: {handler.get_data_point_count()}")
print(f"Sampling rate: {handler.detect_sampling_rate():.0f} Hz")

# Save to file
from pathlib import Path
handler.save_to_csv(Path('output/raw_signals.csv'))
```

---

### SHPBTestMetadata

Complete metadata container capturing all SHPB analysis parameters (120+ fields) for full reproducibility.

**Categories:**
- Core identification (test_id, specimen_uri, date, user)
- Equipment configuration (bars, strain gauges)
- Pulse detection parameters (incident, transmitted, reflected)
- Segmentation and alignment settings
- Equilibrium metrics (FBC, SEQI, SOI, DSUF)
- Calculated characteristics (pulse duration, stress amplitude)

**Example:**

```python
from dynamat.mechanical.shpb.io import SHPBTestMetadata

# Create metadata for a test
metadata = SHPBTestMetadata(
    # Required fields
    test_id='TEST_2024_001',
    specimen_uri='dyn:DYNML_SS316A356_0001',
    test_date='2024-01-15',
    user='JSmith',

    # Equipment URIs
    striker_bar_uri='dyn:StrikerBar_C350_2ft',
    incident_bar_uri='dyn:IncidentBar_C350_6ft',
    transmission_bar_uri='dyn:TransmissionBar_C350_6ft',
    incident_strain_gauge_uri='dyn:StrainGauge_INC_SG1',
    transmission_strain_gauge_uri='dyn:StrainGauge_TRA_SG1',

    # Optional test conditions
    striker_velocity={'value': 15.0, 'unit': 'unit:M-PER-SEC'},
    striker_launch_pressure={'value': 30.0, 'unit': 'unit:PSI'},

    # Pulse detection config
    incident_pulse_points=1000,
    incident_polarity='compressive',

    # Analysis results
    fbc=0.96,
    seqi=0.92,
    soi=0.04,
    dsuf=0.99
)

# Validate all fields
metadata.validate()

# Auto-assess validity from equilibrium metrics
metrics = {'FBC': 0.96, 'SEQI': 0.92, 'SOI': 0.04, 'DSUF': 0.99}
metadata.assess_validity_from_metrics(metrics)

print(f"Test validity: {metadata.test_validity}")  # dyn:ValidTest
print(f"Is valid: {metadata.is_valid()}")  # True
```

**Extracting Equipment Properties:**

```python
from dynamat.mechanical.shpb.io import SpecimenLoader

loader = SpecimenLoader(ontology_manager)
loader.load_specimen_files()

# Extract all equipment properties for analysis
equipment = metadata.extract_all_equipment_properties(loader)

print(f"Incident bar length: {equipment['incident_bar']['length']} mm")
print(f"Wave speed: {equipment['incident_bar']['wave_speed']} m/s")
print(f"Gauge factor: {equipment['incident_gauge']['gauge_factor']}")
```

---

### SHPBTestWriter

Simplified workflow orchestrator for SHPB test data ingestion. Delegates RDF generation to InstanceWriter.

**Workflow Steps:**
1. Validate metadata and DataFrame
2. Save CSV file(s) (raw, and processed if provided)
3. Build all RDF instances (AnalysisFile, DataSeries, processing objects)
4. Save all instances to single TTL file
5. Link test to specimen

**Example:**

```python
from dynamat.mechanical.shpb.io import SHPBTestWriter, SHPBTestMetadata
from dynamat.ontology import OntologyManager
import pandas as pd

# Initialize
ontology_manager = OntologyManager()
writer = SHPBTestWriter(ontology_manager)

# Prepare data
metadata = SHPBTestMetadata(
    test_id='TEST_2024_001',
    specimen_uri='dyn:DYNML_SS316A356_0001',
    test_date='2024-01-15',
    user='JSmith',
    striker_bar_uri='dyn:StrikerBar_C350_2ft',
    incident_bar_uri='dyn:IncidentBar_C350_6ft',
    transmission_bar_uri='dyn:TransmissionBar_C350_6ft',
    incident_strain_gauge_uri='dyn:StrainGauge_INC_SG1',
    transmission_strain_gauge_uri='dyn:StrainGauge_TRA_SG1',
)

raw_df = pd.DataFrame({
    'time': [...],
    'incident': [...],
    'transmitted': [...]
})

# Ingest test (creates TTL file and links to specimen)
test_path, validation = writer.ingest_test(metadata, raw_df)

if test_path:
    print(f"Test saved to: {test_path}")
else:
    print(f"Validation failed: {validation.get_summary()}")
```

**With Processed Results:**

```python
from dynamat.mechanical.shpb.analysis import StressStrainCalculator

# Calculate stress-strain curves
calculator = StressStrainCalculator(...)
processed_results = calculator.calculate(inc, trs, ref, time)

# Ingest with processed data
test_path, validation = writer.ingest_test(
    metadata,
    raw_df,
    processed_results=processed_results
)
```

---

### SpecimenLoader

High-level interface for loading and querying specimen data from RDF graphs.

**Example:**

```python
from dynamat.ontology import OntologyManager
from dynamat.mechanical.shpb.io import SpecimenLoader

manager = OntologyManager()
loader = SpecimenLoader(manager)

# Load all specimen files
count = loader.load_specimen_files()
print(f"Loaded {count} specimen files")

# Find specimens by material
specimens = loader.find_specimens(material_name='SS316')
for spec in specimens:
    print(f"  {spec['id']}: {spec['material_name']}")

# Get detailed specimen data
specimen_data = loader.get_specimen_data(specimens[0]['uri'])
print(f"Dimensions: {specimen_data['dimensions']}")
print(f"Manufacturing: {specimen_data['manufacturing']}")
```

**Querying Individual Properties:**

```python
# Get a single property
bar_length = loader.get_individual_property(
    'dyn:IncidentBar_C350_6ft',
    'hasLength'
)
print(f"Bar length: {bar_length} mm")

# Get multiple properties at once
gauge_props = loader.get_multiple_properties(
    'dyn:StrainGauge_INC_SG1',
    ['hasGaugeFactor', 'hasGaugeResistance', 'hasDistanceFromSpecimen']
)
print(f"Gauge factor: {gauge_props['hasGaugeFactor']}")
```

---

### ValidityAssessor

Assesses SHPB test validity based on equilibrium metrics using multi-level criteria.

**Threshold Constants:**

| Metric | Strict | Relaxed | Description |
|--------|--------|---------|-------------|
| FBC    | 0.95   | 0.85    | Force Balance Coefficient |
| SEQI   | 0.90   | 0.80    | Stress Equilibrium Quality Index |
| SOI    | 0.05   | 0.10    | Strain Offset Index (lower is better) |
| DSUF   | 0.98   | 0.90    | Dynamic Stress Uniformity Factor |

**Validity Levels:**
- `dyn:ValidTest` - All 4 metrics meet strict standards
- `dyn:QuestionableTest` - At least 2/4 relaxed standards met
- `dyn:InvalidTest` - Less than 2/4 relaxed standards met

**Example:**

```python
from dynamat.mechanical.shpb.io import ValidityAssessor

assessor = ValidityAssessor()

metrics = {
    'FBC': 0.96,
    'SEQI': 0.92,
    'SOI': 0.04,
    'DSUF': 0.99
}

# Full assessment
result = assessor.assess_validity_from_metrics(metrics)
print(f"Validity: {result['test_validity']}")
print(f"Notes: {result['validity_notes']}")
print(f"Criteria met: {result['validity_criteria']}")

# Individual assessments
validity = assessor.determine_overall_validity(metrics)
force_eq = assessor.assess_force_equilibrium(0.96, 0.99)
strain_rate = assessor.assess_strain_rate(0.04)

print(f"Force equilibrium: {force_eq}")  # 'achieved'
print(f"Constant strain rate: {strain_rate}")  # 'achieved'
```

---

### FormDataConverter

Converts SHPBTestMetadata to form data dictionaries for RDF instance writing.

**Example:**

```python
from dynamat.mechanical.shpb.io import FormDataConverter

converter = FormDataConverter(metadata)

# Get form data for test instance
form_data = converter.to_form_data()
# Returns: {'dyn:hasTestID': 'TEST_001', 'dyn:performedOn': 'dyn:SPECIMEN_001', ...}

# Get all processing instances for batch creation
processing = converter.get_processing_instances()
# Returns: {
#     'detection_params': [(form_data, 'dyn:PulseDetectionParams', instance_id), ...],
#     'alignment_params': [...],
#     'equilibrium_metrics': [...]
# }
```

---

### DataSeriesBuilder

Builds DataSeries instances from DataFrames using SERIES_METADATA configuration.

**Example:**

```python
from dynamat.mechanical.shpb.io import DataSeriesBuilder, SERIES_METADATA

builder = DataSeriesBuilder(test_metadata)

# Create raw signal DataSeries instances
gauge_params = {
    'incident': 'dyn:StrainGauge_INC_SG1',
    'transmitted': 'dyn:StrainGauge_TRA_SG1'
}

raw_series = builder.prepare_raw_data_series(
    raw_df,
    file_uri='dyn:TEST_001_raw_csv',
    gauge_params=gauge_params
)
# Returns: [(form_data, 'dyn:RawSignal', 'TEST_001_time'), ...]

# Create windowed DataSeries
raw_uris = {
    'time': 'dyn:TEST_001_time',
    'incident': 'dyn:TEST_001_incident',
    'transmitted': 'dyn:TEST_001_transmitted'
}

windowed_series = builder.prepare_windowed_data_series(
    raw_series_uris=raw_uris,
    window_length=1000,
    file_uri='dyn:TEST_001_processed_csv'
)

# Create processed DataSeries with derivation chains
processed_series = builder.prepare_processed_data_series(
    results={'stress_1w': [...], 'strain_1w': [...], ...},
    file_uri='dyn:TEST_001_processed_csv',
    windowed_series_uris={'incident_windowed': 'dyn:TEST_001_incident_windowed', ...}
)
```

---

### RDF Helper Functions

Utilities for converting Python types to RDF Literals with explicit XSD datatypes.

**Example:**

```python
from dynamat.mechanical.shpb.io import ensure_typed_literal, apply_type_conversion_to_dict
from rdflib.namespace import XSD

# Single value conversion
literal = ensure_typed_literal(25000)
# Returns: Literal(25000, datatype=XSD.integer)

literal = ensure_typed_literal(0.35)
# Returns: Literal(0.35, datatype=XSD.double)

literal = ensure_typed_literal(True)
# Returns: Literal(True, datatype=XSD.boolean)

literal = ensure_typed_literal("TEST_001")
# Returns: "TEST_001" (unchanged - strings stay strings)

# Dictionary conversion
form_dict = {
    'dyn:hasStartIndex': 7079,
    'dyn:hasEndIndex': 81301,
    'dyn:hasThreshold': 0.05
}

typed_form = apply_type_conversion_to_dict(form_dict)
# All numeric values now have explicit XSD datatypes
```

---

## SERIES_METADATA Configuration

The `SERIES_METADATA` constant provides metadata for all DataSeries types, loaded from the ontology with fallback to hardcoded values.

**Available Series Types:**

| Column Name | Series Type | Unit | Quantity Kind |
|-------------|-------------|------|---------------|
| `time` | Time | ms | Time |
| `incident` | IncidentPulse | V | Voltage |
| `transmitted` | TransmittedPulse | V | Voltage |
| `strain_1w` | Strain | - | Dimensionless |
| `stress_1w` | Stress | MPa | Stress |
| `strain_rate_1w` | StrainRate | 1/s | StrainRate |
| `true_strain_1w` | TrueStrain | - | Dimensionless |
| `true_stress_1w` | TrueStress | MPa | Stress |
| (3-wave variants) | ... | ... | ... |

**Accessing Metadata:**

```python
from dynamat.mechanical.shpb.io import SERIES_METADATA

# Get metadata for a specific series
stress_meta = SERIES_METADATA['stress_1w']
print(f"Unit: {stress_meta['unit']}")
print(f"Quantity kind: {stress_meta['quantity_kind']}")
print(f"Legend name: {stress_meta['legend_name']}")

# Check if a series type exists
if 'strain_3w' in SERIES_METADATA:
    print("3-wave strain is available")

# Iterate over all series
for name, meta in SERIES_METADATA.items():
    print(f"{name}: {meta['legend_name']}")
```

---

## Typical Workflow

```python
from dynamat.ontology import OntologyManager
from dynamat.mechanical.shpb.io import (
    SpecimenLoader,
    SHPBTestMetadata,
    CSVDataHandler,
    SHPBTestWriter
)
import pandas as pd

# 1. Initialize
manager = OntologyManager()
loader = SpecimenLoader(manager)
loader.load_specimen_files()

# 2. Find specimen to test
specimens = loader.find_specimens(material_name='SS316')
specimen_uri = specimens[0]['uri']

# 3. Load raw data
raw_df = pd.read_csv('oscilloscope_data.csv')

# 4. Validate raw data
handler = CSVDataHandler(raw_df)
handler.validate_structure()

# 5. Create metadata
metadata = SHPBTestMetadata(
    test_id='TEST_2024_001',
    specimen_uri=specimen_uri,
    test_date='2024-01-15',
    user='JSmith',
    # ... equipment URIs ...
    # ... analysis parameters ...
)

# 6. Ingest test
writer = SHPBTestWriter(manager)
test_path, validation = writer.ingest_test(metadata, raw_df)

print(f"Test saved: {test_path}")
```
