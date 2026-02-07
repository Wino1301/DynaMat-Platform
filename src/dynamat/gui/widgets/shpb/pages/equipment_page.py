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

        # Extract equipment properties
        if not self._extract_equipment_properties():
            self.show_warning(
                "Property Error",
                "Could not extract equipment properties. Please verify selections."
            )
            return False

        return True

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
        """Populate identification fields from specimen selection (cross-page data).

        This sets:
        - Test ID: Auto-generated from specimen ID (e.g., DYNML_A356_0001_SHPBTest)
        - Test Specimen: Selected specimen URI (read-only reference)

        These fields are populated from the specimen selected on the previous page,
        not from constraint triggers within this form.
        """
        if not self.form_widget or not hasattr(self.form_widget, 'form_fields'):
            return

        form_fields = self.form_widget.form_fields

        # Get specimen info from state (set on previous page)
        specimen_id = getattr(self.state, 'specimen_id', None)
        specimen_uri = getattr(self.state, 'specimen_uri', None)

        if not specimen_id and not specimen_uri:
            self.logger.debug("No specimen selected, skipping identification population")
            return

        # 1. Generate and set Test ID (inherited from MechanicalTest via DynaMat_core.ttl)
        test_id_uri = f"{DYN_NS}hasTestID"
        if test_id_uri in form_fields:
            test_id_field = form_fields[test_id_uri]
            widget = test_id_field.widget

            # Generate test ID from specimen ID
            if specimen_id:
                # Format: DYNML_A356_0001_SHPBTest (replace dashes with underscores for consistency)
                test_id = f"{specimen_id.replace('-', '_')}_SHPBTest"
            else:
                # Fallback: extract from URI
                local_name = specimen_uri.split('#')[-1] if '#' in specimen_uri else specimen_uri.split('/')[-1]
                test_id = f"{local_name}_SHPBTest"

            # Set the value
            if isinstance(widget, QLineEdit):
                widget.setText(test_id)
                widget.setReadOnly(True)
                self.logger.info(f"Set Test ID: {test_id} (read-only)")
            elif isinstance(widget, QComboBox):
                # If it's a combo (unlikely for ID), try to add the item
                widget.setCurrentText(test_id)
                widget.setEnabled(False)
                self.logger.info(f"Set Test ID: {test_id} (disabled)")

            # Store in state for later use
            self.state.test_id = test_id

        # 2. Set Test Specimen reference (inherited from Activity via DynaMat_core.ttl as performedOn)
        test_specimen_uri = f"{DYN_NS}performedOn"
        if test_specimen_uri in form_fields and specimen_uri:
            test_specimen_field = form_fields[test_specimen_uri]
            widget = test_specimen_field.widget

            if isinstance(widget, QComboBox):
                # Find and select the specimen in the combo
                index = widget.findData(specimen_uri)
                if index >= 0:
                    widget.setCurrentIndex(index)
                else:
                    # Specimen not in list - add it
                    display_name = specimen_id or specimen_uri.split('#')[-1]
                    widget.addItem(display_name, specimen_uri)
                    widget.setCurrentIndex(widget.count() - 1)

                # Make read-only (disable the combo)
                widget.setEnabled(False)
                self.logger.info(f"Set Test Specimen: {specimen_uri} (read-only)")

    def _restore_selections(self) -> None:
        """Restore previous selections from state (equipment and test conditions)."""
        if not self.form_widget or not self.form_builder:
            return

        # Build state data dict from stored state
        # Note: Identification fields (Test ID, Test Specimen) are handled by
        # _populate_from_specimen_selection() and are read-only
        state_data = {}

        # Equipment URIs
        if hasattr(self.state, 'striker_bar_uri') and self.state.striker_bar_uri:
            state_data[f"{DYN_NS}hasStrikerBar"] = self.state.striker_bar_uri
        if hasattr(self.state, 'incident_bar_uri') and self.state.incident_bar_uri:
            state_data[f"{DYN_NS}hasIncidentBar"] = self.state.incident_bar_uri
        if hasattr(self.state, 'transmission_bar_uri') and self.state.transmission_bar_uri:
            state_data[f"{DYN_NS}hasTransmissionBar"] = self.state.transmission_bar_uri
        if hasattr(self.state, 'incident_gauge_uri') and self.state.incident_gauge_uri:
            state_data[f"{DYN_NS}hasIncidentStrainGauge"] = self.state.incident_gauge_uri
        if hasattr(self.state, 'transmission_gauge_uri') and self.state.transmission_gauge_uri:
            state_data[f"{DYN_NS}hasTransmissionStrainGauge"] = self.state.transmission_gauge_uri
        if hasattr(self.state, 'momentum_trap_uri') and self.state.momentum_trap_uri:
            state_data[f"{DYN_NS}hasMomentumTrap"] = self.state.momentum_trap_uri
        if hasattr(self.state, 'pulse_shaper_uri') and self.state.pulse_shaper_uri:
            state_data[f"{DYN_NS}hasPulseShaper"] = self.state.pulse_shaper_uri

        # Test date
        if hasattr(self.state, 'test_date') and self.state.test_date:
            state_data[f"{DYN_NS}hasTestDate"] = self.state.test_date

        # Measurement values (these are dicts with value/unit)
        if hasattr(self.state, 'striker_velocity') and self.state.striker_velocity:
            state_data[f"{DYN_NS}hasStrikerVelocity"] = self.state.striker_velocity
        if hasattr(self.state, 'striker_launch_pressure') and self.state.striker_launch_pressure:
            state_data[f"{DYN_NS}hasStrikerLaunchPressure"] = self.state.striker_launch_pressure
        if hasattr(self.state, 'barrel_offset') and self.state.barrel_offset:
            state_data[f"{DYN_NS}hasBarrelOffset"] = self.state.barrel_offset
        if hasattr(self.state, 'momentum_trap_distance') and self.state.momentum_trap_distance:
            state_data[f"{DYN_NS}hasMomentumTrapTailoredDistance"] = self.state.momentum_trap_distance

        # Set form data if we have any
        if state_data:
            self.form_builder.set_form_data(self.form_widget, state_data)

    def _save_to_state(self) -> None:
        """Save current form data to state."""
        if not self.form_widget or not self.form_builder:
            return

        # Get all form data
        data = self.form_builder.get_form_data(self.form_widget)

        # Identification (auto-generated, read-only)
        # test_id is already set in _populate_from_specimen_selection()
        # specimen_uri is already in state from specimen selection page

        # Equipment URIs
        self.state.striker_bar_uri = data.get(f"{DYN_NS}hasStrikerBar")
        self.state.incident_bar_uri = data.get(f"{DYN_NS}hasIncidentBar")
        self.state.transmission_bar_uri = data.get(f"{DYN_NS}hasTransmissionBar")
        self.state.incident_gauge_uri = data.get(f"{DYN_NS}hasIncidentStrainGauge")
        self.state.transmission_gauge_uri = data.get(f"{DYN_NS}hasTransmissionStrainGauge")
        self.state.momentum_trap_uri = data.get(f"{DYN_NS}hasMomentumTrap")
        self.state.pulse_shaper_uri = data.get(f"{DYN_NS}hasPulseShaper")

        # Test date
        self.state.test_date = data.get(f"{DYN_NS}hasTestDate")

        # Measurement values
        self.state.striker_velocity = data.get(f"{DYN_NS}hasStrikerVelocity")
        self.state.striker_launch_pressure = data.get(f"{DYN_NS}hasStrikerLaunchPressure")
        self.state.barrel_offset = data.get(f"{DYN_NS}hasBarrelOffset")
        self.state.momentum_trap_distance = data.get(f"{DYN_NS}hasMomentumTrapTailoredDistance")

        # Get user
        self.state.user_uri = self.get_current_user()

    def _extract_equipment_properties(self) -> bool:
        """Extract full equipment properties from ontology.

        Returns:
            True if successful, False otherwise
        """
        if not self.specimen_loader:
            self.logger.error("Specimen loader not available")
            return False

        try:
            equipment = {}

            # Extract bar properties
            for bar_type, uri_attr in [
                ('striker_bar', self.state.striker_bar_uri),
                ('incident_bar', self.state.incident_bar_uri),
                ('transmission_bar', self.state.transmission_bar_uri),
            ]:
                if uri_attr:
                    bar_props = self.specimen_loader.get_multiple_properties(
                        uri_attr,
                        ['hasLength', 'hasDiameter', 'hasCrossSection', 'hasMaterial']
                    )

                    equipment[bar_type] = {
                        'uri': uri_attr,
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
            for gauge_type, uri_attr in [
                ('incident_gauge', self.state.incident_gauge_uri),
                ('transmission_gauge', self.state.transmission_gauge_uri),
            ]:
                if uri_attr:
                    gauge_props = self.specimen_loader.get_multiple_properties(
                        uri_attr,
                        ['hasGaugeFactor', 'hasGaugeResistance',
                         'hasCalibrationVoltage', 'hasCalibrationResistance',
                         'hasDistanceFromSpecimen']
                    )

                    equipment[gauge_type] = {
                        'uri': uri_attr,
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
