# DynaMat Platform - Development Guide

Welcome! This guide will help you understand the DynaMat Platform's architecture and development philosophy. The project is built around a core principle: **let the ontology drive everything**.

## Project Vision

DynaMat Platform is a desktop application for managing dynamic materials testing data through an **ontology-based GUI design**. What does that mean? Instead of hard-coding forms and data structures, the GUI reads an RDF ontology and automatically generates appropriate interfaces. Change the ontology, and the GUI adapts.

### Core Philosophy

**Ontology-First Design**: Every piece of metadata, every relationship, every validation rule lives in the ontology. The GUI is just a view layer that interprets these semantic definitions.

**Module Independence**: The ontology module, GUI module, and future analysis modules (SHPB toolkit, structure generation) are designed to work independently. You can query the ontology without the GUI, or build a different GUI using the same ontology.

**FAIR Data Principles**: The platform emphasizes:
- **Findable**: Semantic metadata makes all data queryable via SPARQL
- **Accessible**: Standard RDF formats (Turtle/TTL) readable by any RDF tool
- **Interoperable**: Uses standard vocabularies (QUDT for units, OWL for ontology)
- **Reusable**: Templates and clear provenance enable data reuse across labs

This isn't just for Python developers—it's for lab users who want structured, traceable, and shareable experimental data.

## Technology Stack

- **Python 3.11+**: Core language
- **RDFLib**: Ontology handling and SPARQL queries
- **PyQt6**: Desktop GUI framework
- **QUDT**: Unit ontology for measurements
- **SHACL**: Validation shapes

## Repository Structure

```
DynaMat-Platform/
├── dynamat/                    # Main Python package
│   ├── ontology/              # Ontology engine
│   │   ├── core/              # Core ontology definition
│   │   │   └── DynaMat_core.ttl
│   │   ├── class_properties/  # Property definitions by class
│   │   ├── class_individuals/ # Predefined individuals
│   │   ├── shapes/            # SHACL validation shapes
│   │   ├── templates/         # Reusable configurations
│   │   ├── manager.py         # OntologyManager (main interface)
│   │   ├── query_builder.py  # Domain-specific queries
│   │   ├── template_manager.py
│   │   └── validator.py       # SHACL validation
│   │
│   ├── gui/                   # PyQt6 interface (v2.0 refactored)
│   │   ├── core/              # Widget factory, form manager, data handler
│   │   ├── builders/          # Form building, layout management
│   │   ├── dependencies/      # Dependency manager, calculation engine
│   │   ├── widgets/           # UI components
│   │   ├── app.py             # Main application
│   │   └── main_window.py     # Main window
│   │
│   ├── shpb/                  # SHPB analysis toolkit (planned)
│   ├── structures/            # Structure generation (planned)
│   ├── models/                # Material models (planned)
│   └── config.py              # Configuration
│
├── specimens/                  # Specimen data database (SEPARATE)
│   └── SPN-{MaterialID}-{XXX}/
│       ├── SPN-*_specimen.ttl
│       ├── SPN-*_TEST_DATE.ttl
│       ├── raw/
│       └── processed/
│
├── guides/                     # Jupyter notebooks
│   └── Ontology_Explorer.ipynb
│
├── main.py                     # Application entry point
└── requirements.txt
```

### Why Specimens are Separate from Code

The `specimens/` directory is intentionally **outside** the `dynamat/` package. Here's why this matters:

**FAIR Data Management**:
- **Version Control**: Specimen data evolves differently than code. Git tracks changes to both, but they're logically separate concerns
- **Data Portability**: Labs can share entire specimen datasets by copying the folder—no code dependencies
- **Tool Independence**: Other RDF tools can read `specimens/` without knowing anything about DynaMat's Python code
- **Scalability**: As data grows, it doesn't bloat the code repository

**File Organization**:
- Each specimen gets its own folder: `SPN-AL6061-001/`, `SPN-SS316-042/`, etc.
- Inside each folder:
  - **TTL files**: Metadata (who, what, when, how)
  - **CSV files**: Numerical data (raw signals, processed results)
  - **Subdirectories**: `raw/` and `processed/` organize data by stage

**Multi-File Experiments**:
A single experiment might span multiple files:
```
specimens/SPN-AL6061-001/
├── SPN-AL6061-001_specimen.ttl          # Specimen metadata (created once)
├── SPN-AL6061-001_SHPB_20250115.ttl     # Test #1 metadata
├── SPN-AL6061-001_SHPB_20250120.ttl     # Test #2 metadata
├── SPN-AL6061-001_characterization.ttl  # SEM/microscopy data
├── raw/
│   ├── shpb_test_20250115.csv
│   └── shpb_test_20250120.csv
└── processed/
    ├── stress_strain_20250115.csv
    └── stress_strain_20250120.csv
```

