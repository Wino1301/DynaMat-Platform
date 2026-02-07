"""
DynaMat Platform - Raw Data Loader Configuration
Configuration dataclass for RawDataLoaderWidget.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple


@dataclass
class RawDataLoaderConfig:
    """
    Configuration for RawDataLoaderWidget.

    Supports two modes:
    1. Ontology-driven: Provide test_class_uri, widget queries dyn:hasRawSeries
    2. Manual: Provide required_series list directly

    Attributes:
        test_class_uri: URI of the test class (e.g., "dyn:SHPBCompression").
            When set, the widget queries the ontology for required series.
        required_series: Manual list of required series definitions.
            Each dict has keys: key, label, default_column, quantity_kind, unit.
        file_filters: File dialog filter string.
        default_directory: Initial directory for file browser.
        separator_options: List of (display_name, separator_value) tuples.
        preview_rows: Number of rows to show in preview table.

    Example:
        >>> # Ontology-driven mode
        >>> config = RawDataLoaderConfig(
        ...     test_class_uri="dyn:SHPBCompression"
        ... )
        >>> widget = RawDataLoaderWidget(config, ontology_manager, qudt_manager)

        >>> # Manual mode
        >>> config = RawDataLoaderConfig(
        ...     required_series=[
        ...         {'key': 'time', 'label': 'Time', 'default_column': 'time',
        ...          'quantity_kind': 'http://qudt.org/vocab/quantitykind/Time',
        ...          'unit': 'http://qudt.org/vocab/unit/MilliSEC'},
        ...     ]
        ... )
    """

    # Ontology-driven mode
    test_class_uri: Optional[str] = None

    # Manual mode fallback
    required_series: Optional[List[Dict[str, Any]]] = None

    # File handling
    file_filters: str = "CSV Files (*.csv);;Text Files (*.txt);;Excel Files (*.xlsx);;All Files (*)"
    default_directory: Optional[Path] = None
    separator_options: Optional[List[Tuple[str, str]]] = None

    # Display
    preview_rows: int = 10

    def __post_init__(self):
        if self.test_class_uri is None and self.required_series is None:
            raise ValueError(
                "RawDataLoaderConfig requires either test_class_uri or required_series"
            )
        if self.separator_options is None:
            self.separator_options = [
                ("Comma (,)", ","),
                ("Tab (\\t)", "\t"),
                ("Semicolon (;)", ";"),
                ("Space", " "),
            ]
