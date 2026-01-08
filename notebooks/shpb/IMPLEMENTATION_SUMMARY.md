# SHPB Test Ingestion System - Implementation Summary

## Overview

A complete system for ingesting SHPB compression test data into the DynaMat platform with full RDF metadata generation, FAIR data principles, and ontology integration.

## Components Implemented

### 1. Test Metadata Dataclass (`test_metadata.py`)

**Purpose**: Type-safe container for SHPB test metadata with validation

**Required Fields**:
- Test identification: `test_id`, `specimen_uri`, `test_date`, `operator_name`
- Equipment bars: `striker_bar_uri`, `incident_bar_uri`, `transmission_bar_uri`
- Strain gauges: `incident_strain_gauge_uri`, `transmission_strain_gauge_uri`
- Test condition: `striker_velocity` (with units)

**Optional Fields**:
- Equipment: `momentum_trap_uri`, `pulse_shaper_uri`
- Test conditions: `incident_strain_gauge_distance`, `transmission_strain_gauge_distance`, `barrel_offset`
- Pulse shaping: `pulse_shaping`, `pulse_shaper_diameter`, `pulse_shaper_thickness`
- Lubrication: `lubrication_used`, `lubrication_type`

**Key Methods**:
- `to_form_data()`: Convert to form data dict for InstanceWriter
- `validate()`: Validate required fields and data format

**Important Notes**:
- Bar lengths/materials are NOT stored in test metadata (inherited from Bar individuals)
- Strain gauge factors/resistances are inherited from StrainGauge individuals
- Strain gauge distances can override default positions if specified

### 2. CSV Data Handler (`csv_data_handler.py`)

**Purpose**: Validate and save pandas DataFrames containing raw SHPB signals

**Features**:
- Validates required columns: `time`, `incident`, `transmitted`
- Checks data quality: numeric types, no NaN/Inf, monotonic time
- Auto-detects sampling rate from time column
- Saves DataFrame as CSV with proper formatting
- Provides metadata for AnalysisFile creation

**Key Methods**:
- `validate_structure()`: Check DataFrame structure and quality
- `get_data_point_count()`: Number of rows
- `detect_sampling_rate()`: Calculate sampling rate (Hz)
- `save_to_csv(output_path)`: Save DataFrame as CSV
- `get_file_metadata_for_saving()`: Get CSV format metadata

### 3. DataSeries Builder (`data_series_builder.py`)

**Purpose**: Build RDF metadata for DataSeries and AnalysisFile instances

**Features**:
- Creates AnalysisFile metadata (file path, size, format, encoding)
- Creates DataSeries metadata for time, incident pulse, transmitted pulse
- Sets proper units (SEC for time, V for voltage)
- Sets quantity kinds (Time, Voltage)
- Sets processing flags (all False for raw data)

**Key Methods**:
- `create_analysis_file(file_path, specimen_dir, file_size, **metadata)`: AnalysisFile metadata
- `build_time_series(column_name, data_point_count, column_index)`: Time series metadata
- `build_incident_pulse_series(...)`: Incident pulse metadata
- `build_transmitted_pulse_series(...)`: Transmitted pulse metadata
- `build_all_raw_series(data_point_count)`: All three series at once

**Important Changes**:
- DataSeries NO LONGER have `hasDataFile` property
- File reference is on the Test/AnalysisFile level

### 4. SHPB Test Writer (`shpb_test_writer.py`)

**Purpose**: Orchestrate complete test ingestion workflow

**10-Step Workflow**:
1. Validate test metadata (required fields)
2. Validate DataFrame structure (required columns)
3. Determine specimen directory from specimen_uri
4. Create directory structure (raw/, processed/)
5. Save DataFrame as CSV to raw/
6. Create AnalysisFile instance for raw CSV
7. Create DataSeries instances (time, incident, transmitted)
8. Create SHPBCompression test instance
9. Link test to specimen (update specimen TTL)
10. Save test TTL file with validation

**Key Method**:
- `ingest_test(test_metadata, raw_data_df)`: Complete ingestion workflow
  - Returns: `(test_file_path, validation_result)`
  - Returns `(None, validation_result)` if validation fails

**Features**:
- Uses InstanceWriter for ALL RDF writing (no manual graph construction)
- Proper unit conversion for all instances
- Complete SHACL validation
- Combines all instances into single test TTL file
- Links test to specimen automatically

### 5. Property Extraction Helpers (`specimen_loader.py`)

**Purpose**: Extract inherited properties from equipment individuals for analysis