The ontology module's `ImprovedRDFParser` can load all related files and correlate them automatically.

## Ontology Structure

The ontology is organized hierarchically to keep things manageable:

### Core Hierarchy

```
DynaMat Ontology/
│
├── Core Ontology (DynaMat_core.ttl)
│   └── Base classes: Specimen, MechanicalTest, Material, Equipment, etc.
│
├── Class Properties (class_properties/*.ttl)
│   ├── specimen_class.ttl              # All properties specific to Specimen
│   ├── mechanical_testing_class.ttl    # All properties for tests
│   ├── material_class.ttl              # Material properties
│   └── equipment_class.ttl             # Equipment properties
│
├── Predefined Individuals (class_individuals/*.ttl)
│   ├── material_individuals.ttl        # Al6061-T6, SS316L, Ti-6Al-4V
│   ├── equipment_individuals.ttl       # Specific bars, DAQ systems, strain gauges
│   └── mechanical_testing_individuals.ttl  # Test types, validity criteria
│
├── Templates (templates/)
│   ├── equipment/
│   │   └── SHPB_compression_C350.ttl   # Standard C350 steel bar setup
│   ├── materials/
│   └── structures/
│
└── SHACL Shapes (shapes/*.ttl)
    ├── specimen_shapes.ttl              # Validation rules for specimens
    └── mechanical_testing_shapes.ttl    # Validation rules for tests
```

### Understanding Relationships with Examples

Let's see how everything connects using actual TTL snippets:

#### 1. Core Class Definition

```turtle
# In DynaMat_core.ttl
dyn:Specimen rdf:type owl:Class ;
    rdfs:subClassOf dyn:PhysicalObject ;
    rdfs:label "Specimen"@en ;
    rdfs:comment "Physical sample prepared for testing"@en .

dyn:SHPBCompression rdf:type owl:Class ;
    rdfs:subClassOf dyn:DynamicTest ;
    rdfs:label "SHPB Compression Test"@en ;
    rdfs:comment "Split Hopkinson Pressure Bar compression test"@en .
```

#### 2. Property Definition with GUI Annotations

```turtle
# In specimen_class.ttl
dyn:hasOriginalLength rdf:type owl:DatatypeProperty, owl:FunctionalProperty ;
    rdfs:domain dyn:Specimen ;
    rdfs:range xsd:double ;
    qudt:hasQuantityKind qkdv:Length ;
    
    # GUI annotations (the magic that drives form generation)
    dyn:hasDisplayName "Original Length (mm)" ;
    dyn:hasFormGroup "GeometryDimensions" ;
    dyn:hasGroupOrder 2 ;
    dyn:hasDisplayOrder 3 ;
    dyn:hasDefaultUnit "unit:MilliM" ;
    
    rdfs:label "Original Length"@en ;
    rdfs:comment "Initial length of specimen before testing"@en .

dyn:hasMaterial rdf:type owl:ObjectProperty, owl:FunctionalProperty ;
    rdfs:domain dyn:Specimen ;
    rdfs:range dyn:Material ;
    
    # GUI annotations
    dyn:hasDisplayName "Material" ;
    dyn:hasFormGroup "Identification" ;
    dyn:hasGroupOrder 1 ;
    dyn:hasDisplayOrder 3 ;
    
    rdfs:label "Material"@en ;
    rdfs:comment "Base material of the specimen"@en .
```

#### 3. Predefined Individual

```turtle
# In material_individuals.ttl
dyn:Al6061_T6 rdf:type owl:NamedIndividual, dyn:AluminumAlloy ;
    rdfs:label "Al6061-T6"@en ;
    dyn:hasName "Aluminum 6061-T6"@en ;
    dyn:hasMaterialCode "AL6061"@en ;
    dyn:hasDescription "Heat-treated aluminum alloy"@en ;
    dyn:hasNominalDensity 2700.0 ;  # kg/m³
    dyn:hasYoungsModulus 68.9 ;     # GPa
    dyn:hasPoissonsRatio 0.33 .
```

#### 4. Template (Reusable Configuration)

