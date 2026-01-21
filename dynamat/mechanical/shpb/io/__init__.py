"""
SHPB IO module for RDF data extraction and test ingestion.

Architecture (refactored):
- SHPBTestMetadata: Complete test metadata with all 120+ analysis parameters
- SHPBTestWriter: Thin orchestrator delegating RDF generation to InstanceWriter
- SpecimenLoader: Bridge to RDF ontology for loading specimen data
- CSVDataHandler: DataFrame validation and CSV file management

Extracted modules:
- rdf_helpers: Type conversion utilities for RDF Literals
- validity_assessment: ValidityAssessor for test quality assessment
- series_config: SERIES_METADATA constant and DataSeriesBuilder class
- form_conversion: FormDataConverter for metadata to RDF conversion
"""

from .specimen_loader import SpecimenLoader
from .test_metadata import SHPBTestMetadata
from .csv_data_handler import CSVDataHandler
from .shpb_test_writer import SHPBTestWriter

# New extracted modules
from .rdf_helpers import ensure_typed_literal, apply_type_conversion_to_dict
from .validity_assessment import ValidityAssessor
from .series_config import SERIES_METADATA, DataSeriesBuilder
from .form_conversion import FormDataConverter

__all__ = [
    # Original exports (backwards compatible)
    'SpecimenLoader',
    'SHPBTestMetadata',
    'CSVDataHandler',
    'SHPBTestWriter',
    # New exports from extracted modules
    'ensure_typed_literal',
    'apply_type_conversion_to_dict',
    'ValidityAssessor',
    'SERIES_METADATA',
    'DataSeriesBuilder',
    'FormDataConverter',
]
