# RawDataLoaderWidget

Ontology-driven widget for loading raw data files and mapping CSV columns to data series defined in the DynaMat ontology.

## Overview

Instead of hardcoding column mapping UI for each test type, `RawDataLoaderWidget` queries the ontology via `dyn:hasRawSeries` to dynamically build column mapping rows. Each row includes a QUDT unit dropdown populated from the series' `qudt:hasQuantityKind`.

## Architecture

The widget is composed of two main parts:

1. **DataFileWidget** (sub-widget): Handles file selection, separator dropdown, and skip rows
2. **RawDataLoaderWidget** (main widget): Adds column mapping and data preview on top of DataFileWidget

```
RawDataLoaderWidget
├── DataFileWidget (Data File section)
│   ├── File browse (hardcoded Python)
│   ├── Separator dropdown (ontology-driven from dyn:ColumnSeparator)
│   └── Skip rows spinbox
├── Column Mapping section
│   └── Per-series: Column dropdown + Unit dropdown
└── Data Preview section
    └── Table with first N rows
```

## Usage

### Ontology-Driven Mode (Preferred)

```python
from dynamat.gui.widgets.base.raw_data_loader import RawDataLoaderConfig, RawDataLoaderWidget

config = RawDataLoaderConfig(
    test_class_uri="dyn:SHPBCompression"
)
widget = RawDataLoaderWidget(config, ontology_manager, qudt_manager)
widget.data_loaded.connect(on_data_loaded)
```

### Manual Mode

```python
config = RawDataLoaderConfig(
    required_series=[
        {'key': 'time', 'label': 'Time', 'default_column': 'time',
         'quantity_kind': 'http://qudt.org/vocab/quantitykind/Time',
         'unit': 'http://qudt.org/vocab/unit/MilliSEC'},
        {'key': 'force', 'label': 'Force', 'default_column': 'force',
         'quantity_kind': 'http://qudt.org/vocab/quantitykind/Force',
         'unit': 'http://qudt.org/vocab/unit/N'},
    ]
)
widget = RawDataLoaderWidget(config, ontology_manager)
```

### Standalone DataFileWidget

```python
from dynamat.gui.widgets.base.raw_data_loader import DataFileWidget

widget = DataFileWidget(ontology_manager)
widget.file_loaded.connect(lambda df: print(f"Loaded {len(df)} rows"))
widget.set_default_directory(Path("/data"))
```

## Column Mapping Strategy

When a file is loaded, columns are auto-mapped using:

1. **Name match**: If a file column name matches `dyn:hasDefaultColumnName` (case-insensitive), it is auto-selected.
2. **Order fallback**: Unmatched series are assigned the next unmapped column by position.
3. **User override**: Users can always manually change any selection.

## DataFileWidget

Sub-widget for file selection and parsing settings, extracted from RawDataLoaderWidget.

### Ontology-Driven Separator Dropdown

The separator dropdown is populated from `dyn:ColumnSeparator` individuals in the ontology:

```turtle
dyn:CommaSeparator rdf:type owl:NamedIndividual, dyn:ColumnSeparator ;
    rdfs:label "Comma (,)"@en ;
    dyn:hasDelimiterCharacter "," ;
    gui:hasDisplayOrder 1 .
```

If the ontology query fails or returns empty, hardcoded defaults are used as fallback.

### Signals

| Signal | Payload | Description |
|--------|---------|-------------|
| `file_loaded(object)` | pd.DataFrame | File successfully parsed |
| `file_cleared()` | None | Data cleared |
| `settings_changed()` | None | Separator or skip rows changed |
| `error_occurred(str)` | Error message | Error occurred |

### Public API

| Method | Returns | Description |
|--------|---------|-------------|
| `load_file(path)` | `bool` | Programmatic file load |
| `get_file_path()` | `Optional[Path]` | Current file path |
| `get_separator()` | `str` | Current delimiter character |
| `get_separator_uri()` | `Optional[str]` | ColumnSeparator individual URI |
| `get_skip_rows()` | `int` | Current skip rows value |
| `get_dataframe()` | `Optional[DataFrame]` | Loaded DataFrame |
| `set_default_directory(path)` | None | Set browser default directory |
| `clear()` | None | Reset widget |

## RawDataLoaderWidget Signals

| Signal | Payload | Description |
|--------|---------|-------------|
| `data_loaded(dict)` | `{dataframe, column_mapping, unit_mapping, file_path, sampling_interval, total_samples, separator, separator_uri}` | Data loaded and mapped |
| `data_cleared()` | None | Data cleared |
| `mapping_changed(dict)` | `{column_mapping, unit_mapping, is_complete}` | Mapping changed |
| `error_occurred(str)` | Error message | Error occurred |

## RawDataLoaderWidget Public API

| Method | Returns | Description |
|--------|---------|-------------|
| `load_file(path)` | `bool` | Programmatic file load |
| `get_data()` | `Optional[dict]` | Current data payload |
| `get_dataframe()` | `Optional[DataFrame]` | Loaded DataFrame |
| `get_column_mapping()` | `Dict[str, str]` | `{series_key: column_name}` |
| `get_unit_mapping()` | `Dict[str, dict]` | `{series_key: {unit, symbol}}` |
| `get_sampling_interval()` | `Optional[float]` | Calculated sampling interval |
| `is_mapping_complete()` | `bool` | All series mapped |
| `set_default_directory(path)` | None | Set browser default directory |
| `clear()` | None | Reset widget |

## Ontology Requirements

### Test Class Raw Series

The test class must declare raw series via `dyn:hasRawSeries`:

```turtle
dyn:SHPBCompression dyn:hasRawSeries dyn:Time ,
                                     dyn:IncidentPulse ,
                                     dyn:TransmittedPulse .
```

### SeriesType Individuals

Each `dyn:SeriesType` individual must have:
- `rdfs:label` - Display name
- `dyn:hasDefaultColumnName` - Default CSV column name for matching
- `qudt:hasQuantityKind` - QUDT quantity kind (for unit dropdown)
- `dyn:hasUnit` - Default QUDT unit

### ColumnSeparator Individuals

Separator options are defined as `dyn:ColumnSeparator` individuals:

```turtle
dyn:ColumnSeparator rdf:type owl:Class ;
    rdfs:comment "Column delimiter type for tabular data files."@en .

dyn:hasDelimiterCharacter rdf:type owl:DatatypeProperty ;
    rdfs:domain dyn:ColumnSeparator ;
    rdfs:range xsd:string .

dyn:CommaSeparator rdf:type owl:NamedIndividual, dyn:ColumnSeparator ;
    rdfs:label "Comma (,)"@en ;
    dyn:hasDelimiterCharacter "," ;
    gui:hasDisplayOrder 1 .
```

### AnalysisFile Subclasses

Data files can be typed as:
- `dyn:RawDataFile` - Raw input data (oscilloscope CSV/TXT)
- `dyn:ProcessedDataFile` - Processed output from analysis pipeline

Both inherit GUI-annotated properties:
- `dyn:hasFilePath` (gui:hasDisplayOrder 1)
- `dyn:hasColumnSeparator` (gui:hasDisplayOrder 2) - ObjectProperty to ColumnSeparator
- `dyn:hasHeaderRow` (gui:hasDisplayOrder 3)