```turtle
# In templates/equipment/SHPB_compression_C350.ttl
template:shpb_standard_setup rdf:type dyn:Template ;
    dyn:hasName "SHPB Standard C350 Setup" ;
    dyn:hasDescription "Standard SHPB configuration with C350 steel bars" ;
    dyn:hasTargetClass dyn:SHPBCompression .

# Example configuration that users can instantiate
template:shpb_c350_example rdf:type dyn:SHPBCompression ;
    rdfs:label "SHPB C350 Standard Configuration" ;
    
    # Bar configuration
    dyn:hasStrikerBar dyn:StrikerBar_C350_2ft ;
    dyn:hasIncidentBar dyn:IncidentBar_C350_6ft ;
    dyn:hasTransmissionBar dyn:TransmissionBar_C350_6ft ;
    
    # Test parameters
    dyn:hasStrikerVelocity 15.0 ;      # m/s
    dyn:hasSamplingRate 2000000.0 ;    # Hz (2 MHz)
    dyn:hasGaugeFactor 2.12 ;
    dyn:hasTestTemperature 23.0 ;      # °C
    
    # Strain gauge configuration
    dyn:hasStrainGauge dyn:StrainGauge_INC_SG1, dyn:StrainGauge_TRA_SG1 ;
    dyn:hasIncidentStrainGaugeDistance 915.0 ;  # mm from impact
    dyn:hasTransmissionStrainGaugeDistance 915.0 .
```

#### 5. Actual Specimen Instance

```turtle
# In specimens/SPN-AL6061-001/SPN-AL6061-001_specimen.ttl
dyn:SPN_AL6061_001 rdf:type owl:NamedIndividual, dyn:Specimen ;
    rdfs:label "SPN-AL6061-001"@en ;
    
    # Identification
    dyn:hasSpecimenID "SPN-AL6061-001" ;
    dyn:hasMaterial dyn:Al6061_T6 ;          # Links to predefined individual
    dyn:hasStructure dyn:MonolithicMaterial ;
    dyn:hasShape dyn:CylindricalShape ;
    
    # Geometry
    dyn:hasOriginalLength 10.0 ;    # mm
    dyn:hasOriginalDiameter 6.35 ;  # mm
    dyn:hasOriginalMass 0.851 ;     # g
    
    # Manufacturing
    dyn:hasCreationDate "2025-01-10"^^xsd:date ;
    dyn:hasManufacturingMethod "Machining" ;
    dyn:hasSurfaceFinish "Polished" ;
    
    # Batch tracking
    dyn:hasSpecimenBatch dyn:Batch_AL001_2025_01 .
```

#### 6. Test Instance Linking Everything Together

```turtle
# In specimens/SPN-AL6061-001/SPN-AL6061-001_SHPB_20250115.ttl
dyn:SPN_AL6061_001_SHPB_20250115 rdf:type owl:NamedIndividual, dyn:SHPBCompression ;
    rdfs:label "SHPB Test on SPN-AL6061-001"@en ;
    
    # Links to specimen
    dyn:hasSpecimen dyn:SPN_AL6061_001 ;
    
    # Test metadata
    dyn:hasTestID "SHPB-AL6061-001-20250115" ;
    dyn:hasTestDate "2025-01-15"^^xsd:date ;
    dyn:hasOperator dyn:User_JohnDoe ;
    
    # Configuration (from template or custom)
    dyn:hasStrikerBar dyn:StrikerBar_C350_2ft ;
    dyn:hasIncidentBar dyn:IncidentBar_C350_6ft ;
    dyn:hasTransmissionBar dyn:TransmissionBar_C350_6ft ;
    dyn:hasStrikerVelocity 18.5 ;           # m/s (custom value)
    dyn:hasSamplingRate 2000000.0 ;         # Hz
    dyn:hasTestTemperature 23.0 ;           # °C
    
    # Data files
    dyn:hasRawDataFile dyn:RawData_SHPB_20250115 ;
    dyn:hasProcessedDataFile dyn:ProcessedData_SHPB_20250115 ;
    
    # Results
    dyn:hasMaxStress 450.0 ;                # MPa
    dyn:hasStrainRate 2500.0 ;              # 1/s
    dyn:hasTestValidity dyn:ValidTest .

# Data file metadata
dyn:RawData_SHPB_20250115 rdf:type dyn:DataFile ;
    dyn:hasFileName "shpb_raw_20250115.csv" ;
    dyn:hasRelativePath "raw/" ;
    dyn:hasFileFormat "CSV" ;
    dyn:hasDataColumns "time, incident, reflected, transmitted" .
```

See how everything connects? The specimen instance references the Al6061-T6 material individual. The test instance references both the specimen and equipment individuals. Templates provide starting configurations that users can customize.

## How GUI Forms are Generated

This is where the magic happens. The GUI doesn't have hard-coded forms—it reads the ontology annotations and builds forms automatically.

### The Annotation System

