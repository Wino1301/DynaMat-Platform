# DynaMat Platform Context

## Project Overview
DynaMat Platform is an integrated, ontology-driven desktop application for dynamic materials testing, specifically focusing on Split-Hopkinson Pressure Bar (SHPB) experiments. It leverages semantic web technologies (RDF/OWL/SHACL) to ensure data traceability, reproducibility, and interoperability (FAIR data principles).

**Core Philosophy:** "Ontology-First Design". The GUI and data structures are dynamically generated from RDF ontology definitions rather than hard-coded.

### Key Features
*   **Ontology-Driven GUI:** Forms and validation rules are generated from RDF metadata.
*   **SHPB Analysis:** Toolkit for automated processing of dynamic test data (pulse detection, alignment, stress-strain calculation).
*   **FAIR Data:** Data stored as RDF/TTL with standard vocabularies (QUDT).
*   **Modular Architecture:** Separation of Ontology, GUI, and Analysis logic.

## Technical Stack
*   **Language:** Python 3.11+
*   **GUI Framework:** PyQt6
*   **Data/Ontology:** RDFLib, SHACL, QUDT (Units)
*   **Scientific Stack:** NumPy, SciPy, Matplotlib, Plotly

## Project Structure
*   `dynamat/`: Main package source.
    *   `ontology/`: Core ontology engine, definitions (`.ttl` files), query builder, and validation.
    *   `gui/`: PyQt6 application logic, widget factory, and form builders.
    *   `mechanical/`: Physics/engineering analysis modules (e.g., `shpb`).
*   `user_data/`: **External** directory for user data (specimens, tests), keeping it separate from code.
*   `tools/`: scripts for validation, testing, and maintenance.
*   `tests/`: Unit tests.
*   `notebooks/`: Jupyter notebooks for research and analysis.
*   `main.py`: Application entry point.

## Setup & Running

### Installation
1.  **Environment:** Create a conda environment using `environment.yml`:
    ```bash
    conda env create -f environment.yml
    conda activate pinn311
    ```
2.  **Install Package:** Install in editable mode:
    ```bash
    pip install -e .
    ```

### Execution
*   **Launch GUI:**
    ```bash
    python main.py
    ```
*   **Command Line Options:**
    *   `python main.py --help`: Show help.
    *   `python main.py --validate`: Run ontology validation only.
    *   `python main.py --debug`: Enable debug logging.
    *   `python main.py --nogui`: Run in CLI mode.

## Development Workflows

### 1. Modifying the Ontology (Forms & Data Structure)
*   **Do not hard-code forms.** Instead, modify the `.ttl` files in `dynamat/ontology/class_properties/`.
*   **GUI Annotations:** Use `gui:hasDisplayName`, `gui:hasFormGroup`, `gui:hasDisplayOrder` to control form rendering.
*   **Validation:** Use `python main.py --validate` or `python tools/validate_ttl.py` to check ontology integrity.

### 2. Testing & Validation
*   **Integration Tests:**
    ```bash
    python tools/test_statistics_workflow.py
    python tools/test_instance_index.py
    python tools/test_plot_widgets.py
    ```
*   **Data Validation:**
    ```bash
    python tools/validate_ttl.py user_data/specimens/<specimen_dir>/
    ```
*   **Constraint Validation:**
    ```bash
    python tools/validate_constraints.py
    ```

### 3. Adding Features
*   **GUI Widgets:** Extend `dynamat.gui.core.widget_factory.WidgetFactory`.
*   **Calculations:** Register new functions in `dynamat.gui.dependencies.calculation_engine.CalculationEngine`.
*   **Analysis:** Implement physics logic in `dynamat/mechanical/`.

## Important References
*   `CLAUDE.md`: Comprehensive guide on project philosophy and development patterns.
*   `dynamat/gui/README.md`: Detailed architecture of the GUI module.
*   `dynamat/ontology/README.md`: Guide to the ontology engine.
*   `dynamat/mechanical/shpb/core/README.md`: SHPB signal processing pipeline docs.