**New Methods**:
- `get_individual_property(individual_uri, property_name, return_type='value')`:
  - Extract single property from any individual
  - Returns just value or full metadata (value, unit, quantity kind)
  - Works for Bar, StrainGauge, MomentumTrap, PulseShaper, etc.

- `get_multiple_properties(individual_uri, property_names)`:
  - Extract multiple properties at once
  - Returns dict mapping property names to values

**Use Cases**:
- Get bar length for wave speed calculations
- Get strain gauge factor for voltage-to-strain conversion
- Get gauge resistance for calibration
- Get material properties for analysis

## File Organization

```
user_data/specimens/SPECIMEN_ID/
├── SPECIMEN_ID_specimen.ttl                    # Specimen metadata (updated with test link)
├── SPECIMEN_ID_SHPB_YYYY-MM-DD.ttl            # Test metadata (NEW)
├── raw/                                        # Raw data directory (NEW)
│   └── SPECIMEN_ID_SHPB_YYYY_MM_DD_raw.csv   # Raw CSV data (NEW)
└── processed/                                  # Processed results (NEW, empty for now)
```

## RDF Structure Created

### Test → AnalysisFile → DataSeries Relationship

```turtle
# Test instance
dyn:SPECIMEN_ID_SHPB_YYYY_MM_DD rdf:type dyn:SHPBCompression ;
    dyn:hasTestID "SPECIMEN_ID_SHPB_YYYY-MM-DD" ;
    dyn:hasSpecimen dyn:SPECIMEN_ID ;
    dyn:hasStrikerBar dyn:StrikerBar_C350_2ft ;
    dyn:hasIncidentBar dyn:IncidentBar_C350_6ft ;
    dyn:hasTransmissionBar dyn:TransmissionBar_C350_6ft ;
    dyn:hasStrainGauge dyn:StrainGauge_INC_SG1, dyn:StrainGauge_TRA_SG1 ;
    dyn:hasStrikerVelocity 12.5 ;
    dyn:hasRawDataFile dyn:SPECIMEN_ID_SHPB_YYYY_MM_DD_raw_csv ;  # Points to file
    dyn:hasDataSeries dyn:SPECIMEN_ID_SHPB_YYYY_MM_DD_time ;      # Points to column
    dyn:hasDataSeries dyn:SPECIMEN_ID_SHPB_YYYY_MM_DD_incident ;
    dyn:hasDataSeries dyn:SPECIMEN_ID_SHPB_YYYY_MM_DD_transmitted .

# AnalysisFile instance (describes the CSV file)
dyn:SPECIMEN_ID_SHPB_YYYY_MM_DD_raw_csv rdf:type dyn:AnalysisFile ;
    dyn:hasFileName "SPECIMEN_ID_SHPB_YYYY-MM-DD_raw.csv" ;
    dyn:hasFilePath "raw/SPECIMEN_ID_SHPB_YYYY-MM-DD_raw.csv" ;
    dyn:hasFileFormat "CSV" ;
    dyn:hasFileEncoding "UTF-8" ;
    dyn:hasDelimiter "," ;
    dyn:hasHeaderRow true ;
    dyn:hasSkipRows 0 ;
    dyn:hasFileSize 123456 .

# DataSeries instances (describe columns in the file)
dyn:SPECIMEN_ID_SHPB_YYYY_MM_DD_time rdf:type dyn:RawSignal ;
    dyn:hasSeriesType "Time" ;
    dyn:hasColumnName "time" ;
    dyn:hasColumnIndex 0 ;
    dyn:hasLegendName "Time" ;
    dyn:hasSeriesUnit "unit:SEC" ;
    dyn:hasQuantityKind "qkdv:Time" ;
    dyn:hasDataPointCount 10000 ;
    dyn:hasFilterApplied false ;
    dyn:isCenteredPulse false ;
    dyn:isAlignedPulse false .

# Similar for incident and transmitted DataSeries...

# Specimen update (test link added)
dyn:SPECIMEN_ID dyn:hasSHPBCompressionTest dyn:SPECIMEN_ID_SHPB_YYYY_MM_DD .
```

## Usage Example

