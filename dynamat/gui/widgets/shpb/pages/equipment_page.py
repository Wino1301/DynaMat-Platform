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

from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel,
    QScrollArea, QWidget, QFrame
)

from .base_page import BaseSHPBPage
from .....mechanical.shpb.io.specimen_loader import SpecimenLoader
from .....config import config
from ....builders.customizable_form_builder import CustomizableFormBuilder
from ....dependencies import DependencyManager

logger = logging.getLogger(__name__)


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

        # Create scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)

        # Initialize customizable form builder
        self.form_builder = CustomizableFormBuilder(self.ontology_manager)

        # Build form from ontology for SHPBCompression class
        try:
            self.form_widget = self.form_builder.build_form(
                "https://dynamat.utep.edu/ontology#SHPBCompression",
                parent=content
            )

            if self.form_widget:
                content_layout.addWidget(self.form_widget)
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
                content_layout.addWidget(error_label)

        except Exception as e:
            self.logger.error(f"Failed to build form from ontology: {e}", exc_info=True)
            error_label = QLabel(f"Error creating form: {str(e)}")
            error_label.setStyleSheet("color: red;")
            content_layout.addWidget(error_label)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        self._add_status_area()


    def initializePage(self) -> None:
        """Initialize page when it becomes current."""
        super().initializePage()

        # Initialize specimen loader for equipment property queries
        if self.specimen_loader is None:
            self._initialize_specimen_loader()

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


    def _restore_selections(self) -> None:
        """Restore previous selections from state."""
        if not self.form_widget or not self.form_builder:
            return

        # Build state data dict from stored state
        state_data = {}

        # Equipment URIs
        if hasattr(self.state, 'striker_bar_uri') and self.state.striker_bar_uri:
            state_data["https://dynamat.utep.edu/ontology#hasStrikerBar"] = self.state.striker_bar_uri
        if hasattr(self.state, 'incident_bar_uri') and self.state.incident_bar_uri:
            state_data["https://dynamat.utep.edu/ontology#hasIncidentBar"] = self.state.incident_bar_uri
        if hasattr(self.state, 'transmission_bar_uri') and self.state.transmission_bar_uri:
            state_data["https://dynamat.utep.edu/ontology#hasTransmissionBar"] = self.state.transmission_bar_uri
        if hasattr(self.state, 'incident_gauge_uri') and self.state.incident_gauge_uri:
            state_data["https://dynamat.utep.edu/ontology#hasIncidentStrainGauge"] = self.state.incident_gauge_uri
        if hasattr(self.state, 'transmission_gauge_uri') and self.state.transmission_gauge_uri:
            state_data["https://dynamat.utep.edu/ontology#hasTransmissionStrainGauge"] = self.state.transmission_gauge_uri
        if hasattr(self.state, 'momentum_trap_uri') and self.state.momentum_trap_uri:
            state_data["https://dynamat.utep.edu/ontology#hasMomentumTrap"] = self.state.momentum_trap_uri
        if hasattr(self.state, 'pulse_shaper_uri') and self.state.pulse_shaper_uri:
            state_data["https://dynamat.utep.edu/ontology#hasPulseShaper"] = self.state.pulse_shaper_uri

        # Test date
        if hasattr(self.state, 'test_date') and self.state.test_date:
            state_data["https://dynamat.utep.edu/ontology#hasTestDate"] = self.state.test_date

        # Measurement values (these are dicts with value/unit)
        if hasattr(self.state, 'striker_velocity') and self.state.striker_velocity:
            state_data["https://dynamat.utep.edu/ontology#hasStrikerVelocity"] = self.state.striker_velocity
        if hasattr(self.state, 'striker_launch_pressure') and self.state.striker_launch_pressure:
            state_data["https://dynamat.utep.edu/ontology#hasStrikerLaunchPressure"] = self.state.striker_launch_pressure
        if hasattr(self.state, 'barrel_offset') and self.state.barrel_offset:
            state_data["https://dynamat.utep.edu/ontology#hasBarrelOffset"] = self.state.barrel_offset
        if hasattr(self.state, 'momentum_trap_distance') and self.state.momentum_trap_distance:
            state_data["https://dynamat.utep.edu/ontology#hasMomentumTrapTailoredDistance"] = self.state.momentum_trap_distance

        # Set form data if we have any
        if state_data:
            self.form_builder.set_form_data(self.form_widget, state_data)

    def _save_to_state(self) -> None:
        """Save current form data to state."""
        if not self.form_widget or not self.form_builder:
            return

        # Get all form data
        data = self.form_builder.get_form_data(self.form_widget)

        # Equipment URIs
        self.state.striker_bar_uri = data.get("https://dynamat.utep.edu/ontology#hasStrikerBar")
        self.state.incident_bar_uri = data.get("https://dynamat.utep.edu/ontology#hasIncidentBar")
        self.state.transmission_bar_uri = data.get("https://dynamat.utep.edu/ontology#hasTransmissionBar")
        self.state.incident_gauge_uri = data.get("https://dynamat.utep.edu/ontology#hasIncidentStrainGauge")
        self.state.transmission_gauge_uri = data.get("https://dynamat.utep.edu/ontology#hasTransmissionStrainGauge")
        self.state.momentum_trap_uri = data.get("https://dynamat.utep.edu/ontology#hasMomentumTrap")
        self.state.pulse_shaper_uri = data.get("https://dynamat.utep.edu/ontology#hasPulseShaper")

        # Test date
        self.state.test_date = data.get("https://dynamat.utep.edu/ontology#hasTestDate")

        # Measurement values
        self.state.striker_velocity = data.get("https://dynamat.utep.edu/ontology#hasStrikerVelocity")
        self.state.striker_launch_pressure = data.get("https://dynamat.utep.edu/ontology#hasStrikerLaunchPressure")
        self.state.barrel_offset = data.get("https://dynamat.utep.edu/ontology#hasBarrelOffset")
        self.state.momentum_trap_distance = data.get("https://dynamat.utep.edu/ontology#hasMomentumTrapTailoredDistance")

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