Remember those `dyn:hasDisplayName`, `dyn:hasFormGroup`, etc. properties? Those are **GUI annotations**. Here's what each one does:

```turtle
dyn:hasOriginalDiameter rdf:type owl:DatatypeProperty ;
    rdfs:domain dyn:Specimen ;
    rdfs:range xsd:double ;                     # Tells GUI: numeric input
    qudt:hasQuantityKind qkdv:Length ;          # Tells GUI: this is a length
    
    dyn:hasDisplayName "Original Diameter (mm)" ;  # Label shown to user
    dyn:hasFormGroup "GeometryDimensions" ;        # Which section of the form
    dyn:hasGroupOrder 2 ;                          # Order of sections
    dyn:hasDisplayOrder 4 ;                        # Order within section
    dyn:hasDefaultUnit "unit:MilliM" ;             # Default unit selection
    
    rdfs:label "Original Diameter"@en ;
    rdfs:comment "Initial diameter for cylindrical specimens"@en .
```

### Form Generation Flow (Overview)

Here's how the system transforms ontology into GUI:

```
User requests form for "dyn:Specimen"
        ↓
OntologyManager reads class definition
  → Finds all properties with rdfs:domain dyn:Specimen
  → Reads GUI annotations (displayName, formGroup, displayOrder, etc.)
  → Infers widget types from data types (xsd:double → number input)
        ↓
GUISchemaBuilder creates PropertyMetadata objects
  → Groups properties by formGroup
  → Sorts by displayOrder within each group
  → Identifies measurement properties (has qudt:hasQuantityKind)
        ↓
OntologyFormBuilder orchestrates form creation
  → FormManager creates base QWidget
  → WidgetFactory creates specific widgets per property type
  → LayoutManager arranges widgets into sections
  → DependencyManager connects field dependencies
        ↓
Form appears in GUI with:
  ✓ Proper labels from hasDisplayName
  ✓ Grouped sections from hasFormGroup
  ✓ Correct widget types from XSD types
  ✓ Unit selectors from QUDT integration
  ✓ Dropdown menus from object property ranges
```

**The beauty**: Change the ontology annotations, reload the application, and the form automatically updates. No GUI code to modify.

### Widget Type Inference

The system automatically chooses the right widget based on property definitions:

| Property Type | Widget Created |
|---------------|----------------|
| `xsd:string` | Text input (QLineEdit) |
| `xsd:string` + `hasValidValues` | Dropdown (QComboBox) |
| `xsd:integer` | Number input (QSpinBox) |
| `xsd:double` | Decimal input (QDoubleSpinBox) |
| `xsd:double` + `qudt:hasQuantityKind` | Number + unit selector (UnitValueWidget) |
| `xsd:boolean` | Checkbox (QCheckBox) |
| `xsd:date` | Date picker (QDateEdit) |
| `owl:ObjectProperty` → Material | Dropdown with Al6061-T6, SS316L, etc. |

### Validation Layers

Forms have multiple validation levels:

**1. Widget-Level (Immediate)**
- Data type checking (xsd:double ensures numeric input)
- Range validation (from SHACL shapes: `sh:minExclusive 0.0`)
- Format validation (dates, units)

**2. Form-Level (On Save)**
- Required fields (from SHACL: `sh:minCount 1`)
- Field dependencies (managed by DependencyManager)
- Completeness checks

**3. SHACL Validation (Before Finalization)**
```turtle
# From specimen_shapes.ttl
dyn:SpecimenShape a sh:NodeShape ;
    sh:targetClass dyn:Specimen ;
    
    sh:property [
        sh:path dyn:hasSpecimenID ;
        sh:minCount 1 ;    # Required
        sh:maxCount 1 ;    # Single value
        sh:datatype xsd:string ;
        sh:pattern "^SPN-[A-Z0-9]+-[0-9]{3}$" ;  # Format validation
    ] ;
    
    sh:property [
        sh:path dyn:hasOriginalDiameter ;
        sh:datatype xsd:double ;
        sh:minExclusive 0.0 ;  # Must be positive
    ] .
```

## Established Patterns

### 1. The Measurement Pattern

**Problem**: How do you store a value with its unit in RDF?

**Our Solution**: Don't store "10.0 mm" as a string. Create a proper measurement structure:

```turtle
# WRONG - loses semantic meaning
dyn:SPN_001 dyn:hasLength "10.0 mm" .

# RIGHT - structured and queryable
dyn:SPN_001 dyn:hasOriginalLength 10.0 ;
            dyn:hasOriginalLengthUnit unit:MilliM .

# Even better with QUDT
dyn:hasOriginalLength rdf:type owl:DatatypeProperty ;
    qudt:hasQuantityKind qkdv:Length ;
    dyn:hasDefaultUnit "unit:MilliM" .
```

