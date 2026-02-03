"""Equipment Configuration Page - Ontology-driven form for SHPB analysis.

This page uses CustomizableFormBuilder to automatically generate the equipment
configuration form from the SHPBTestingConfiguration class definition in the ontology.

Form structure comes from gui:hasFormGroup annotations:
- EquipmentConfiguration: Bars, gauges, momentum trap, pulse shaper (custom builder)
- TestConditions: Velocity, pressure, date, lubrication, etc. (default builder)

Widget types and constraints are automatically inferred from ontology metadata.

The EquipmentConfiguration group uses a custom GroupBuilder that includes an
intermediate display widget showing derived properties from selected equipment
(bar wave speed, gauge factors, etc.).
"""

import logging
import re
from typing import Optional, Dict, Any, List, Tuple

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QGridLayout, QScrollArea,
    QWidget, QFrame, QFormLayout
)
from PyQt6.QtCore import Qt

from .base_page import BaseSHPBPage
from .....mechanical.shpb.io.specimen_loader import SpecimenLoader
from .....config import config
from .....ontology import PropertyMetadata
from ....builders.customizable_form_builder import CustomizableFormBuilder
from ....builders.group_builder import GroupBuilder
from ....core.form_manager import FormField

logger = logging.getLogger(__name__)


class EquipmentPage(BaseSHPBPage):
    """Equipment configuration page for SHPB analysis (ontology-driven with custom groups).

    Features:
    - Auto-generated form from SHPBTestingConfiguration ontology class
    - Automatic widget type inference (combos for equipment, unit widgets for measurements)
    - Constraint-based visibility (momentum trap distance only for TailoredGap)
    - Equipment property display (derived values from selected equipment via custom group builder)

    The form structure is entirely driven by GUI annotations in:
    - dynamat/ontology/class_properties/shpb_compression_class.ttl
    - dynamat/ontology/constraints/gui_shpb_rules.ttl

    Custom group rendering:
    - EquipmentConfiguration group uses nested _EquipmentPropertiesBuilder
    - Other groups use default QGroupBox + QFormLayout rendering
    """

    class _EquipmentPropertiesBuilder(GroupBuilder):
        """Custom builder for equipment configuration with derived properties display.

        This builder creates two sections:
        1. Standard form group for equipment selection (bars, gauges, etc.)
        2. Intermediate display showing derived properties from selected equipment
        """

        def build_group(
            self,
            group_name: str,
            properties: List[PropertyMetadata],
            parent: Optional[QWidget] = None
        ) -> Tuple[QWidget, Dict[str, FormField]]:
            """Build equipment group with standard form and properties display."""
            # Create container with vertical layout
            container = QWidget(parent)
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)

            # 1. Create standard form group for equipment selection
            equipment_group, form_fields = self._create_equipment_form(
                group_name, properties, container
            )
            layout.addWidget(equipment_group)

            # 2. Create intermediate display widget for derived properties
            properties_display = self._create_properties_display(container)
            layout.addWidget(properties_display)

            # Store references to display labels on container for external access
            container.wave_speed_label = self.wave_speed_label
            container.cross_section_label = self.cross_section_label
            container.elastic_modulus_label = self.elastic_modulus_label
            container.inc_gauge_factor_label = self.inc_gauge_factor_label
            container.inc_gauge_distance_label = self.inc_gauge_distance_label
            container.trans_gauge_factor_label = self.trans_gauge_factor_label
            container.trans_gauge_distance_label = self.trans_gauge_distance_label
            container.momentum_trap_distance_label = self.momentum_trap_distance_label

            return container, form_fields

        def _create_equipment_form(
            self,
            group_name: str,
            properties: List[PropertyMetadata],
            parent: QWidget
        ) -> Tuple[QGroupBox, Dict[str, FormField]]:
            """Create standard form group for equipment selection."""
            # Create QGroupBox with formatted title
            group_box = QGroupBox(self._format_group_name(group_name), parent)
            form_layout = QFormLayout(group_box)

            # Create widgets for all properties
            widgets = self.create_widgets_for_group(properties)

            # Add label-widget pairs
            form_fields = {}
            sorted_properties = sorted(properties, key=lambda p: p.display_order or 0)

            for prop in sorted_properties:
                if prop.uri not in widgets:
                    continue

                widget = widgets[prop.uri]

                # Create label
                label_text = prop.display_name or prop.name
                if prop.is_required:
                    label_text += " *"

                label = QLabel(label_text)

                # Add to form layout
                form_layout.addRow(label, widget)

                # Create FormField
                form_fields[prop.uri] = FormField(
                    widget=widget,
                    property_uri=prop.uri,
                    property_metadata=prop,
                    group_name=group_name,
                    required=prop.is_required,
                    label=label_text,
                    label_widget=label
                )

            return group_box, form_fields

        def _create_properties_display(self, parent: QWidget) -> QGroupBox:
            """Create intermediate display widget for derived equipment properties."""
            props_group = QGroupBox("Equipment Properties", parent)
            props_layout = QGridLayout(props_group)

            # Bar properties (derived from selected bar equipment)
            props_layout.addWidget(QLabel("Bar Wave Speed:"), 0, 0)
            self.wave_speed_label = QLabel("--")
            props_layout.addWidget(self.wave_speed_label, 0, 1)

            props_layout.addWidget(QLabel("Bar Cross Section:"), 1, 0)
            self.cross_section_label = QLabel("--")
            props_layout.addWidget(self.cross_section_label, 1, 1)

            props_layout.addWidget(QLabel("Bar Elastic Modulus:"), 2, 0)
            self.elastic_modulus_label = QLabel("--")
            props_layout.addWidget(self.elastic_modulus_label, 2, 1)

            # Strain gauge properties (derived from selected gauge equipment)
            props_layout.addWidget(QLabel("Incident Gauge Factor:"), 3, 0)
            self.inc_gauge_factor_label = QLabel("--")
            props_layout.addWidget(self.inc_gauge_factor_label, 3, 1)

            props_layout.addWidget(QLabel("Incident Gauge Distance:"), 4, 0)
            self.inc_gauge_distance_label = QLabel("--")
            props_layout.addWidget(self.inc_gauge_distance_label, 4, 1)

            props_layout.addWidget(QLabel("Transmission Gauge Factor:"), 5, 0)
            self.trans_gauge_factor_label = QLabel("--")
            props_layout.addWidget(self.trans_gauge_factor_label, 5, 1)

            props_layout.addWidget(QLabel("Transmission Gauge Distance:"), 6, 0)
            self.trans_gauge_distance_label = QLabel("--")
            props_layout.addWidget(self.trans_gauge_distance_label, 6, 1)

            # Momentum trap distance (from test conditions)
            props_layout.addWidget(QLabel("Momentum Trap Distance:"), 7, 0)
            self.momentum_trap_distance_label = QLabel("--")
            props_layout.addWidget(self.momentum_trap_distance_label, 7, 1)

            return props_group

        def _format_group_name(self, group_name: str) -> str:
            """Format group name for display (camelCase/snake_case to Title Case)."""
            formatted = re.sub(r'([a-z])([A-Z])', r'\1 \2', group_name)
            formatted = formatted.replace('_', ' ')
            return formatted.title()

    def __init__(self, state, ontology_manager, qudt_manager=None, parent=None):
        super().__init__(state, ontology_manager, qudt_manager, parent)

        self.setTitle("Configure Equipment")
        self.setSubTitle("Select the SHPB equipment and test conditions.")

        self.specimen_loader: Optional[SpecimenLoader] = None
        self.form_widget: Optional[QWidget] = None
        self.form_builder: Optional[CustomizableFormBuilder] = None
        self.equipment_container: Optional[QWidget] = None

    def _setup_ui(self) -> None:
        """Setup page UI using customizable form builder with equipment group builder."""
        layout = self._create_base_layout()

        # Create scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)

        # Initialize customizable form builder
        self.form_builder = CustomizableFormBuilder(self.ontology_manager)

        # Register custom builder for EquipmentConfiguration group
        # This will automatically include the equipment properties display
        equipment_builder = self._EquipmentPropertiesBuilder(
            self.form_builder.widget_factory
        )
        self.form_builder.register_group_builder(
            "EquipmentConfiguration",
            equipment_builder
        )

        # Build form from ontology for SHPBTestingConfiguration class
        try:
            self.form_widget = self.form_builder.build_form(
                "https://dynamat.utep.edu/ontology#SHPBTestingConfiguration",
                parent=content
            )

            if self.form_widget:
                content_layout.addWidget(self.form_widget)
                self.logger.info("Equipment form created from ontology with custom group builder")

                # Find the equipment container for property updates
                self._find_equipment_container()

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

    def _find_equipment_container(self) -> None:
        """Find the equipment container widget created by EquipmentPropertiesGroupBuilder.

        The custom group builder creates a container widget with references to the
        display labels. This method finds that container so we can update the displays
        when equipment selections change.
        """
        if not self.form_widget:
            return

        # The equipment container is the widget for one of the equipment properties
        # We'll search through form_fields to find it
        if hasattr(self.form_widget, 'form_fields'):
            for field in self.form_widget.form_fields.values():
                if field.group_name == "EquipmentConfiguration":
                    # Walk up the widget tree to find the container
                    widget = field.widget
                    while widget and widget != self.form_widget:
                        if hasattr(widget, 'wave_speed_label'):
                            # Found the equipment container
                            self.equipment_container = widget
                            # Store label references for convenience
                            self.wave_speed_label = widget.wave_speed_label
                            self.cross_section_label = widget.cross_section_label
                            self.elastic_modulus_label = widget.elastic_modulus_label
                            self.inc_gauge_factor_label = widget.inc_gauge_factor_label
                            self.inc_gauge_distance_label = widget.inc_gauge_distance_label
                            self.trans_gauge_factor_label = widget.trans_gauge_factor_label
                            self.trans_gauge_distance_label = widget.trans_gauge_distance_label
                            self.momentum_trap_distance_label = widget.momentum_trap_distance_label
                            self.logger.debug("Found equipment container with display labels")
                            return
                        widget = widget.parentWidget()

        self.logger.warning("Could not find equipment container widget")

    def initializePage(self) -> None:
        """Initialize page when it becomes current."""
        super().initializePage()

        # Initialize specimen loader for equipment property queries
        if self.specimen_loader is None:
            self._initialize_specimen_loader()

        # Restore previous selections if any
        self._restore_selections()

        # Connect equipment combo change handlers to update properties display
        self._connect_equipment_handlers()

        # Update properties display
        self._update_properties_display()

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

    def _connect_equipment_handlers(self) -> None:
        """Connect equipment selection changes to property display updates.

        Finds the equipment combo widgets in the generated form and connects
        them to update the equipment properties display.
        """
        if not self.form_widget or not hasattr(self.form_widget, 'form_fields'):
            return

        # Equipment properties that should trigger display updates
        equipment_properties = [
            "https://dynamat.utep.edu/ontology#hasIncidentBar",
            "https://dynamat.utep.edu/ontology#hasIncidentStrainGauge",
            "https://dynamat.utep.edu/ontology#hasTransmissionStrainGauge",
            "https://dynamat.utep.edu/ontology#hasMomentumTrapTailoredDistance"
        ]

        for prop_uri in equipment_properties:
            if prop_uri in self.form_widget.form_fields:
                widget = self.form_widget.form_fields[prop_uri].widget

                # Connect appropriate signal based on widget type
                if hasattr(widget, 'currentIndexChanged'):
                    # QComboBox
                    widget.currentIndexChanged.connect(self._update_properties_display)
                elif hasattr(widget, 'valueChanged'):
                    # UnitValueWidget
                    widget.valueChanged.connect(self._update_properties_display)

    def _update_properties_display(self) -> None:
        """Update equipment properties display from selected equipment.

        Queries ontology for properties of selected equipment individuals
        and displays them in the Equipment Properties section.
        """
        if not self.specimen_loader or not self.form_widget:
            return

        if not hasattr(self.form_widget, 'form_fields'):
            return

        try:
            form_fields = self.form_widget.form_fields

            # Get incident bar properties (use for display)
            incident_bar_uri_prop = "https://dynamat.utep.edu/ontology#hasIncidentBar"
            if incident_bar_uri_prop in form_fields:
                widget = form_fields[incident_bar_uri_prop].widget
                incident_bar_uri = widget.currentData() if hasattr(widget, 'currentData') else None

                if incident_bar_uri:
                    # Get bar properties
                    bar_props = self.specimen_loader.get_multiple_properties(
                        incident_bar_uri,
                        ['hasCrossSection', 'hasMaterial']
                    )

                    cross_section = bar_props.get('hasCrossSection')
                    if cross_section:
                        self.cross_section_label.setText(f"{cross_section:.2f} mm²")
                    else:
                        self.cross_section_label.setText("--")

                    # Get material properties
                    material_uri = bar_props.get('hasMaterial')
                    if material_uri:
                        mat_props = self.specimen_loader.get_multiple_properties(
                            material_uri,
                            ['hasWaveSpeed', 'hasElasticModulus']
                        )

                        wave_speed = mat_props.get('hasWaveSpeed')
                        elastic_mod = mat_props.get('hasElasticModulus')

                        if wave_speed:
                            self.wave_speed_label.setText(f"{wave_speed:.1f} m/s")
                        else:
                            self.wave_speed_label.setText("--")

                        if elastic_mod:
                            self.elastic_modulus_label.setText(f"{elastic_mod:.1f} GPa")
                        else:
                            self.elastic_modulus_label.setText("--")

            # Get gauge factors and distances
            inc_gauge_uri_prop = "https://dynamat.utep.edu/ontology#hasIncidentStrainGauge"
            trans_gauge_uri_prop = "https://dynamat.utep.edu/ontology#hasTransmissionStrainGauge"

            if inc_gauge_uri_prop in form_fields:
                widget = form_fields[inc_gauge_uri_prop].widget
                inc_gauge_uri = widget.currentData() if hasattr(widget, 'currentData') else None

                if inc_gauge_uri:
                    gauge_props = self.specimen_loader.get_multiple_properties(
                        inc_gauge_uri, ['hasGaugeFactor', 'hasDistanceFromSpecimen']
                    )
                    gf = gauge_props.get('hasGaugeFactor')
                    distance = gauge_props.get('hasDistanceFromSpecimen')

                    self.inc_gauge_factor_label.setText(f"{gf:.3f}" if gf else "--")
                    self.inc_gauge_distance_label.setText(f"{distance:.1f} mm" if distance else "--")
                else:
                    self.inc_gauge_factor_label.setText("--")
                    self.inc_gauge_distance_label.setText("--")

            if trans_gauge_uri_prop in form_fields:
                widget = form_fields[trans_gauge_uri_prop].widget
                trans_gauge_uri = widget.currentData() if hasattr(widget, 'currentData') else None

                if trans_gauge_uri:
                    gauge_props = self.specimen_loader.get_multiple_properties(
                        trans_gauge_uri, ['hasGaugeFactor', 'hasDistanceFromSpecimen']
                    )
                    gf = gauge_props.get('hasGaugeFactor')
                    distance = gauge_props.get('hasDistanceFromSpecimen')

                    self.trans_gauge_factor_label.setText(f"{gf:.3f}" if gf else "--")
                    self.trans_gauge_distance_label.setText(f"{distance:.1f} mm" if distance else "--")
                else:
                    self.trans_gauge_factor_label.setText("--")
                    self.trans_gauge_distance_label.setText("--")

            # Get momentum trap distance from test conditions widget
            mtrap_dist_prop = "https://dynamat.utep.edu/ontology#hasMomentumTrapTailoredDistance"
            if mtrap_dist_prop in form_fields:
                widget = form_fields[mtrap_dist_prop].widget
                try:
                    if hasattr(widget, 'getData'):
                        mtrap_data = widget.getData()
                        mtrap_value = mtrap_data.get('value', 0)
                        mtrap_unit = mtrap_data.get('unit_symbol', 'mm')

                        if mtrap_value > 0:
                            self.momentum_trap_distance_label.setText(f"{mtrap_value:.1f} {mtrap_unit}")
                        else:
                            self.momentum_trap_distance_label.setText("--")
                except Exception as e:
                    self.logger.debug(f"Could not get momentum trap distance: {e}")
                    self.momentum_trap_distance_label.setText("--")

        except Exception as e:
            self.logger.warning(f"Failed to update properties display: {e}")

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
