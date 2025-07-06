# DynaMat Platform

An integrated ontology-based platform for dynamic materials testing, data management, and analysis.

## Overview

DynaMat Platform provides a comprehensive solution for managing experimental data from dynamic materials testing, focusing on Split-Hopkinson Pressure Bar (SHPB) experiments. The platform uses semantic web technologies (RDF/OWL) to ensure data traceability, reproducibility, and interoperability.

## Features

- **Ontology-based data management** - RDF/OWL ontology for materials science
- **Integrated GUI** - PyQt6-based interface for data entry and visualization  
- **SHPB analysis toolkit** - Automated processing of dynamic test data
- **Structure generation** - Tools for creating lattice structures
- **Material modeling** - Johnson-Cook and other constitutive models
- **Image analysis** - SEM and optical microscopy analysis tools

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/DynaMat-Platform.git
cd DynaMat-Platform

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e.