The GUI automatically creates a UnitValueWidget (number input + unit dropdown) when it sees `qudt:hasQuantityKind`.

### 2. Template Usage Pattern

Templates provide reusable configurations. Here's how they work:

**Template Definition** (in `templates/equipment/`)
```turtle
template:shpb_standard_setup rdf:type dyn:Template ;
    dyn:hasTargetClass dyn:SHPBCompression ;
    dyn:hasName "Standard C350 Setup" .

template:shpb_c350_example rdf:type dyn:SHPBCompression ;
    # ... all the standard values ...
```

**Template Instantiation** (in GUI)
```python
# User selects "Standard C350 Setup" from template dropdown
template_manager = ontology_manager.create_template_manager()
template = template_manager.load_template("shpb_standard_setup")

# GUI populates form fields with template values
# User can modify any field before saving
```

### 3. Individual vs. Literal Values

**When to use individuals** (separate TTL entries):
- Materials (Al6061-T6, SS316L) - reused across many specimens
- Equipment (specific bars, DAQ systems) - shared resources
- Standard configurations - referenced by multiple tests

**When to use literal values** (properties on instances):
- Measurements specific to one specimen (original length, mass)
- Test conditions that vary (striker velocity, temperature)
- Timestamps, IDs, descriptions

### 4. File Naming Convention

**Specimen Files**:
- Format: `SPN-{MaterialCode}-{SequenceNumber}_specimen.ttl`
- Example: `SPN-AL6061-001_specimen.ttl`

**Test Files**:
- Format: `SPN-{MaterialCode}-{SequenceNumber}_{TestType}_{Date}.ttl`
- Example: `SPN-AL6061-001_SHPB_20250115.ttl`

**Data Files**:
- Raw data: `{description}_{date}.csv` in `raw/` subdirectory
- Processed: `{analysis_type}_{date}.csv` in `processed/` subdirectory

### 5. URI Generation Pattern

**Base URI**: `https://dynamat.utep.edu/`

**Specimens**: `{base}specimens/SPN-{MaterialCode}-{Sequence}`
- Example: `https://dynamat.utep.edu/specimens/SPN-AL6061-001`

**Tests**: `{specimen_uri}_{TestType}_{Date}`
- Example: `https://dynamat.utep.edu/specimens/SPN-AL6061-001_SHPB_20250115`

**Measurements**: `{parent_uri}_{PropertyName}`
- Example: `https://dynamat.utep.edu/specimens/SPN-AL6061-001_OriginalLength`

The system auto-generates these URIs and handles collisions automatically.

## SHPB Test Workflow Example

Let's walk through creating an SHPB compression test entry using the GUI.

### Scenario
User has:
- An aluminum specimen already created (SPN-AL6061-001)
- A standard C350 steel bar SHPB setup
- Raw data file from the test

### Step-by-Step Workflow

**Step 1: Navigate to Mechanical Test Activity**

User opens DynaMat Platform → clicks "Mechanical Test" tab

**Step 2: Create New Test**

User clicks "New Test" button → dialog appears:
- "Select Test Type": Dropdown with [SHPB Compression, Quasi-static Compression, Tensile, ...]
- User selects "SHPB Compression"

**Step 3: Select Template (The Time-Saver)**

Form loads with "Template" dropdown at top:
```
Template: [Select Template ▼]
          - None (Manual Entry)
          - Standard C350 Setup
          - Standard C350 with Pulse Shaper
          - Custom Configuration A
```

User selects "Standard C350 Setup"

**What Happens**: Form auto-populates with template values:
```
Equipment Configuration:
  Striker Bar: [C350 Steel - 2ft        ▼]  ← from template
  Incident Bar: [C350 Steel - 6ft      ▼]  ← from template
  Transmission Bar: [C350 Steel - 6ft  ▼]  ← from template
  
Test Conditions:
  Striker Velocity: [15.0] m/s              ← from template
  Sampling Rate: [2000000] Hz               ← from template
  Test Temperature: [23.0] °C               ← from template
  
Strain Gauge Configuration:
  Incident Gauge: [INC-SG1 ▼]               ← from template
  Transmission Gauge: [TRA-SG1 ▼]           ← from template
  Gauge Factor: [2.12]                      ← from template
  Incident Gauge Distance: [915.0] mm       ← from template
  Transmission Gauge Distance: [915.0] mm   ← from template
```

User can now:
- Keep template values (most common)
- Modify specific fields (e.g., change striker velocity to 18.5 m/s)
- Add custom notes