```python
from dynamat.ontology import OntologyManager
from dynamat.mechanical.shpb.io import (
    SpecimenLoader,
    SHPBTestWriter,
    SHPBTestMetadata
)
import pandas as pd

# 1. Initialize
ontology_manager = OntologyManager()
specimen_loader = SpecimenLoader(ontology_manager)
test_writer = SHPBTestWriter(ontology_manager)

# 2. Load specimens
specimen_loader.load_specimen_files()
specimens = specimen_loader.find_specimens(material_name="dyn:A356")
specimen_uri = specimens[0]['uri']

# 3. Load raw data (user converts from custom txt format)
raw_data_df = pd.DataFrame({
    'time': [...],
    'incident': [...],
    'transmitted': [...]
})

# 4. Create test metadata
test_metadata = SHPBTestMetadata(
    test_id="SPECIMEN_ID_SHPB_2025-01-15",
    specimen_uri=specimen_uri,
    test_date="2025-01-15",
    operator_name="ErwinCazares",
    striker_bar_uri="dyn:StrikerBar_C350_2ft",
    incident_bar_uri="dyn:IncidentBar_C350_6ft",
    transmission_bar_uri="dyn:TransmissionBar_C350_6ft",
    incident_strain_gauge_uri="dyn:StrainGauge_INC_SG1",
    transmission_strain_gauge_uri="dyn:StrainGauge_TRA_SG1",
    striker_velocity={'value': 12.5, 'unit': 'unit:M-PER-SEC', 'reference_unit': 'unit:M-PER-SEC'},
    momentum_trap_uri="dyn:MomentumTrap_Full",
    pulse_shaper_uri="dyn:PulseShaper_Copper_0020in"
)

# 5. Ingest test
test_file_path, validation = test_writer.ingest_test(test_metadata, raw_data_df)

if test_file_path:
    print(f"Test saved to: {test_file_path}")

    # 6. Extract equipment properties for analysis
    bar_length = specimen_loader.get_individual_property(
        "dyn:IncidentBar_C350_6ft",
        "hasLength"
    )
    gauge_factor = specimen_loader.get_individual_property(
        "dyn:StrainGauge_INC_SG1",
        "hasGaugeFactor"
    )

    print(f"Bar length: {bar_length} mm")
    print(f"Gauge factor: {gauge_factor}")
```

## Key Design Decisions

### 1. Inherited Properties
Bar lengths, diameters, and materials are NOT stored in test metadata. They are inherited from Bar individuals. This:
- Avoids data duplication
- Ensures consistency across tests using same equipment
- Makes equipment updates propagate automatically

### 2. File/Column Separation
DataSeries do NOT point to files directly. The structure is:
- Test → hasRawDataFile → AnalysisFile (describes the file)
- Test → hasDataSeries → DataSeries (describes columns)

This allows:
- Multiple tests to reference the same file
- Multiple columns to be defined per file
- Clear separation of file metadata vs. column metadata

### 3. InstanceWriter Integration
All RDF writing uses InstanceWriter, ensuring:
- Proper unit conversion
- Complete property handling
- SHACL validation
- Consistent RDF structure

### 4. No Special Characters in Logs
All logger statements use plain text (no emojis or special characters) to avoid terminal encoding issues.

## Validation Strategy

### 1. DataFrame Validation (CSVDataHandler)
- Required columns exist
- Data types are numeric
- No NaN or Inf values
- Time is monotonically increasing
- Minimum 10 data points

### 2. Metadata Validation (SHPBTestMetadata)
- Required fields not empty
- URIs have proper format (dyn: or http)
- Date format is YYYY-MM-DD
- Striker velocity has proper unit dict

### 3. RDF Validation (InstanceWriter)
- SHACL shapes validation
- Property domain/range checking
- Cardinality constraints
- Unit compatibility

## Next Steps

1. **Processed Data Ingestion**: Similar system for processed results (stress, strain, etc.)
2. **Test Querying**: Query methods to find tests by specimen, date, equipment
3. **Analysis Integration**: Direct integration with SHPB analysis toolkit
4. **GUI Integration**: Forms for test ingestion in the GUI
5. **Helper Method Expansion**: Add more property extraction helpers for other individuals

## Files Modified

- `dynamat/mechanical/shpb/io/test_metadata.py` (NEW - 198 lines)
- `dynamat/mechanical/shpb/io/csv_data_handler.py` (NEW - 247 lines)
- `dynamat/mechanical/shpb/io/data_series_builder.py` (NEW - 296 lines)
- `dynamat/mechanical/shpb/io/shpb_test_writer.py` (NEW - 541 lines)
- `dynamat/mechanical/shpb/io/specimen_loader.py` (UPDATED - added property extraction helpers)
- `dynamat/mechanical/shpb/io/__init__.py` (UPDATED - added exports)
- `notebooks/shpb/test_ingestion_cells.md` (NEW - notebook cells guide)
