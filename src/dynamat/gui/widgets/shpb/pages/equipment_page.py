"""Equipment Configuration Page - Ontology-driven form for SHPB analysis.

This page uses CustomizableFormBuilder to automatically generate the equipment
configuration form from the SHPBCompression class definition in the ontology.

Form structure comes from gui:hasFormGroup annotations:
- Identification: Test ID, test specimen, test date
- BarConfiguration: Striker, incident, and transmission bars
- StrainGaugeConfiguration: Incident and transmission strain gauges
- TestConditions: Striker velocity, pressure, barrel offset, pulse shaper, momentum trap, lubrication

Widget types and constraints are automatically inferred from ontology metadata.
"""

import logging
from typing import Optional

from PyQt6.QtWidgets import QVBoxLayout, QLabel, QWidget, QComboBox, QLineEdit
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, XSD

from .base_page import BaseSHPBPage
from .....mechanical.shpb.io.specimen_loader import SpecimenLoader
from .....config import config
from ....builders.customizable_form_builder import CustomizableFormBuilder
from ....dependencies import DependencyManager

logger = logging.getLogger(__name__)

# DynaMat ontology namespace
DYN_NS = "https://dynamat.utep.edu/ontology#"


class EquipmentPage(BaseSHPBPage):
    """Equipment configuration page for SHPB analysis (ontology-driven).

    Features:
    - Auto-generated form from SHPBCompression ontology class
    - Automatic widget type inference (combos for equipment, unit widgets for measurements)
    - Constraint-based visibility (momentum trap distance only for TailoredGap)

    The form structure is entirely driven by GUI annotations in:
    - dynamat/ontology/class_properties/shpb_compression_class.ttl
    - dynamat/ontology/constraints/gui_shpb_rules.ttl
    """

    def __init__(self, state, ontology_manager, qudt_manager=None, parent=None):
        super().__init__(state, ontology_manager, qudt_manager, parent)

        self.setTitle("Configure Equipment")
        self.setSubTitle("Select the SHPB equipment and test conditions.")

        self.specimen_loader: Optional[SpecimenLoader] = None
        self.form_widget: Optional[QWidget] = None
        self.form_builder: Optional[CustomizableFormBuilder] = None
        self.dependency_manager: Optional[DependencyManager] = None

    def _setup_ui(self) -> None:
        """Setup page UI using customizable form builder."""
        layout = self._create_base_layout()

        # Initialize customizable form builder
        self.form_builder = CustomizableFormBuilder(self.ontology_manager)

        # Build form from ontology for SHPBCompression class
        # Note: CustomizableFormBuilder already creates its own scroll area
        try:
            self.form_widget = self.form_builder.build_form(
                "https://dynamat.utep.edu/ontology#SHPBCompression",
                parent=self
            )

            if self.form_widget:
                layout.addWidget(self.form_widget)
                self.logger.info("Equipment form created from ontology")

                # Setup dependency manager for constraints
                self.dependency_manager = DependencyManager(self.ontology_manager)
                self.dependency_manager.setup_dependencies(
                    self.form_widget,
                    "https://dynamat.utep.edu/ontology#SHPBCompression"
                )
                self.logger.info("Dependencies configured with PropertyDisplayWidgets")

            else:
                self.logger.error("Form builder returned None")
                error_label = QLabel("Error: Could not create form from ontology")
                error_label.setStyleSheet("color: red;")
                layout.addWidget(error_label)

        except Exception as e:
            self.logger.error(f"Failed to build form from ontology: {e}", exc_info=True)
            error_label = QLabel(f"Error creating form: {str(e)}")
            error_label.setStyleSheet("color: red;")
            layout.addWidget(error_label)

        self._add_status_area()


    def initializePage(self) -> None:
        """Initialize page when it becomes current."""
        super().initializePage()

        # Initialize specimen loader for equipment property queries
        if self.specimen_loader is None:
            self._initialize_specimen_loader()

        # Populate identification fields from specimen selection (cross-page data)
        self._populate_from_specimen_selection()

        # Restore previous selections if any
        self._restore_selections()

    def validatePage(self) -> bool:
        """Validate before allowing Next."""
        if not self.form_widget:
            self.show_warning("Form Error", "Form not initialized")
            return False

        # Validate using form builder
        errors = self.form_builder.validate_form(self.form_widget)

        if errors:
            error_msg = "Please fix the following errors:\n\n"
            for field_uri, field_errors in errors.items():
                # Extract readable field name
                field_name = field_uri.split('#')[-1].replace('has', '').replace('_', ' ')
                error_msg += f"• {field_name}: {', '.join(field_errors)}\n"

            self.show_warning("Validation Errors", error_msg)
            return False

        # Save to state
        self._save_to_state()

        # Run SHACL validation on partial graph
        validation_graph = self._build_validation_graph()
        if validation_graph and not self._validate_page_data(validation_graph):
            return False

        # Extract equipment properties
        if not self._extract_equipment_properties():
            self.show_warning(
                "Property Error",
                "Could not extract equipment properties. Please verify selections."
            )
            return False

        return True

    def _build_validation_graph(self) -> Optional[Graph]:
        """Build partial RDF graph for SHACL validation of equipment data.

        Returns:
            RDF graph with SHPBCompression instance, or None on error.
        """
        if not self.state.equipment_form_data:
            return None

        try:
            DYN = Namespace(DYN_NS)
            g = Graph()
            g.bind("dyn", DYN)

            instance = DYN["_val_equipment"]
            g.add((instance, RDF.type, DYN.SHPBCompression))

            form_data = self.state.equipment_form_data

            # Property type mapping for SHPBCompression
            object_properties = {
                "hasStrikerBar", "hasIncidentBar", "hasTransmissionBar",
                "hasMomentumTrap", "hasPulseShaper", "hasAlignmentParams",
                "hasEquilibriumMetrics", "performedOn", "hasUser",
                "hasIncidentStrainGauge", "hasTransmissionStrainGauge",
            }
            boolean_properties = {
                "hasPulseShaping", "hasLubricationUsed",
            }
            integer_properties = {
                "hasPulsePoints", "hasCenteredSegmentPoints",
                "hasShiftValue", "hasMinSeparation", "hasFrontIndex",
                "hasDetectionLowerBound", "hasDetectionUpperBound",
                "hasDataBitResolution",
            }
            string_properties = {
                "hasTestID", "hasTestType", "hasLubricationType",
                "hasKTrials", "hasDeformationMode", "hasFailureMode",
                "hasTestValidity", "hasWaveDispersion", "hasCompressionSign",
            }
            date_properties = {"hasTestDate", "hasAnalysisTimestamp"}

            for uri, value in form_data.items():
                if value is None:
                    continue

                prop_name = uri.split("#")[-1] if "#" in uri else uri.split("/")[-1]
                prop = DYN[prop_name]

                if prop_name in object_properties:
                    if isinstance(value, str) and value:
                        g.add((instance, prop, URIRef(value)))
                elif prop_name in boolean_properties:
                    g.add((instance, prop, Literal(bool(value), datatype=XSD.boolean)))
                elif prop_name in integer_properties:
                    g.add((instance, prop, Literal(int(value), datatype=XSD.integer)))
                elif prop_name in string_properties:
                    g.add((instance, prop, Literal(str(value), datatype=XSD.string)))
                elif prop_name in date_properties:
                    g.add((instance, prop, Literal(str(value), datatype=XSD.date)))
                else:
                    # Default to double for measurement properties
                    try:
                        g.add((instance, prop, Literal(float(value), datatype=XSD.double)))
                    except (ValueError, TypeError):
                        g.add((instance, prop, Literal(str(value), datatype=XSD.string)))

            return g

        except Exception as e:
            self.logger.error(f"Failed to build validation graph: {e}")
            return None

    def _initialize_specimen_loader(self) -> None:
        """Initialize the specimen loader for property queries."""
        try:
            self.specimen_loader = SpecimenLoader(self.ontology_manager)

            # Load specimen files if available
            if config.SPECIMENS_DIR.exists():
                self.specimen_loader.load_specimen_files(config.SPECIMENS_DIR)

            self.logger.info("Specimen loader initialized")

        except Exception as e:
            self.logger.error(f"Failed to initialize specimen loader: {e}")

    def _populate_from_specimen_selection(self) -> None:
        """Populate identification fields from specimen selection (cross-page data)."""
        if not self.form_widget or not hasattr(self.form_widget, 'form_fields'):
            return

        form_fields = self.form_widget.form_fields

        # Get specimen info from state (set on previous page)
        specimen_id = getattr(self.state, 'specimen_id', None)
        specimen_uri = getattr(self.state, 'specimen_uri', None)

        if not specimen_id and not specimen_uri:
            self.logger.debug("No specimen selected, skipping identification population")
            return

        # 1. Generate and set Test ID
        test_id_uri = f"{DYN_NS}hasTestID"
        if test_id_uri in form_fields:
            test_id_field = form_fields[test_id_uri]
            widget = test_id_field.widget

            # Generate test ID from specimen ID
            if specimen_id:
                test_id = f"{specimen_id.replace('-', '_')}_SHPBTest"
            else:
                local_name = specimen_uri.split('#')[-1] if '#' in specimen_uri else specimen_uri.split('/')[-1]
                test_id = f"{local_name}_SHPBTest"

            if isinstance(widget, QLineEdit):
                widget.setText(test_id)
                widget.setReadOnly(True)
                self.logger.info(f"Set Test ID: {test_id} (read-only)")
            elif isinstance(widget, QComboBox):
                widget.setCurrentText(test_id)
                widget.setEnabled(False)
                self.logger.info(f"Set Test ID: {test_id} (disabled)")

            self.state.test_id = test_id

        # 2. Set Test Specimen reference
        test_specimen_uri = f"{DYN_NS}performedOn"
        if test_specimen_uri in form_fields and specimen_uri:
            test_specimen_field = form_fields[test_specimen_uri]
            widget = test_specimen_field.widget

            if isinstance(widget, QComboBox):
                index = widget.findData(specimen_uri)
                if index >= 0:
                    widget.setCurrentIndex(index)
                else:
                    display_name = specimen_id or specimen_uri.split('#')[-1]
                    widget.addItem(display_name, specimen_uri)
                    widget.setCurrentIndex(widget.count() - 1)

                widget.setEnabled(False)
                self.logger.info(f"Set Test Specimen: {specimen_uri} (read-only)")

    def _restore_selections(self) -> None:
        """Restore previous selections from state equipment form data."""
        if not self.form_widget or not self.form_builder:
            return

        if self.state.equipment_form_data:
            self.form_builder.set_form_data(self.form_widget, self.state.equipment_form_data)

    def _save_to_state(self) -> None:
        """Save current form data to state as a single dict."""
        if not self.form_widget or not self.form_builder:
            return

        self.state.equipment_form_data = self.form_builder.get_form_data(self.form_widget)

    def _extract_equipment_properties(self) -> bool:
        """Extract full equipment properties from ontology.

        Reads URIs from equipment_form_data and queries ontology for
        bar/gauge physical properties needed for calculations.

        Returns:
            True if successful, False otherwise
        """
        if not self.specimen_loader:
            self.logger.error("Specimen loader not available")
            return False

        data = self.state.equipment_form_data
        if not data:
            self.logger.error("No equipment form data available")
            return False

        try:
            equipment = {}

            # Extract bar properties using URIs from form data
            bar_uri_map = {
                'striker_bar': data.get(f"{DYN_NS}hasStrikerBar"),
                'incident_bar': data.get(f"{DYN_NS}hasIncidentBar"),
                'transmission_bar': data.get(f"{DYN_NS}hasTransmissionBar"),
            }

            for bar_type, uri in bar_uri_map.items():
                if uri:
                    bar_props = self.specimen_loader.get_multiple_properties(
                        uri,
                        ['hasLength', 'hasDiameter', 'hasCrossSection', 'hasMaterial']
                    )

                    equipment[bar_type] = {
                        'uri': uri,
                        'length': bar_props.get('hasLength'),
                        'diameter': bar_props.get('hasDiameter'),
                        'cross_section': bar_props.get('hasCrossSection'),
                        'material_uri': bar_props.get('hasMaterial'),
                    }

                    # Get material properties
                    material_uri = bar_props.get('hasMaterial')
                    if material_uri:
                        mat_props = self.specimen_loader.get_multiple_properties(
                            material_uri,
                            ['hasWaveSpeed', 'hasElasticModulus', 'hasDensity']
                        )
                        equipment[bar_type]['wave_speed'] = mat_props.get('hasWaveSpeed')
                        equipment[bar_type]['elastic_modulus'] = mat_props.get('hasElasticModulus')
                        equipment[bar_type]['density'] = mat_props.get('hasDensity')

            # Extract gauge properties
            gauge_uri_map = {
                'incident_gauge': data.get(f"{DYN_NS}hasIncidentStrainGauge"),
                'transmission_gauge': data.get(f"{DYN_NS}hasTransmissionStrainGauge"),
            }

            for gauge_type, uri in gauge_uri_map.items():
                if uri:
                    gauge_props = self.specimen_loader.get_multiple_properties(
                        uri,
                        ['hasGaugeFactor', 'hasGaugeResistance',
                         'hasCalibrationVoltage', 'hasCalibrationResistance',
                         'hasDistanceFromSpecimen']
                    )

                    equipment[gauge_type] = {
                        'uri': uri,
                        'gauge_factor': gauge_props.get('hasGaugeFactor'),
                        'gauge_resistance': gauge_props.get('hasGaugeResistance'),
                        'calibration_voltage': gauge_props.get('hasCalibrationVoltage'),
                        'calibration_resistance': gauge_props.get('hasCalibrationResistance'),
                        'distance_from_specimen': gauge_props.get('hasDistanceFromSpecimen'),
                    }

            self.state.equipment_properties = equipment
            self.logger.info("Equipment properties extracted successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to extract equipment properties: {e}")
            return False