**Step 4: Fill Required Fields**

Some fields aren't in the template (test-specific info):
```
Test Identification:
  Test ID: [Auto-generated: SHPB-AL6061-001-20250115]  ← Generated by GenerationEngine
  Specimen: [SPN-AL6061-001 ▼]  ← User selects from existing specimens
  Test Date: [2025-01-15]  ← Auto-filled with today, user can change
  Operator: [John Doe ▼]  ← User selection
```

**Step 5: Link Data Files**

```
Data Files:
  Raw Data File: [Browse...] → User selects shpb_raw_20250115.csv
    ↓
  System shows preview:
    - Columns detected: time, incident, reflected, transmitted ✓
    - 50,000 rows
    - File size: 2.3 MB
  
  Relative Path: [raw/]  ← System suggests, user can change
```

**Step 6: Real-Time Validation**

As user fills form, validation indicators appear:

```
✓ Specimen ID: Valid format
✓ Striker Velocity: 18.5 m/s (within valid range 5-30 m/s)
⚠ Test Temperature: Missing (recommended but not required)
✗ Raw Data File: Not selected (required)
```

Bottom of form shows:
```
[Validate] button - runs SHACL validation
Status: ⚠ 1 required field missing, 1 warning
```

**Step 7: Save and Generate TTL**

User clicks "Save"

**Behind the scenes**:
1. FormDataHandler collects all form data
2. DependencyManager calculates any derived values
3. SHACLValidator runs full validation
4. System generates TTL file:

```turtle
# File: specimens/SPN-AL6061-001/SPN-AL6061-001_SHPB_20250115.ttl

@prefix dyn: <https://dynamat.utep.edu/ontology#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

dyn:SPN_AL6061_001_SHPB_20250115 rdf:type owl:NamedIndividual, dyn:SHPBCompression ;
    rdfs:label "SHPB Compression Test - SPN-AL6061-001 - 2025-01-15"@en ;
    
    # Core identification
    dyn:hasTestID "SHPB-AL6061-001-20250115" ;
    dyn:hasSpecimen dyn:SPN_AL6061_001 ;
    dyn:hasTestDate "2025-01-15"^^xsd:date ;
    dyn:hasOperator dyn:User_JohnDoe ;
    
    # Equipment (from template)
    dyn:hasStrikerBar dyn:StrikerBar_C350_2ft ;
    dyn:hasIncidentBar dyn:IncidentBar_C350_6ft ;
    dyn:hasTransmissionBar dyn:TransmissionBar_C350_6ft ;
    
    # Test conditions (modified from template)
    dyn:hasStrikerVelocity 18.5 ;           # User changed from 15.0
    dyn:hasStrikerLength 609.6 ;            # mm (from template)
    dyn:hasIncidentBarLength 1828.8 ;       # mm (from template)
    dyn:hasTransmissionBarLength 1828.8 ;   # mm (from template)
    dyn:hasSamplingRate 2000000.0 ;         # Hz (from template)
    dyn:hasTestTemperature 23.0 ;           # °C (from template)
    dyn:hasLubricationUsed false ;          # (from template)
    dyn:hasPulseShaping false ;             # (from template)
    
    # Strain gauge configuration (from template)
    dyn:hasStrainGauge dyn:StrainGauge_INC_SG1, dyn:StrainGauge_TRA_SG1 ;
    dyn:hasIncidentStrainGaugeDistance 915.0 ;
    dyn:hasTransmissionStrainGaugeDistance 915.0 ;
    dyn:hasGaugeFactor 2.12 ;
    dyn:hasGaugeResistance 350.0 ;
    dyn:hasCalibrationVoltage 5.0 ;
    dyn:hasDataBitResolution 16 ;
    
    # Data files
    dyn:hasRawDataFile dyn:RawData_SHPB_AL6061_001_20250115 ;
    
    # Test validity (to be updated after analysis)
    dyn:hasTestValidity dyn:PendingAnalysis ;
    
    # Metadata
    dyn:hasCreatedBy "DynaMat Platform v2.0" ;
    dyn:hasCreatedDate "2025-01-15T14:30:00"^^xsd:dateTime ;
    dyn:hasNotes "Test conducted with modified striker velocity per plan." .

# Data file metadata
dyn:RawData_SHPB_AL6061_001_20250115 rdf:type dyn:DataFile ;
    dyn:hasFileName "shpb_raw_20250115.csv" ;
    dyn:hasRelativePath "raw/" ;
    dyn:hasFileFormat "CSV" ;
    dyn:hasDelimiter "," ;
    dyn:hasSkipRows 0 ;
    dyn:hasDataColumns "time, incident, reflected, transmitted" ;
    dyn:hasSampleCount 50000 ;
    dyn:hasSamplingRate 2000000.0 .
```

