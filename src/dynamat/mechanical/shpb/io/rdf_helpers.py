"""
RDF Type Conversion Utilities

Provides functions for converting Python types to RDF Literals with explicit XSD datatypes.
Extracted from SHPBTestMetadata for reuse across the io module.
"""

from typing import Any, Dict, Union
import numpy as np
from rdflib import Literal
from rdflib.namespace import XSD


def ensure_typed_literal(value: Any) -> Union[Literal, Any]:
    """
    Convert Python types to RDF Literals with explicit XSD datatypes.

    Ensures all numeric values are saved with proper ^^xsd:datatype flags in TTL.
    Non-numeric types (strings, URIs, dicts) are passed through unchanged.

    Args:
        value: Python value to convert

    Returns:
        RDF Literal with explicit datatype, or original value if not a simple numeric type

    Examples:
        >>> ensure_typed_literal(25000)           # Literal(25000, datatype=XSD.integer)
        >>> ensure_typed_literal(0.35)            # Literal(0.35, datatype=XSD.double)
        >>> ensure_typed_literal("TEST_001")      # "TEST_001" (unchanged)
        >>> ensure_typed_literal(np.int64(100))   # Literal(100, datatype=XSD.integer)
        >>> ensure_typed_literal("12345")         # "12345" (unchanged - strings stay strings)
    """
    # Handle None (pass through)
    if value is None:
        return value

    # Handle NumPy types (convert to native Python types first)
    if isinstance(value, (np.integer, np.int32, np.int64)):
        return Literal(int(value), datatype=XSD.integer)
    if isinstance(value, (np.floating, np.float32, np.float64)):
        return Literal(float(value), datatype=XSD.double)

    # Handle native Python numeric types
    if isinstance(value, bool):
        # Handle bool before int (bool is subclass of int in Python)
        return Literal(value, datatype=XSD.boolean)
    if isinstance(value, int):
        return Literal(value, datatype=XSD.integer)
    if isinstance(value, float):
        return Literal(value, datatype=XSD.double)

    # Pass through everything else (strings, URIs, dicts, lists, etc.)
    # These have their own handling in InstanceWriter
    # NOTE: We do NOT convert string representations of numbers (e.g., "123") to integers here.
    # Values should be properly typed before reaching this method.
    return value


def apply_type_conversion_to_dict(form_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply type conversion to all values in a form dictionary.

    Recursively processes dictionary values to ensure numeric types have explicit XSD datatypes.

    Args:
        form_dict: Dictionary with property URIs as keys

    Returns:
        New dictionary with typed literals for all numeric values

    Examples:
        >>> form = {'dyn:hasStartIndex': 7079, 'dyn:hasEndIndex': 81301}
        >>> typed_form = apply_type_conversion_to_dict(form)
        # Returns: {'dyn:hasStartIndex': Literal(7079, datatype=XSD.integer), ...}
    """
    typed_dict = {}
    for key, value in form_dict.items():
        if value is not None:
            typed_dict[key] = ensure_typed_literal(value)
        else:
            typed_dict[key] = value
    return typed_dict
