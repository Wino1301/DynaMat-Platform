"""Converts GUI form data to TTL files with automatic unit conversion and SHACL validation."""

import logging
from pathlib import Path
from typing import Dict, Any, Union, Optional, Tuple
from datetime import datetime, date

from rdflib import Graph, URIRef, Literal, Namespace, BNode
from rdflib.namespace import RDF, RDFS, OWL, XSD

from ..core.form_validator import SHACLValidator, ValidationResult

logger = logging.getLogger(__name__)


class InstanceWriter:
    """
    Writes GUI form data to TTL files with QUDT unit conversion and SHACL validation.
    Converts values from user-selected units to ontology-defined storage units.
    """

    def __init__(self, ontology_manager, qudt_manager=None):
        """
        Args:
            ontology_manager: OntologyManager for namespace access
            qudt_manager: QUDTManager for unit conversions (optional)
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
            class_uri: RDF class URI (e.g., "dyn:Specimen")
            instance_id: Instance identifier (e.g., "DYNML-AL6061-001")
            output_path: Path where TTL file will be saved
            additional_triples: Optional list of (subject, predicate, object) tuples
            skip_validation: If True, skip SHACL validation

        Returns:
            Tuple of (saved_file_path or None if blocked, ValidationResult)
        """
        try:
            # Create RDF graph
            graph = Graph()
            self._setup_namespaces(graph)

            # Create instance using extracted method (DRY principle)
            instance_ref = self.create_single_instance(graph, form_data, class_uri, instance_id)

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
        """Validate RDF instance graph with SHACL shapes."""
        if skip_validation:
            logger.debug("SHACL validation skipped (skip_validation=True)")
            return ValidationResult(conforms=True, raw_report="Validation skipped")

        logger.info("Running SHACL validation on instance graph...")
        validation_result = self.validator.validate(graph)

        # Log validation summary
        if validation_result.conforms:
            logger.info("SHACL validation passed")
        else:
            logger.warning(f"SHACL validation found issues: {validation_result.get_summary()}")

        return validation_result

    def _convert_to_rdf_value(self, value: Any) -> Union[URIRef, Literal]:
        """Convert Python/form value to RDF value.

        NOTE: Measurement dicts (dict with 'value' key) are handled by
        _create_quantity_value() in create_single_instance(), not here.
        """
        # Pass through already-typed literals unchanged
        if isinstance(value, Literal):
            return value

        # Standard type conversions
        elif isinstance(value, str):
            # Check if it's a URI
            if value.startswith("http") or value.startswith("dyn:") or value.startswith("unit:") or value.startswith("qkdv:"):
                return self._resolve_uri(value)
            # ISO datetime string - store as xsd:dateTime
            elif 'T' in value and len(value) > 10:
                try:
                    # Validate as ISO datetime
                    datetime.fromisoformat(value)
                    return Literal(value, datatype=XSD.dateTime)
                except (ValueError, AttributeError):
                    pass
            # Date string (YYYY-MM-DD format)
            if len(value) == 10 and value.count('-') == 2:
                try:
                    # Validate it's a proper date
                    datetime.strptime(value, "%Y-%m-%d")
                    return Literal(value, datatype=XSD.date)
                except ValueError:
                    return Literal(value, datatype=XSD.string)
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

        elif hasattr(value, 'isoformat'):
            return Literal(value.isoformat(), datatype=XSD.date)

        else:
            logger.warning(f"Unknown value type {type(value)}, converting to string")
            return Literal(str(value))

    def _setup_namespaces(self, graph: Graph):
        """Setup standard namespaces for the graph."""
        if self.ns_manager:
            self.ns_manager.setup_graph_namespaces(graph)
        else:
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
        """Create full URI for instance from ID."""
        clean_id = instance_id.replace(" ", "_").replace("-", "_")
        return str(self.DYN[clean_id])

    def _resolve_uri(self, uri_string: str) -> URIRef:
        """Resolve prefixed URI to full URIRef."""
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
                return URIRef(uri_string)
        else:
            return URIRef(self.DYN[uri_string])

    def _is_measurement_dict(self, value: Any) -> bool:
        """Check if value is a measurement dictionary from UnitValueWidget."""
        return isinstance(value, dict) and 'value' in value

    def _create_quantity_value(self, graph: Graph, value_dict: dict,
                               property_uri: str = None) -> BNode:
        """
        Create a qudt:QuantityValue blank node from a measurement dictionary.

        Performs unit conversion if user's selected unit differs from ontology default,
        then serializes as a structured QuantityValue with numericValue, unit, and
        hasQuantityKind.

        Args:
            graph: RDF graph to add BNode triples to
            value_dict: Measurement dict with keys: value, unit, reference_unit,
                        quantity_kind (optional)
            property_uri: Property URI for quantity_kind fallback lookup

        Returns:
            BNode representing the QuantityValue
        """
        numeric_value = value_dict['value']
        user_unit = value_dict.get('unit')
        reference_unit = value_dict.get('reference_unit')
        quantity_kind = value_dict.get('quantity_kind')

        # Perform unit conversion if units differ
        stored_value = numeric_value
        stored_unit = user_unit or reference_unit
        if user_unit and reference_unit and user_unit != reference_unit and self.qudt:
            try:
                stored_value = self.qudt.convert_value(
                    value=numeric_value,
                    from_unit_uri=user_unit,
                    to_unit_uri=reference_unit
                )
                stored_unit = reference_unit
                logger.info(
                    f"Unit conversion: {numeric_value} ({user_unit}) -> "
                    f"{stored_value:.6f} ({reference_unit})"
                )
            except Exception as e:
                logger.warning(f"Unit conversion failed ({user_unit} -> {reference_unit}): {e}")
                stored_unit = user_unit
        elif reference_unit:
            stored_unit = reference_unit

        # Fallback: look up quantity_kind from ontology if not in dict
        if not quantity_kind and property_uri:
            quantity_kind = self._get_quantity_kind_for_property(property_uri)

        # Create QuantityValue blank node
        bnode = BNode()
        graph.add((bnode, RDF.type, self.QUDT.QuantityValue))
        graph.add((bnode, self.QUDT.numericValue,
                   Literal(float(stored_value), datatype=XSD.double)))

        if stored_unit:
            unit_ref = self._resolve_uri(stored_unit)
            graph.add((bnode, self.QUDT.unit, unit_ref))

        if quantity_kind:
            qk_ref = self._resolve_uri(quantity_kind)
            graph.add((bnode, self.QUDT.hasQuantityKind, qk_ref))

        # Optional: standard uncertainty
        uncertainty = value_dict.get('uncertainty')
        if uncertainty is not None:
            graph.add((bnode, self.QUDT.standardUncertainty,
                       Literal(float(uncertainty), datatype=XSD.double)))

        return bnode

    def _get_quantity_kind_for_property(self, property_uri: str) -> Optional[str]:
        """
        Look up qudt:hasQuantityKind annotation for a property from the ontology.

        Used as fallback when the measurement dict doesn't include quantity_kind
        (e.g., programmatic paths like SHPBTestMetadata).

        Args:
            property_uri: Full or prefixed property URI

        Returns:
            Quantity kind URI string, or None if not found
        """
        if not self.ontology:
            return None

        try:
            prop_ref = self._resolve_uri(property_uri)
            qk_predicate = URIRef("http://qudt.org/schema/qudt/hasQuantityKind")

            for _, _, qk in self.ontology.graph.triples((prop_ref, qk_predicate, None)):
                return str(qk)
        except Exception as e:
            logger.debug(f"Could not look up quantity_kind for {property_uri}: {e}")

        return None

    def _save_graph(self, graph: Graph, output_path: Path):
        """Serialize and save graph to TTL file with explicit datatypes."""
        try:
            import re

            ttl_content = graph.serialize(format='turtle')

            logger.debug("Post-processing TTL to add explicit numeric datatypes...")

            # Scientific notation numbers -> xsd:double
            scientific_pattern = r'(\s)(-?\d+\.?\d*[eE][+-]?\d+)(\s*[;,.\]])'

            def add_double_type(match):
                before, number, after = match.groups()
                try:
                    float_val = float(number)
                    if float_val == 0:
                        decimal_str = "0.0"
                    elif abs(float_val) >= 1e-4 and abs(float_val) < 1e6:
                        decimal_str = f"{float_val:.10f}".rstrip('0').rstrip('.')
                        if '.' not in decimal_str:
                            decimal_str += '.0'
                    else:
                        decimal_str = number
                    result = f'{before}"{decimal_str}"^^xsd:double{after}'
                    logger.debug(f"  Converting scientific notation: {number} -> \"{decimal_str}\"^^xsd:double")
                    return result
                except ValueError:
                    result = f'{before}"{number}"^^xsd:double{after}'
                    return result

            ttl_content = re.sub(scientific_pattern, add_double_type, ttl_content)

            # Decimal numbers -> xsd:double (if not already typed)
            decimal_pattern = r'(\s)(-?\d+\.\d+)(?!\^\^)(?!")(\s*[;,.\]])'

            def add_decimal_type(match):
                before, number, after = match.groups()
                if '^^xsd:' in ttl_content[max(0, match.start()-100):match.end()+20]:
                    return match.group(0)
                result = f'{before}"{number}"^^xsd:double{after}'
                logger.debug(f"  Converting decimal: {number} -> \"{number}\"^^xsd:double")
                return result

            ttl_content = re.sub(decimal_pattern, add_decimal_type, ttl_content)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(ttl_content)

            logger.info(f"Graph serialized to {output_path} with explicit numeric datatypes")

        except Exception as e:
            logger.error(f"Failed to save graph to {output_path}: {e}")
            raise

    def create_single_instance(self,
                              graph: Graph,
                              form_data: Dict[str, Any],
                              class_uri: str,
                              instance_id: str) -> URIRef:
        """
        Add a single RDF instance to an existing graph.

        Args:
            graph: RDF graph to add instance to
            form_data: Property dictionary (property_uri -> value)
            class_uri: RDF class URI (e.g., "dyn:PulseWindow")
            instance_id: Instance identifier

        Returns:
            URIRef of the created instance
        """
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

            # Handle multi-valued properties (lists)
            if isinstance(value, list):
                for item in value:
                    if item is not None and item != "":
                        rdf_value = self._convert_to_rdf_value(item)
                        graph.add((instance_ref, property_ref, rdf_value))
                logger.debug(f"Added {len(value)} values for multi-valued property {property_uri}")
            elif self._is_measurement_dict(value):
                # Measurement property -> create qudt:QuantityValue blank node
                bnode = self._create_quantity_value(graph, value, property_uri)
                graph.add((instance_ref, property_ref, bnode))
            else:
                # Single-valued property
                rdf_value = self._convert_to_rdf_value(value)
                graph.add((instance_ref, property_ref, rdf_value))

        logger.debug(f"Created instance {instance_id} of type {class_uri}")
        return instance_ref

    def create_instances_batch(self,
                              instances: list,
                              output_graph: Optional[Graph] = None) -> Graph:
        """
        Create multiple RDF instances in a single graph.

        Args:
            instances: List of (form_data, class_uri, instance_id) tuples
            output_graph: Optional existing graph to add to (creates new if None)

        Returns:
            Combined RDF graph with all instances
        """
        if output_graph is None:
            graph = Graph()
            self._setup_namespaces(graph)
        else:
            graph = output_graph

        # Create each instance
        for form_data, class_uri, instance_id in instances:
            self.create_single_instance(graph, form_data, class_uri, instance_id)

        logger.info(f"Created batch of {len(instances)} instances")
        return graph

    def write_multi_instance_file(self,
                                 instances: list,
                                 output_path: Path,
                                 skip_validation: bool = False) -> Tuple[Optional[str], ValidationResult]:
        """
        Write multiple instances to a single TTL file with validation.

        Args:
            instances: List of (form_data, class_uri, instance_id) tuples
            output_path: Path to output TTL file
            skip_validation: Skip SHACL validation if True

        Returns:
            Tuple of (saved_file_path or None if blocked, ValidationResult)
        """
        try:
            # Create batch graph
            graph = self.create_instances_batch(instances)

            # Validate RDF graph with SHACL (after unit conversion, before save)
            validation_result = self._validate_instance_graph(graph, skip_validation)

            # Check validation result - return immediately if blocking violations exist
            if validation_result.has_blocking_issues():
                logger.warning(
                    f"Batch validation failed with {len(validation_result.violations)} violation(s). "
                    f"Save blocked."
                )
                return None, validation_result

            # Ensure output directory exists
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Serialize to TTL
            self._save_graph(graph, output_path)

            logger.info(f"Batch of {len(instances)} instances written to {output_path}")
            return str(output_path), validation_result

        except Exception as e:
            logger.error(f"Failed to write multi-instance file to {output_path}: {e}", exc_info=True)
            raise

    def update_instance(self,
                       instance_uri: str,
                       updates: Dict[str, Any],
                       ttl_file: Path,
                       skip_validation: bool = False) -> Tuple[Optional[str], ValidationResult]:
        """
        Update existing instance by loading TTL, modifying, and re-saving.

        Args:
            instance_uri: URI of instance to update
            updates: Dictionary of property_uri -> new_value
            ttl_file: Path to existing TTL file
            skip_validation: If True, skip SHACL validation

        Returns:
            Tuple of (saved_file_path or None if blocked, ValidationResult)
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

                # Remove old triples (including QuantityValue BNode sub-triples)
                for _, _, old_obj in list(graph.triples((instance_ref, property_ref, None))):
                    if isinstance(old_obj, BNode):
                        # Remove all triples where BNode is the subject
                        graph.remove((old_obj, None, None))
                graph.remove((instance_ref, property_ref, None))

                # Add new value(s)
                if new_value is not None and new_value != "":
                    # Handle multi-valued properties (lists from multi-select widgets)
                    if isinstance(new_value, list):
                        for item in new_value:
                            if item is not None and item != "":
                                rdf_value = self._convert_to_rdf_value(item)
                                graph.add((instance_ref, property_ref, rdf_value))
                        logger.debug(f"Updated with {len(new_value)} values for multi-valued property {property_uri}")
                    elif self._is_measurement_dict(new_value):
                        # Measurement property -> create QuantityValue BNode
                        bnode = self._create_quantity_value(graph, new_value, property_uri)
                        graph.add((instance_ref, property_ref, bnode))
                    else:
                        # Single-valued property
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
