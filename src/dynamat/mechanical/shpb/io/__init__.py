"""
SHPB IO module for RDF data extraction and test ingestion.

Architecture:
- SHPBTestWriter: Orchestrator delegating RDF generation to InstanceWriter
- StateToInstancesConverter: Converts form-data-driven state to RDF instances
- SpecimenLoader: Bridge to RDF ontology for loading specimen data
- CSVDataHandler: DataFrame validation and CSV file management

Legacy (kept for backward compatibility):
- SHPBTestMetadata: Complete test metadata with all 120+ analysis parameters
- FormDataConverter: Metadata to RDF conversion (replaced by StateToInstancesConverter)

Extracted modules:
- rdf_helpers: Type conversion utilities for RDF Literals
- validity_assessment: ValidityAssessor for test quality assessment
- series_config: SERIES_METADATA constant and DataSeriesBuilder class
"""

from .specimen_loader import SpecimenLoader
from .test_metadata import SHPBTestMetadata
from .csv_data_handler import CSVDataHandler
from .shpb_test_writer import SHPBTestWriter
from .state_instances import StateToInstancesConverter

# Extracted modules
from .rdf_helpers import ensure_typed_literal, apply_type_conversion_to_dict
from .validity_assessment import ValidityAssessor
from .series_config import SERIES_METADATA, DataSeriesBuilder
from .form_conversion import FormDataConverter

__all__ = [
    # Core exports
    'SpecimenLoader',
    'CSVDataHandler',
    'SHPBTestWriter',
    'StateToInstancesConverter',
    # Legacy (backward compat)
    'SHPBTestMetadata',
    'FormDataConverter',
    # Utility exports
    'ensure_typed_literal',
    'apply_type_conversion_to_dict',
    'ValidityAssessor',
    'SERIES_METADATA',
    'DataSeriesBuilder',
]
