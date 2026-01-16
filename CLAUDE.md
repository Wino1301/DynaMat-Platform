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
│   │   ├── core/              # Core ontology definition (DynaMat_core.ttl)
│   │   ├── class_properties/  # Property definitions by class
│   │   ├── class_individuals/ # Predefined individuals (materials, equipment)
│   │   ├── shapes/            # SHACL validation shapes
│   │   ├── templates/         # Reusable configurations
│   │   └── manager.py         # OntologyManager (main interface)
│   │
│   ├── gui/                   # PyQt6 interface (v2.0 refactored)
│   │   ├── core/              # Widget factory, form manager, data handler
│   │   ├── builders/          # Form building, layout management
│   │   ├── dependencies/      # Dependency manager, calculation engine
│   │   └── widgets/           # UI components
│   │
│   └── config.py              # Configuration
│
├── user_data/                  # User data directory (SEPARATE from code)
│   ├── specimens/             # Specimen data database
│   │   └── DYNML-{MaterialCode}-{XXXXX}/
│   │       ├── DYNML-*_specimen.ttl
│   │       ├── DYNML-*_TEST_DATE.ttl
│   │       ├── raw/           # Raw data files
│   │       └── processed/     # Processed results
│   │
│   └── individuals/           # User-defined individuals
│
├── .claude/
│   └── agents/
│       └── ontology-semantic-validator.md  # Ontology validation guide
│
├── guides/                     # Jupyter notebooks
├── main.py                     # Application entry point
└── requirements.txt
```

### Why User Data is Separate from Code

The `user_data/` directory is intentionally **outside** the `dynamat/` package:

**FAIR Data Management**:
- **Version Control**: User data (specimens, custom individuals) evolves differently than code
- **Data Portability**: Labs can share datasets by copying the `user_data/` folder
- **Tool Independence**: Any RDF tool can read `user_data/specimens/` and `user_data/individuals/`
- **Scalability**: Data growth doesn't bloat the code repository

**File Organization**:
- `user_data/specimens/`: Each specimen gets its own folder (e.g., `DYNML-A356-00001/`) with TTL metadata files and CSV data files organized by processing stage
- `user_data/individuals/`: User-defined individuals (custom materials, equipment configurations, etc.)

## How It Works: Ontology → GUI

### The Core Concept

```
1. Define properties in ontology with GUI annotations
2. OntologyManager reads the definitions
3. GUI automatically generates appropriate forms
4. User fills forms → saves as RDF/TTL
5. Data is queryable, shareable, and FAIR-compliant
```

### Form Generation Flow

```
User requests form for "dyn:Specimen"
        ↓
OntologyManager reads class properties
  → Finds properties with domain dyn:Specimen
  → Reads GUI annotations (display name, form group, order)
  → Infers widget types from data types
        ↓
WidgetFactory creates appropriate widgets
  → xsd:double + qudt:hasQuantityKind → UnitValueWidget
  → xsd:string → Text input
  → owl:ObjectProperty → Dropdown with individuals
        ↓
LayoutManager arranges widgets into grouped sections
        ↓
Form appears with proper labels, order, and validation
```

**The beauty**: Change the ontology annotations, reload the application, and the form automatically updates. No GUI code to modify.

### Key GUI Annotations

Properties need these annotations to appear in forms:
- `gui:hasDisplayName` - Label shown to user
- `gui:hasFormGroup` - Which section of the form
- `gui:hasGroupOrder` - Order of sections
- `gui:hasDisplayOrder` - Order within section

For measurements (values with units):
- `qudt:hasQuantityKind` - Type of measurement (Length, Mass, etc.)
- `dyn:hasUnit` - Unit for the measurement

**See `.claude/agents/ontology-semantic-validator.md` for detailed ontology patterns and validation requirements.**

## Example Workflow: Creating an SHPB Test

**Step 1**: User opens "Mechanical Test" tab → "New Test"

**Step 2**: Selects test type (SHPB Compression)

**Step 3**: Optionally selects template (e.g., "Standard C350 Setup")
- Form auto-populates with standard equipment and parameters
- User can modify any field

**Step 4**: Fills required fields
- Test ID (auto-generated)
- Specimen selection
- Date, operator

**Step 5**: Links data files
- Selects CSV file with raw signals
- System validates columns

**Step 6**: Real-time validation
- Widget-level: Data types, ranges
- Form-level: Required fields
- SHACL-level: Complex constraints

**Step 7**: Saves
- System generates TTL file in `user_data/specimens/` directory
- Copies data files to appropriate subdirectories
- All metadata is now queryable via SPARQL

## Development Guidelines

### Working with the Ontology

**Loading the Ontology**:
```python
from dynamat.ontology import OntologyManager

ontology_manager = OntologyManager()
class_metadata = ontology_manager.get_class_metadata_for_form("dyn:Specimen")
materials = ontology_manager.get_available_individuals("dyn:Material")
```

**Adding New Properties**:
1. Add to appropriate file in `class_properties/`
2. Include GUI annotations for form display
3. Update SHACL shapes if validation needed
4. See ontology-semantic-validator agent for detailed guidance

**For ontology work**, use the ontology-semantic-validator agent (`.claude/agents/ontology-semantic-validator.md`) which provides:
- Detailed validation checklists
- Property pattern examples
- GUI annotation requirements
- Common issues to catch

### Working with the GUI

**GUI Architecture** (v2.0):
- `gui/core/`: Core functionality (widget creation, form management)
- `gui/builders/`: Form building orchestration
- `gui/dependencies/`: Field dependencies and calculations
- `gui/widgets/`: UI components

**Creating a Form**:
```python
from dynamat.gui import OntologyFormBuilder