5. CSV file copied to `specimens/SPN-AL6061-001/raw/shpb_raw_20250115.csv`
6. Success message shown to user

**Step 8: Later - Analysis Results**

After SHPB analysis toolkit processes the data:

```turtle
# System updates the test instance with results
dyn:SPN_AL6061_001_SHPB_20250115
    # ... existing properties ...
    
    # Analysis results added
    dyn:hasProcessedDataFile dyn:ProcessedData_SHPB_AL6061_001_20250115 ;
    dyn:hasMaxStress 450.0 ;                # MPa
    dyn:hasYieldStress 380.0 ;              # MPa
    dyn:hasStrainRate 2500.0 ;              # 1/s
    dyn:hasTestValidity dyn:ValidTest ;     # Updated from PendingAnalysis
    dyn:hasEquilibriumAchieved true .

# New data file metadata
dyn:ProcessedData_SHPB_AL6061_001_20250115 rdf:type dyn:DataFile ;
    dyn:hasFileName "stress_strain_20250115.csv" ;
    dyn:hasRelativePath "processed/" ;
    dyn:hasFileFormat "CSV" ;
    dyn:hasDataColumns "strain, stress, strain_rate, time" .
```

### Why This Workflow Works

**For Lab Users**:
- Templates eliminate repetitive data entry
- Form validation catches errors immediately
- No need to learn RDF/TTL syntax
- Can focus on the science, not data management

**For Data Scientists**:
- All metadata queryable via SPARQL
- Standard RDF format enables tool interoperability
- Clear provenance: know exactly what configuration was used
- Can load and analyze multiple experiments programmatically

**For PIs/Collaborators**:
- FAIR-compliant data is shareable
- Templates ensure consistency across lab members
- Easy to understand what was done (readable TTL files)
- Can verify experimental conditions for publications

## Development Guidelines

### Working with the Ontology

**Loading the Ontology**:
```python
from dynamat.ontology import OntologyManager

# Initialize (loads core ontology + all property files automatically)
ontology_manager = OntologyManager()

# Query for information
class_metadata = ontology_manager.get_class_metadata_for_form("dyn:Specimen")
materials = ontology_manager.get_available_individuals("dyn:Material")
```

**Adding New Properties**:
1. Decide which class it belongs to
2. Add to appropriate file in `class_properties/`
3. Include GUI annotations if it should appear in forms
4. Update SHACL shapes in `shapes/` if validation needed

**Creating Templates**:
1. Create TTL file in `templates/{category}/`
2. Define template metadata with `dyn:Template` type
3. Create example instance with typical values
4. Template becomes available in GUI template dropdowns

### Working with the GUI

**GUI is in Version 2.0** (recently refactored):

**Architecture**:
- `gui/core/`: Core functionality (widget creation, form management, data handling)
- `gui/builders/`: Orchestration (form building, layout management)
- `gui/dependencies/`: Advanced features (dependencies, calculations, ID generation)
- `gui/widgets/`: UI components

**Creating a New Form**:
```python
from dynamat.gui import OntologyFormBuilder

form_builder = OntologyFormBuilder(ontology_manager)

# Build form for any ontology class
form = form_builder.build_form("dyn:QuasistaticTest")

# Get data from form
data = form_builder.get_form_data(form)

# Populate form with existing data
form_builder.set_form_data(form, existing_data)
```

The form builder reads the ontology and creates appropriate widgets automatically.

**Dependency System**:

The `DependencyManager` handles field interactions defined in the ontology:

```turtle
# Example: Enable/disable fields based on other fields
dyn:ConstraintEnableLubricationType a dyn:Constraint ;
    dyn:hasSourceProperty dyn:hasLubricationUsed ;
    dyn:hasTargetProperty dyn:hasLubricationType ;
    dyn:hasConstraintType dyn:EnableWhen ;
    dyn:hasTriggerLogic dyn:Equals ;
    dyn:hasTriggerValue true .
```

This constraint means: Enable the "Lubrication Type" field only when "Lubrication Used" is checked.

**Calculation Engine**:

Auto-calculates derived values:

```turtle
# Example: Calculate cross-sectional area from diameter
dyn:CalculationCrossSection a dyn:Calculation ;
    dyn:hasSourceProperty dyn:hasOriginalDiameter ;
    dyn:hasTargetProperty dyn:hasOriginalCrossSection ;
    dyn:hasCalculationType dyn:CircularArea .
```

