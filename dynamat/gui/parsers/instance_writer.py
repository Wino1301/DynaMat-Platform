"""
DynaMat Platform - Instance Writer
Converts GUI form data to TTL files with automatic unit conversion

This is the SINGLE point where unit conversion happens during save operations.
Converts values from user-selected units to ontology-defined storage units (dyn:hasUnit).
"""

import logging
from pathlib import Path
from typing import Dict, Any, Union, Optional, Tuple
from datetime import datetime

from rdflib import Graph, URIRef, Literal, Namespace, BNode
from rdflib.namespace import RDF, RDFS, OWL, XSD

from ..core.form_validator import SHACLValidator, ValidationResult

logger = logging.getLogger(__name__)


class InstanceWriter:
    """
    Writes GUI form data to TTL files with automatic QUDT unit conversion and SHACL validation.

    Responsibilities:
    - Convert form data dictionary to RDF graph
    - Handle unit conversion using QUDT for measurement properties
    - Validate RDF graph using SHACL shapes before saving
    - Serialize graph to TTL format
    - Save to specified file path

    Unit Conversion Strategy:
    - UnitValueWidget provides: {'value': X, 'unit': user_unit, 'reference_unit': storage_unit}
    - If user_unit != storage_unit, convert using QUDTManager
    - Store ONLY the converted numeric value (float) in TTL
    - Unit information preserved in ontology via dyn:hasUnit

    Validation Strategy:
    - After creating RDF graph (with unit conversion), validate using SHACL shapes
    - If blocking violations exist, return None (save aborted)
    - If only warnings/infos, return path and validation_result (caller handles user confirmation)
    """

    def __init__(self, ontology_manager, qudt_manager=None):
        """
        Initialize instance writer.

        Args:
            ontology_manager: OntologyManager for namespace access
            qudt_manager: QUDTManager for unit conversions (optional but recommended)
        """
        self.ontology = ontology_manager
        self.qudt = qudt_manager

        # Get namespace manager
        self.ns_manager = ontology_manager.namespace_manager if hasattr(ontology_manager, 'namespace_manager') else None

        # Standard namespaces
        self.DYN = Namespace("https://dynamat.utep.edu/ontology#")
        self.GUI = Namespace("https://dynamat.utep.edu/ontology/gui#")
        self.QUDT = Namespace("http://qudt.org/schema/qudt/")
        self.UNIT = Namespace("http://qudt.org/vocab/unit/")
        self.QKDV = Namespace("http://qudt.org/vocab/quantitykind/")

        # Initialize SHACL validator
        self.validator = SHACLValidator(ontology_manager)

        logger.info("InstanceWriter initialized with QUDT unit conversion and SHACL validation support")

    def write_instance(self,
                      form_data: Dict[str, Any],
                      class_uri: str,
                      instance_id: str,
                      output_path: Path,
                      additional_triples: list = None,
                      skip_validation: bool = False) -> Tuple[Optional[str], ValidationResult]:
        """
        Write form data to a TTL file with unit conversion and SHACL validation.

        Args:
            form_data: Dictionary from FormDataHandler (property_uri -> widget_value)
            class_uri: RDF class URI (e.g., "dyn:Specimen", "dyn:MechanicalTest")
            instance_id: Instance identifier (e.g., "DYNML-AL6061-001")
            output_path: Path where TTL file will be saved
            additional_triples: Optional list of (subject, predicate, object) tuples to add
            skip_validation: If True, skip SHACL validation (for testing)

        Returns:
            Tuple of (saved_file_path, validation_result):
            - saved_file_path: Path to saved file, or None if save was blocked by validation
            - validation_result: SHACL validation result with violations/warnings/infos

        Example:
            >>> writer = InstanceWriter(ontology_manager, qudt_manager)
            >>> data = {
            ...     'dyn:hasOriginalLength': {'value': 10.0, 'unit': 'unit:IN', 'reference_unit': 'unit:MilliM'},
            ...     'dyn:hasSpecimenID': 'DYNML-AL6061-001',
            ...     'dyn:hasMaterial': 'dyn:Al6061_T6'
            ... }
            >>> path, validation_result = writer.write_instance(
            ...     form_data=data,
            ...     class_uri='dyn:Specimen',
            ...     instance_id='DYNML_AL6061_001',
            ...     output_path=Path('specimens/DYNML-AL6061-001/DYNML-AL6061-001_specimen.ttl')
            ... )
            >>> if path:
            ...     print(f"Saved to {path}")
            >>> if validation_result.has_any_issues():
            ...     # Caller can display ValidationResultsDialog here
            ...     pass
        """
        try:
            # Create RDF graph
            graph = Graph()
            self._setup_namespaces(graph)

            # Create instance URI
            instance_uri = self._create_instance_uri(instance_id)
            instance_ref = URIRef(instance_uri)

            # Add type assertion
            class_ref = self._resolve_uri(class_uri)
            graph.add((instance_ref, RDF.type, class_ref))

            # Process each property from form data
            for property_uri, value in form_data.items():
                if value is None or value == "":
                    continue  # Skip empty values

                property_ref = self._resolve_uri(property_uri)
                rdf_value = self._convert_to_rdf_value(value)

                graph.add((instance_ref, property_ref, rdf_value))

            # Add any additional triples
            if additional_triples:
                for subject, predicate, obj in additional_triples:
                    graph.add((subject, predicate, obj))

            # Validate RDF graph with SHACL (after unit conversion, before save)
            validation_result = self._validate_instance_graph(graph, skip_validation)

            # Check validation result - return immediately if blocking violations exist
            if validation_result.has_blocking_issues():
                logger.warning(f"Validation failed with {len(validation_result.violations)} violation(s). Save blocked.")
                return None, validation_result

            # If warnings/infos exist, caller can handle showing dialog
            # We continue here, but caller may cancel based on user choice

            # Ensure output directory exists
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Serialize to TTL
            self._save_graph(graph, output_path)

            logger.info(f"Instance {instance_id} written to {output_path}")
            return str(output_path), validation_result

        except Exception as e:
            logger.error(f"Failed to write instance {instance_id}: {e}", exc_info=True)
            raise

    def _validate_instance_graph(self, graph: Graph, skip_validation: bool = False) -> ValidationResult:
        """
        Validate RDF instance graph with SHACL shapes.

        Args:
            graph: RDF graph containing the instance data
            skip_validation: If True, skip validation (for testing)

        Returns:
            ValidationResult with violations, warnings, and infos
        """
        if skip_validation:
            logger.debug("SHACL validation skipped (skip_validation=True)")
            return ValidationResult(conforms=True, raw_report="Validation skipped")

        logger.info("Running SHACL validation on instance graph...")
        validation_result = self.validator.validate(graph)

        # Log validation summary
        if validation_result.conforms:
            logger.info("✓ SHACL validation passed")
        else:
            logger.warning(f"✗ SHACL validation found issues: {validation_result.get_summary()}")

        return validation_result

    def _convert_to_rdf_value(self, value: Any) -> Union[URIRef, Literal]:
        """
        Convert Python/form value to RDF value with unit conversion.

        This is the CORE method where unit conversion happens!

        Args:
            value: Value from form widget (could be dict with units, string, number, etc.)

        Returns:
            RDF URIRef or Literal ready for graph insertion
        """
        # === UNIT CONVERSION LOGIC ===
        # Check if this is a unit-value dictionary from UnitValueWidget
        if isinstance(value, dict) and 'value' in value and 'unit' in value and 'reference_unit' in value:
            numeric_value = value['value']
            user_unit = value['unit']  # Unit selected by user in dropdown
            reference_unit = value['reference_unit']  # dyn:hasUnit from ontology (storage unit)

            # Perform unit conversion if units differ (URI-level comparison)
            if user_unit and reference_unit and user_unit != reference_unit and self.qudt:
                try:
                    # Convert from user's unit to ontology-defined storage unit
                    converted_value = self.qudt.convert_value(
                        value=numeric_value,
                        from_unit_uri=user_unit,
                        to_unit_uri=reference_unit
                    )

                    logger.info(
                        f"Unit conversion: {numeric_value} ({user_unit}) → "
                        f"{converted_value:.6f} ({reference_unit})"
                    )

                    return Literal(converted_value, datatype=XSD.double)

                except Exception as e:
                    logger.warning(
                        f"Unit conversion failed ({user_unit} → {reference_unit}): {e}. "
                        f"Storing original value."
                    )
                    # Fallback: store original value if conversion fails
                    return Literal(numeric_value, datatype=XSD.double)
            else:
                # No conversion needed (same unit, missing info, or no QUDT manager)
                return Literal(numeric_value, datatype=XSD.double)

        # === STANDARD TYPE CONVERSIONS (no units) ===
        elif isinstance(value, str):
            # Check if it's a URI or a literal string
            if value.startswith("http") or value.startswith("dyn:") or value.startswith("unit:"):
                return self._resolve_uri(value)
            else:
                return Literal(value, datatype=XSD.string)

        elif isinstance(value, bool):
            return Literal(value, datatype=XSD.boolean)

        elif isinstance(value, int):
            return Literal(value, datatype=XSD.integer)

        elif isinstance(value, float):
            return Literal(value, datatype=XSD.double)

        elif isinstance(value, datetime):
            return Literal(value.isoformat(), datatype=XSD.dateTime)

        elif hasattr(value, 'isoformat'):  # date objects
            return Literal(value.isoformat(), datatype=XSD.date)

        else:
            # Default: convert to string
            logger.warning(f"Unknown value type {type(value)}, converting to string")
            return Literal(str(value))

    def _setup_namespaces(self, graph: Graph):
        """Setup standard namespaces for the graph."""
        if self.ns_manager:
            # Use namespace manager if available
            self.ns_manager.setup_graph_namespaces(graph)
        else:
            # Fallback: manually bind common namespaces
            graph.bind("dyn", self.DYN)
            graph.bind("gui", self.GUI)
            graph.bind("rdf", RDF)
            graph.bind("rdfs", RDFS)
            graph.bind("owl", OWL)
            graph.bind("xsd", XSD)
            graph.bind("qudt", self.QUDT)
            graph.bind("unit", self.UNIT)
            graph.bind("qkdv", self.QKDV)

    def _create_instance_uri(self, instance_id: str) -> str:
        """Create full URI for instance."""
        # Clean instance ID (remove special characters if needed)
        clean_id = instance_id.replace(" ", "_").replace("-", "_")
        return str(self.DYN[clean_id])

    def _resolve_uri(self, uri_string: str) -> URIRef:
        """Resolve prefixed URI to full URI."""
        if uri_string.startswith("http"):
            return URIRef(uri_string)
        elif ":" in uri_string:
            prefix, local = uri_string.split(":", 1)
            if prefix == "dyn":
                return URIRef(self.DYN[local])
            elif prefix == "unit":
                return URIRef(self.UNIT[local])
            elif prefix == "qkdv":
                return URIRef(self.QKDV[local])
            elif prefix == "gui":
                return URIRef(self.GUI[local])
            else:
                # Unknown prefix, return as-is
                return URIRef(uri_string)
        else:
            # No prefix, assume dyn namespace
            return URIRef(self.DYN[uri_string])

    def _save_graph(self, graph: Graph, output_path: Path):
        """Serialize and save graph to TTL file."""
        try:
            # Serialize with nice formatting
            ttl_content = graph.serialize(format='turtle')

            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(ttl_content)

            logger.debug(f"Graph serialized to {output_path} ({len(graph)} triples)")

        except Exception as e:
            logger.error(f"Failed to save graph to {output_path}: {e}")
            raise

    def update_instance(self,
                       instance_uri: str,
                       updates: Dict[str, Any],
                       ttl_file: Path,
                       skip_validation: bool = False) -> Tuple[Optional[str], ValidationResult]:
        """
        Update existing instance by loading TTL, modifying, and re-saving with validation.

        Args:
            instance_uri: URI of instance to update
            updates: Dictionary of property_uri -> new_value
            ttl_file: Path to existing TTL file
            skip_validation: If True, skip SHACL validation (for testing)

        Returns:
            Tuple of (saved_file_path, validation_result):
            - saved_file_path: Path to saved file, or None if save was blocked by validation
            - validation_result: SHACL validation result
        """
        try:
            # Load existing graph
            graph = Graph()
            graph.parse(ttl_file, format='turtle')
            self._setup_namespaces(graph)

            instance_ref = self._resolve_uri(instance_uri)

            # Update each property
            for property_uri, new_value in updates.items():
                property_ref = self._resolve_uri(property_uri)

                # Remove old triples
                graph.remove((instance_ref, property_ref, None))

                # Add new value
                if new_value is not None and new_value != "":
                    rdf_value = self._convert_to_rdf_value(new_value)
                    graph.add((instance_ref, property_ref, rdf_value))

            # Validate updated graph with SHACL
            validation_result = self._validate_instance_graph(graph, skip_validation)

            # Check validation result - return immediately if blocking violations exist
            if validation_result.has_blocking_issues():
                logger.warning(f"Validation failed with {len(validation_result.violations)} violation(s). Update blocked.")
                return None, validation_result

            # Save updated graph
            self._save_graph(graph, ttl_file)

            logger.info(f"Instance {instance_uri} updated in {ttl_file}")
            return str(ttl_file), validation_result

        except Exception as e:
            logger.error(f"Failed to update instance {instance_uri}: {e}", exc_info=True)
            raise