form_builder = OntologyFormBuilder(ontology_manager)
form = form_builder.build_form("dyn:Specimen")
data = form_builder.get_form_data(form)
```

The form builder reads the ontology and creates appropriate widgets automatically.

**Dependency System**:
The DependencyManager handles field interactions defined in the ontology (e.g., enable field B when field A is checked).

**Calculation Engine**:
Auto-calculates derived values (e.g., cross-sectional area from diameter).

### Querying Data

```python
from dynamat.ontology import create_query_builder

query_builder = create_query_builder(ontology_manager)

# Find all tests for a material
tests = query_builder.find_tests(material="Al6061-T6")

# Find specimens with specific characteristics
specimens = query_builder.find_specimens(
    material="Al6061-T6",
    structure_type="Monolithic"
)

# Get test history for a specimen
history = query_builder.get_specimen_test_history("SPN-AL6061-001")
```

### Validation Workflow

**Three stages**:

1. **Widget-Level** (immediate as user types)
   - Data type checking
   - Range validation

2. **Form-Level** (before save)
   - Required fields
   - Field dependencies
   - Completeness

3. **SHACL Validation** (on save)
   - Complex constraints
   - Pattern matching
   - Cross-field rules

## Key Patterns

### The Measurement Pattern

Store measurements with proper units:

```turtle
# WRONG - loses semantic meaning
dyn:SPN_001 dyn:hasLength "10.0 mm" .

# RIGHT - structured and queryable
dyn:hasOriginalLength rdf:type owl:DatatypeProperty ;
    qudt:hasQuantityKind qkdv:Length ;
    dyn:hasUnit "unit:MilliM" .
```

The GUI automatically creates a UnitValueWidget when it sees `qudt:hasQuantityKind`.

### Individual vs. Literal Values

**Use individuals** (separate TTL entries) for:
- Materials (reused across specimens)
- Equipment (shared resources)
- Standard configurations

**Use literal values** (properties on instances) for:
- Measurements specific to one specimen
- Test conditions that vary
- Timestamps, IDs, descriptions

### File Naming Conventions

- Specimen files: `SPN-{MaterialCode}-{Number}_specimen.ttl`
- Test files: `SPN-{MaterialCode}-{Number}_{TestType}_{Date}.ttl`
- Data files: `{description}_{date}.csv` in `raw/` or `processed/`

## Critical Reminders

### Don't:
- Hard-code form fields (read from ontology)
- Mix code and data (keep user_data/ separate)
- Store values with units as strings (use measurement pattern)
- Create instances in core ontology (they go in user_data/specimens/ or class_individuals/)

### Do:
- Use templates for consistency
- Include GUI annotations for form-friendly properties
- Validate at multiple levels
- Use meaningful URIs following established patterns
- Document design decisions with rdfs:comment

## Debugging with Claude Code

When you encounter issues:

**Tell me**:
- What you expected to happen
- What actually happened
- Any error messages

**I will**:
- Read relevant ontology files directly
- Check GUI code for issues
- Find root cause
- Provide fixes following existing patterns

I have access to Read, Grep, and Edit tools - no special infrastructure needed. Just describe the problem clearly.

## Specialized Agents

### Code Tutor (Learning Mode)

For implementing features yourself with guidance rather than auto-implementation, use the **code-tutor-guide agent**.

**When to use**:
- You want to implement features yourself to learn
- Adding new functionality and want structured guidance
- Debugging issues and want to understand the process
- Maintaining deep understanding of your own codebase

**What it provides**:
- Implementation plans with specific file locations
- References to existing code patterns
- Step-by-step technical guidance
- Code review without auto-fixing

**Example**: "Guide me through adding a surface roughness property" → Agent provides implementation steps, points to template code, reviews your implementation

See `.claude/agents/code-tutor-guide.md` for details.

### Ontology Validator

For ontology-related validation and semantic correctness, reference the **ontology-semantic-validator agent**.

**When to use**:
- Validating property definitions
- Checking GUI annotation completeness
- Ensuring semantic correctness
- Verifying pattern compliance

**What it provides**:
- Detailed validation checklists
- Property definition patterns
- GUI annotation specifications
- Common issues and solutions

See `.claude/agents/ontology-semantic-validator.md` for details.

### When to Ask for Help

**Good questions**:
- "Why isn't this property showing up in the form?"
- "How do I add a measurement property with units?"
- "The widget type is wrong for my field - how do I fix it?"
- "Guide me through implementing [feature]" (triggers code-tutor)

**What to provide**:
- Which module (Ontology? GUI? Both?)
- Specific class/property names
- Expected vs. actual behavior
- Error messages if any
- Whether you want direct solution or guided implementation

## Resources

- **Ontology Validator Agent**: `.claude/agents/ontology-semantic-validator.md` - Detailed ontology guidance
- **Ontology Explorer**: `guides/Ontology_Explorer.ipynb` - Interactive exploration
- **QUDT Units**: [qudt.org](http://www.qudt.org/) - Unit ontology reference
- **SHACL Spec**: [W3C SHACL](https://www.w3.org/TR/shacl/) - Validation shapes
- **RDFLib Docs**: [rdflib.readthedocs.io](https://rdflib.readthedocs.io/) - Python RDF library

---

**Ready to start working?** Ask me anything about the DynaMat Platform. For ontology-specific work, I'll reference the ontology-semantic-validator agent to ensure proper validation and patterns.
