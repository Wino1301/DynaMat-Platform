"""
DynaMat Platform - Instance Writer
Converts form data to TTL instance files for any ontology class
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

try:
    from PyQt6.QtWidgets import QMessageBox, QInputDialog
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, OWL, XSD

from ...ontology.core.namespace_manager import NamespaceManager
from ...config import config

logger = logging.getLogger(__name__)


class InstanceWriter:
    """
    Converts form data to TTL instance files.
    Handles all ontology classes with proper RDF serialization.

    Key responsibilities:
    - Filter ontology properties (dyn:) from GUI properties (gui:)
    - Convert form data to RDF triples
    - Handle measurement properties with units
    - Add metadata (user, dates, version)
    - Validate before saving (SHACL)
    - Handle file overwrite confirmation
    """

    def __init__(self, namespace_manager: NamespaceManager, ontology_manager=None):
        """
        Initialize the instance writer.

        Args:
            namespace_manager: Namespace manager for URI handling
            ontology_manager: Optional ontology manager for property metadata
        """
        self.ns_manager = namespace_manager
        self.ontology_manager = ontology_manager

        # Specimens directory (outside the code package)
        self.specimens_dir = Path(config.BASE_DIR) / "specimens"
        self.specimens_dir.mkdir(exist_ok=True)

        logger.info("InstanceWriter initialized")

    def write_instance(
        self,
        class_uri: str,
        instance_id: str,
        form_data: Dict[str, Any],
        output_path: Optional[Path] = None,
        user_uri: Optional[str] = None,
        notes: Optional[str] = None
    ) -> str:
        """
        Main method: Convert form data to TTL and save.

        Args:
            class_uri: The ontology class (dyn:Specimen, dyn:SHPBCompression, etc.)
            instance_id: Instance identifier (SPN-AL6061-001)
            form_data: Extracted form data from FormDataHandler
            output_path: Optional custom output path (auto-determined if None)
            user_uri: Optional user URI (will prompt if None)
            notes: Optional notes to include

        Returns:
            Path to saved file
        """
        logger.info(f"Writing instance: {instance_id} of class {class_uri}")

        # 1. Validate before saving
        if not self._validate_instance(form_data):
            raise ValueError("Instance validation failed")

        # 2. Filter to only ontology properties (exclude GUI annotations)
        filtered_data = self._filter_ontology_properties(form_data)
        logger.debug(f"Filtered {len(form_data)} properties to {len(filtered_data)} ontology properties")

        # 3. Get or prompt for user
        if user_uri is None:
            user_uri = self._get_user_selection()

        # 4. Determine output path
        if output_path is None:
            output_path = self._determine_output_path(class_uri, instance_id, filtered_data)

        # 5. Check for overwrite
        if output_path.exists():
            if not self._confirm_overwrite(output_path):
                logger.info("User cancelled overwrite")
                return None

        # 6. Create RDF graph
        graph = self._create_instance_graph(
            class_uri=class_uri,
            instance_id=instance_id,
            form_data=filtered_data,
            user_uri=user_uri,
            notes=notes,
            is_overwrite=output_path.exists()
        )

        # 7. Save to file
        self._save_graph_to_file(graph, output_path)

        logger.info(f"Successfully saved instance to: {output_path}")
        return str(output_path)

    # ============================================================================
    # VALIDATION
    # ============================================================================

    def _validate_instance(self, form_data: Dict[str, Any]) -> bool:
        """
        Validate instance data before saving (SHACL validation).

        Args:
            form_data: Form data to validate

        Returns:
            True if validation passes

        NOTE: This is a placeholder. Full SHACL validation will be implemented later.
        """
        # TODO: Implement SHACL validation
        # For now, just return True for testing
        logger.debug("SHACL validation (placeholder): PASS")
        return True

    # ============================================================================
    # FILTERING
    # ============================================================================

    def _filter_ontology_properties(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter to only include dyn: namespace properties.
        Excludes GUI annotation properties like hasDisplayName, hasFormGroup, etc.

        Args:
            form_data: Raw form data

        Returns:
            Filtered data with only ontology properties
        """
        filtered = {}

        dyn_namespace = "https://dynamat.utep.edu/ontology#"

        for prop_uri, value in form_data.items():
            # Only include properties from the dyn: namespace
            if prop_uri.startswith(dyn_namespace):
                # Check if it's not a GUI annotation property
                prop_name = prop_uri.replace(dyn_namespace, "")

                # Skip GUI-specific properties
                gui_properties = {
                    'hasDisplayName', 'hasFormGroup', 'hasGroupOrder',
                    'hasDisplayOrder', 'hasDefaultUnit', 'hasWidgetType',
                    'hasMinValue', 'hasMaxValue', 'hasPattern'
                }

                if prop_name not in gui_properties:
                    filtered[prop_uri] = value

        return filtered

    # ============================================================================
    # GRAPH CREATION
    # ============================================================================

    def _create_instance_graph(
        self,
        class_uri: str,
        instance_id: str,
        form_data: Dict[str, Any],
        user_uri: str,
        notes: Optional[str],
        is_overwrite: bool
    ) -> Graph:
        """
        Create RDF graph for the instance.

        Args:
            class_uri: Class URI
            instance_id: Instance identifier
            form_data: Filtered form data
            user_uri: User URI
            notes: Optional notes
            is_overwrite: Whether this is overwriting an existing file

        Returns:
            RDF Graph
        """
        # Create graph
        graph = Graph()
        self.ns_manager.setup_graph_namespaces(graph)

        # Generate instance URI (replace hyphens with underscores)
        instance_uri = self._generate_instance_uri(instance_id)
        instance_ref = URIRef(instance_uri)
        class_ref = URIRef(class_uri)

        # Add type assertion
        graph.add((instance_ref, RDF.type, OWL.NamedIndividual))
        graph.add((instance_ref, RDF.type, class_ref))

        # Add label
        label = self._generate_label(instance_id, class_uri)
        graph.add((instance_ref, RDFS.label, Literal(label, lang="en")))

        # Add property values
        for prop_uri, value in form_data.items():
            self._add_property_to_graph(graph, instance_ref, prop_uri, value)

        # Add metadata
        self._add_metadata_to_graph(graph, instance_ref, user_uri, notes, is_overwrite)

        return graph

    def _add_property_to_graph(self, graph: Graph, instance_ref: URIRef,
                               prop_uri: str, value: Any):
        """
        Add a property value to the graph.
        Handles measurement properties with unit conversion.

        Args:
            graph: RDF graph
            instance_ref: Instance URI reference
            prop_uri: Property URI
            value: Property value
        """
        prop_ref = URIRef(prop_uri)

        # Handle measurement properties from UnitValueWidget (dict with 'value' and 'unit')
        if isinstance(value, dict) and 'value' in value and 'unit' in value:
            # Convert the value to standard unit using runtime conversion
            # This is triggered when UnitValueWidget data is processed
            converted_value = self._convert_unit_to_standard(
                value['value'],
                value['unit'],
                prop_uri
            )

            # Store only the converted value (in standard unit)
            # The standard unit is defined in the ontology, not stored in the instance
            graph.add((instance_ref, prop_ref, Literal(converted_value, datatype=XSD.double)))

        # Handle object properties (URIs)
        elif isinstance(value, str) and value.startswith('http'):
            graph.add((instance_ref, prop_ref, URIRef(value)))

        # Handle data properties with proper datatypes
        else:
            rdf_value = self._convert_to_rdf_literal(value, prop_uri)
            graph.add((instance_ref, prop_ref, rdf_value))

    def _add_metadata_to_graph(self, graph: Graph, instance_ref: URIRef,
                               user_uri: str, notes: Optional[str],
                               is_overwrite: bool):
        """
        Add metadata to the instance.

        Args:
            graph: RDF graph
            instance_ref: Instance URI reference
            user_uri: User URI
            notes: Optional notes
            is_overwrite: Whether this is an overwrite operation
        """
        now = datetime.now()

        # User
        graph.add((instance_ref, self.ns_manager.DYN.hasUser, URIRef(user_uri)))

        # Dates
        if is_overwrite:
            # This is an overwrite - update modified date
            graph.add((instance_ref, self.ns_manager.DYN.hasModifiedDate,
                      Literal(now.isoformat(), datatype=XSD.dateTime)))
        else:
            # New instance - set creation date
            graph.add((instance_ref, self.ns_manager.DYN.hasCreationDate,
                      Literal(now.isoformat(), datatype=XSD.dateTime)))

        # Version
        graph.add((instance_ref, self.ns_manager.DYN.hasDynamatVersion,
                  Literal(config.VERSION)))

        # Notes (if provided)
        if notes:
            graph.add((instance_ref, self.ns_manager.DYN.hasNotes, Literal(notes)))

    # ============================================================================
    # UNIT CONVERSION (PLACEHOLDER)
    # ============================================================================

    def _convert_unit_to_standard(self, value: float, unit_uri: str,
                                   property_uri: str) -> float:
        """
        Convert measurement value to standard unit at runtime.

        This is triggered when UnitValueWidget data is processed (dict with 'value' and 'unit').
        The standard unit for each property is defined in the ontology.

        Args:
            value: Numeric value from the widget
            unit_uri: Unit URI selected in the widget
            property_uri: Property URI (to determine standard unit from ontology)

        Returns:
            Converted value in standard unit

        NOTE: This is a placeholder. Full unit conversion will be implemented later.
        The actual implementation will:
        1. Query ontology for property's standard unit (e.g., meters for length)
        2. Use QUDT conversion factors to convert from input unit to standard unit
        3. Return the converted value

        For now, just returns the original value unchanged.
        """
        # TODO: Implement full unit conversion logic:
        # 1. Get standard unit from ontology for this property
        # 2. Get conversion factor from QUDT (unit_uri -> standard_unit)
        # 3. Apply conversion: converted_value = value * conversion_factor
        # 4. Return converted value

        logger.debug(f"Unit conversion (placeholder): {value} from {unit_uri} for {property_uri}")
        logger.debug(f"  -> Returning original value: {value} (conversion not yet implemented)")

        return value

    # ============================================================================
    # VALUE CONVERSION
    # ============================================================================

    def _convert_to_rdf_literal(self, value: Any, prop_uri: str) -> Literal:
        """
        Convert Python value to RDF Literal with correct datatype.

        Args:
            value: Python value
            prop_uri: Property URI (to get metadata if available)

        Returns:
            RDF Literal with appropriate datatype
        """
        # Get property metadata if available
        property_metadata = None
        if self.ontology_manager:
            try:
                # Try to get metadata from ontology
                property_metadata = self.ontology_manager.get_property_metadata(prop_uri)
            except:
                pass

        # Use metadata if available
        if property_metadata:
            data_type = property_metadata.data_type.lower()

            if data_type == "integer":
                return Literal(int(value), datatype=XSD.integer)
            elif data_type in ["double", "float"]:
                return Literal(float(value), datatype=XSD.double)
            elif data_type == "boolean":
                return Literal(bool(value), datatype=XSD.boolean)
            elif data_type == "date":
                return Literal(str(value), datatype=XSD.date)
            else:
                return Literal(str(value))

        # Fallback: Infer from Python type
        if isinstance(value, bool):
            return Literal(value, datatype=XSD.boolean)
        elif isinstance(value, int):
            return Literal(value, datatype=XSD.integer)
        elif isinstance(value, float):
            return Literal(value, datatype=XSD.double)
        elif hasattr(value, 'isoformat'):  # datetime/date
            return Literal(value.isoformat(), datatype=XSD.dateTime)
        else:
            return Literal(str(value))

    # ============================================================================
    # FILE OPERATIONS
    # ============================================================================

    def _determine_output_path(self, class_uri: str, instance_id: str,
                               form_data: Dict[str, Any]) -> Path:
        """
        Determine output path based on class type and instance ID.
        Uses underscores in file paths.

        Args:
            class_uri: Class URI
            instance_id: Instance identifier
            form_data: Form data (may contain specimen reference for tests)

        Returns:
            Path object for output file
        """
        # Convert instance_id to use underscores
        safe_id = instance_id.replace("-", "_")

        # Extract class name
        class_name = self._extract_class_name(class_uri)

        # Determine path based on class type
        if class_name == "Specimen":
            # specimens/SPN_AL6061_001/SPN_AL6061_001_specimen.ttl
            specimen_dir = self.specimens_dir / safe_id
            specimen_dir.mkdir(parents=True, exist_ok=True)
            return specimen_dir / f"{safe_id}_specimen.ttl"

        elif "Test" in class_name or "Compression" in class_name:
            # Need to find specimen reference to determine directory
            specimen_id = self._extract_specimen_id_from_test(form_data)
            if specimen_id:
                safe_specimen_id = specimen_id.replace("-", "_")
                specimen_dir = self.specimens_dir / safe_specimen_id
                specimen_dir.mkdir(parents=True, exist_ok=True)

                # Include test type and date in filename
                # e.g., SPN_AL6061_001_SHPB_20250115.ttl
                return specimen_dir / f"{safe_id}.ttl"
            else:
                # Fallback: create in general tests directory
                tests_dir = self.specimens_dir / "tests"
                tests_dir.mkdir(parents=True, exist_ok=True)
                return tests_dir / f"{safe_id}.ttl"

        else:
            # Generic: save in class-specific directory
            class_dir = self.specimens_dir / class_name.lower()
            class_dir.mkdir(parents=True, exist_ok=True)
            return class_dir / f"{safe_id}.ttl"

    def _save_graph_to_file(self, graph: Graph, file_path: Path):
        """
        Save RDF graph to TTL file with proper formatting.

        Args:
            graph: RDF graph
            file_path: Output file path
        """
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Serialize to TTL
        with file_path.open("w", encoding="utf-8") as f:
            f.write(graph.serialize(format="turtle"))

        logger.info(f"Saved TTL file: {file_path}")

    def _confirm_overwrite(self, file_path: Path) -> bool:
        """
        Show confirmation dialog for file overwrite.

        Args:
            file_path: Path to file that exists

        Returns:
            True if user confirms overwrite, False otherwise
        """
        if not PYQT_AVAILABLE:
            # Fallback for testing without GUI
            logger.warning(f"File exists: {file_path}. Auto-confirming overwrite (no GUI available)")
            return True

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Confirm Overwrite")
        msg.setText(f"File already exists:\n{file_path}\n\nDo you want to overwrite it?")
        msg.setInformativeText("The modification date will be updated.")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)

        result = msg.exec()
        return result == QMessageBox.StandardButton.Yes

    # ============================================================================
    # USER SELECTION
    # ============================================================================

    def _get_user_selection(self) -> str:
        """
        Prompt user to select/enter user.

        Returns:
            User URI

        NOTE: This is a placeholder. Full user management will be implemented later.
        For now, just creates a placeholder user.
        """
        # TODO: Implement proper user selection dialog
        # For now, use a simple input dialog

        # Placeholder user
        placeholder_user = "PlaceholderUser"

        # In the future, this would show a dialog with user list
        # For now, just return placeholder
        user_uri = str(self.ns_manager.DYN[placeholder_user])

        logger.debug(f"Using user: {user_uri}")
        return user_uri

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _generate_instance_uri(self, instance_id: str) -> str:
        """
        Generate instance URI from ID.
        Replaces hyphens with underscores for valid URIs.

        Args:
            instance_id: Instance identifier

        Returns:
            Full instance URI
        """
        # Replace hyphens with underscores
        clean_id = instance_id.replace("-", "_")
        return str(self.ns_manager.DYN[clean_id])

    def _generate_label(self, instance_id: str, class_uri: str) -> str:
        """
        Generate human-readable label for instance.

        Args:
            instance_id: Instance identifier
            class_uri: Class URI

        Returns:
            Label string
        """
        class_name = self._extract_class_name(class_uri)

        if class_name == "Specimen":
            return instance_id
        elif "Test" in class_name:
            return f"{class_name} - {instance_id}"
        else:
            return f"{class_name}: {instance_id}"

    def _extract_class_name(self, class_uri: str) -> str:
        """Extract class name from URI."""
        if "#" in class_uri:
            return class_uri.split("#")[-1]
        elif "/" in class_uri:
            return class_uri.split("/")[-1]
        else:
            return class_uri

    def _extract_specimen_id_from_test(self, form_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract specimen ID from test form data.

        Args:
            form_data: Form data

        Returns:
            Specimen ID if found, None otherwise
        """
        # Look for hasSpecimen property
        for prop_uri, value in form_data.items():
            if "hasSpecimen" in prop_uri:
                # Value might be URI or ID
                if isinstance(value, str):
                    if "#" in value:
                        return value.split("#")[-1].replace("_", "-")
                    elif "/" in value:
                        return value.split("/")[-1].replace("_", "-")
                    else:
                        return value

        return None