### Querying Data

**Use DynaMatQueryBuilder for domain-specific queries**:

```python
from dynamat.ontology import create_query_builder

query_builder = create_query_builder(ontology_manager)

# Find all tests for a material
tests = query_builder.find_tests(material="Al6061-T6")

# Find specimens with specific characteristics
specimens = query_builder.find_specimens(
    material="Al6061-T6",
    structure_type="Monolithic",
    has_characterization=True
)

# Get test history for a specimen
history = query_builder.get_specimen_test_history("SPN-AL6061-001")
```

No SPARQL knowledge required—the query builder provides high-level methods.

### Validation Workflow

**Three stages**:

1. **During Data Entry** (Widget-level):
   - Automatic as user types
   - Based on XSD types and min/max constraints

2. **Before Save** (Form-level):
   - Required field checking
   - Field dependency validation
   - Data completeness

3. **On Save** (SHACL-level):
   ```python
   validator = ontology_manager.create_validator()
   report = validator.validate_instance(specimen_graph)
   
   if not report.conforms:
       for result in report.results:
           print(f"{result.severity}: {result.message}")
   ```

## Key Reminders

### Critical Don'ts

**Don't hard-code form fields** - Read from ontology
**Don't mix code and data** - Keep specimens/ separate from dynamat/
**Don't store values with units as strings** - Use proper measurement pattern
**Don't create individual instances in the core ontology** - They go in specimens/ or class_individuals/
**Don't skip validation** - Check SHACL validation tools exists. Do not run it at this time

### Critical Do's

**Do use templates** - Avoid repetition, ensure consistency
**Do include GUI annotations** - Make properties form-friendly
**Do validate at multiple levels** - Widget, form, SHACL
**Do use meaningful URIs** - Follow the established patterns
**Do document design decisions** - Add rdfs:comment to ontology elements

### Common Patterns Recap

**Measurement Pattern**:
```turtle
dyn:hasOriginalLength 10.0 ;
dyn:hasOriginalLengthUnit unit:MilliM .
# OR use qudt:hasQuantityKind for automatic unit handling
```

**Object Property Pattern**:
```turtle
dyn:hasMaterial dyn:Al6061_T6 .  # Links to individual, not literal
```

**File Reference Pattern**:
```turtle
dyn:hasRawDataFile dyn:RawData_123 .
dyn:RawData_123 a dyn:DataFile ;
    dyn:hasFileName "data.csv" ;
    dyn:hasRelativePath "raw/" .
```

**Template Usage Pattern**:
```python
# Load template
template = template_manager.load_template("shpb_standard_setup")

# Instantiate with modifications
test_config = template_manager.instantiate(template, {
    "hasStrikerVelocity": 18.5  # Override default
})
```

## Working with Me (Claude Code)

### When Starting a Session

I can help with:
- Adding new properties to the ontology
- Creating new form widgets
- Implementing validation rules
- Writing SPARQL queries
- Debugging form generation issues
- Creating templates
- Testing the workflow

### What to Tell Me

When asking for help, provide:
- **Which module**: Ontology? GUI? Both?
- **What class/property**: Be specific (e.g., "dyn:Specimen", "dyn:hasOriginalLength")
- **What you're trying to do**: Add field? Modify form? Fix validation?
- **Expected behavior**: What should happen?
- **Current behavior**: What's actually happening?

### Example Interaction

**Good**:
> "I need to add a 'Surface Roughness' property to Specimen class. It should be a numeric value (double) with units in micrometers (Ra). It should appear in the 'Manufacturing' form group and be optional. Can you help me add this to the ontology with proper GUI annotations?"

**Less helpful**:
> "How do I add a property?"

### Testing Your Changes

After modifying the ontology or GUI:

```bash
# Reload ontology in running application
# (OntologyManager.reload_ontology() method)

# Or restart application
python main.py

# Check validation
python -c "
from dynamat.ontology import OntologyManager
om = OntologyManager()
validator = om.create_validator()
# Test your changes
"
```

## Resources

- **Ontology Explorer Notebook**: `guides/Ontology_Explorer.ipynb` - Interactive exploration
- **QUDT Units**: [qudt.org](http://www.qudt.org/) - Unit ontology reference
- **SHACL Spec**: [W3C SHACL](https://www.w3.org/TR/shacl/) - Validation shapes
- **RDFLib Docs**: [rdflib.readthedocs.io](https://rdflib.readthedocs.io/) - Python RDF library

---

**Ready to start working?** Ask me anything about the DynaMat Platform, and let's build something awesome! 🚀
