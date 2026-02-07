"""Pulse Detection Page - Detect incident, transmitted, and reflected pulse windows."""

import logging
from typing import Optional, Dict, Tuple, Any
from datetime import datetime

import numpy as np

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QSplitter, QFrame, QTabWidget, QWidget
)
from PyQt6.QtCore import Qt
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, XSD

from .base_page import BaseSHPBPage
from .....mechanical.shpb.core.pulse_windows import PulseDetector
from ...base.plotting import create_plot_widget
from ....builders.customizable_form_builder import CustomizableFormBuilder

logger = logging.getLogger(__name__)

DYN_NS = "https://dynamat.utep.edu/ontology#"


class PulseDetectionPage(BaseSHPBPage):
    """Pulse detection page for SHPB analysis.

    Features:
    - Configure detection parameters for each pulse type
    - Interactive search bounds adjustment
    - Visualization of detected windows
    - Automatic detection with manual override
    """

    def __init__(self, state, ontology_manager, qudt_manager=None, parent=None):
        super().__init__(state, ontology_manager, qudt_manager, parent)

        self.setTitle("Detect Pulses")
        self.setSubTitle("Configure detection parameters and find pulse windows.")

        self.detectors: Dict[str, PulseDetector] = {}
        self.plot_widget = None

        # Ontology-driven form components
        self.form_builder = CustomizableFormBuilder(ontology_manager)
        self._pulse_forms: Dict[str, QWidget] = {}  # pulse_type -> form widget
        self._form_fields: Dict[str, Dict[str, Any]] = {}  # pulse_type -> {uri -> FormField}

    def _setup_ui(self) -> None:
        """Setup page UI with ontology-driven forms."""
        layout = self._create_base_layout()

        # Create splitter for params and plot
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: Parameters
        params_frame = QFrame()
        params_layout = QVBoxLayout(params_frame)

        # Tab widget for each pulse type with ontology-generated forms
        self.pulse_tabs = QTabWidget()

        DYN_CLASS = "https://dynamat.utep.edu/ontology#PulseDetectionParams"
        for pulse_type in ['incident', 'transmitted', 'reflected']:
            form_widget = self.form_builder.build_form(DYN_CLASS, parent=self.pulse_tabs)

            self._pulse_forms[pulse_type] = form_widget
            self._form_fields[pulse_type] = form_widget.form_fields

            self.pulse_tabs.addTab(form_widget, pulse_type.capitalize())

        params_layout.addWidget(self.pulse_tabs)

        # Detection buttons
        btn_layout = QHBoxLayout()

        detect_current_btn = QPushButton("Detect Current")
        detect_current_btn.clicked.connect(self._detect_current_pulse)
        btn_layout.addWidget(detect_current_btn)

        detect_all_btn = QPushButton("Detect All")
        detect_all_btn.clicked.connect(self._detect_all_pulses)
        btn_layout.addWidget(detect_all_btn)

        params_layout.addLayout(btn_layout)

        # Detection results
        results_group = self._create_group_box("Detection Results")
        results_layout = QGridLayout(results_group)

        self.result_labels = {}
        for row, pulse_type in enumerate(['incident', 'transmitted', 'reflected']):
            results_layout.addWidget(QLabel(f"{pulse_type.capitalize()}:"), row, 0)
            label = QLabel("Not detected")
            label.setStyleSheet("color: gray;")
            self.result_labels[pulse_type] = label
            results_layout.addWidget(label, row, 1)

        params_layout.addWidget(results_group)

        splitter.addWidget(params_frame)

        # Right side: Plot
        plot_frame = QFrame()
        plot_layout = QVBoxLayout(plot_frame)

        try:
            self.plot_widget = create_plot_widget(
                self.ontology_manager,
                self.qudt_manager,
                show_toolbar=True
            )
            plot_layout.addWidget(self.plot_widget)
        except Exception as e:
            logger.warning(f"Could not create plot widget: {e}")
            plot_layout.addWidget(QLabel("Plot unavailable"))

        splitter.addWidget(plot_frame)

        # Set splitter sizes (40% params, 60% plot)
        splitter.setSizes([400, 600])

        layout.addWidget(splitter)
        self._add_status_area()

    def initializePage(self) -> None:
        """Initialize page when it becomes current."""
        super().initializePage()

        # Restore parameters from state
        self._restore_params()

        # Update plot with raw signals
        self._update_plot()

        # If windows already detected, show them
        if self.state.has_detected_pulses():
            self._update_results_display()
            self._update_plot()

    def validatePage(self) -> bool:
        """Validate before allowing Next."""
        if not self.state.has_detected_pulses():
            self.show_warning(
                "Detection Required",
                "Please detect all pulse windows before continuing."
            )
            return False

        # Save parameters to state
        self._save_params()

        # Run SHACL validation on partial graph
        validation_graph = self._build_validation_graph()
        if validation_graph and not self._validate_page_data(validation_graph):
            return False

        return True

    def _build_validation_graph(self) -> Optional[Graph]:
        """Build partial RDF graph for SHACL validation of pulse detection data.

        Creates one PulseDetectionParams instance per pulse type.

        Returns:
            RDF graph with PulseDetectionParams instances, or None on error.
        """
        try:
            DYN = Namespace(DYN_NS)
            g = Graph()
            g.bind("dyn", DYN)

            object_properties = {"hasDetectionPolarity", "hasSelectionMetric", "appliedToSeries"}
            integer_properties = {
                "hasDetectionLowerBound", "hasDetectionUpperBound",
                "hasPulsePoints", "hasMinSeparation",
                "hasStartIndex", "hasEndIndex", "hasWindowLength",
            }

            for pulse_type in ["incident", "transmitted", "reflected"]:
                form_data = self.state.detection_form_data.get(pulse_type, {})
                if not form_data:
                    continue

                instance = DYN[f"_val_{pulse_type}_detection"]
                g.add((instance, RDF.type, DYN.PulseDetectionParams))

                for uri, value in form_data.items():
                    if value is None:
                        continue

                    prop_name = uri.split("#")[-1] if "#" in uri else uri.split("/")[-1]
                    prop = DYN[prop_name]

                    if prop_name in object_properties:
                        if isinstance(value, str) and value:
                            g.add((instance, prop, URIRef(value)))
                    elif prop_name in integer_properties:
                        try:
                            g.add((instance, prop, Literal(int(value), datatype=XSD.integer)))
                        except (ValueError, TypeError):
                            pass
                    elif prop_name == "hasKTrials":
                        g.add((instance, prop, Literal(str(value), datatype=XSD.string)))
                    else:
                        try:
                            g.add((instance, prop, Literal(float(value), datatype=XSD.double)))
                        except (ValueError, TypeError):
                            g.add((instance, prop, Literal(str(value), datatype=XSD.string)))

            return g

        except Exception as e:
            self.logger.error(f"Failed to build validation graph: {e}")
            return None

    def _parse_k_trials(self, k_str: str) -> Tuple[float, ...]:
        """Parse comma-separated k_trials string to tuple."""
        try:
            return tuple(float(k.strip()) for k in k_str.split(','))
        except (ValueError, AttributeError):
            logger.warning(f"Invalid k_trials format: {k_str}, using defaults")
            return (6000.0, 4000.0, 2000.0)

    def _get_polarity_value(self, polarity_uri: Optional[str]) -> str:
        """Get polarity string value from individual URI."""
        if not polarity_uri:
            return "compressive"

        try:
            query = f"""
            PREFIX dyn: <https://dynamat.utep.edu/ontology#>
            SELECT ?value WHERE {{
                <{polarity_uri}> dyn:hasPolarityValue ?value .
            }}
            """
            results = self.ontology_manager.sparql_executor.execute_query(query)
            return str(results[0]['value']) if results else "compressive"
        except Exception as e:
            logger.warning(f"Failed to get polarity value: {e}")
            return "compressive"

    def _get_metric_value(self, metric_uri: Optional[str]) -> str:
        """Get metric string value from individual URI."""
        if not metric_uri:
            return "median"

        try:
            query = f"""
            PREFIX dyn: <https://dynamat.utep.edu/ontology#>
            SELECT ?value WHERE {{
                <{metric_uri}> dyn:hasMetricValue ?value .
            }}
            """
            results = self.ontology_manager.sparql_executor.execute_query(query)
            return str(results[0]['value']) if results else "median"
        except Exception as e:
            logger.warning(f"Failed to get metric value: {e}")
            return "median"

    def _find_polarity_uri(self, polarity_str: str) -> Optional[str]:
        """Find PolarityType individual URI by string value."""
        try:
            query = f"""
            PREFIX dyn: <https://dynamat.utep.edu/ontology#>
            SELECT ?individual WHERE {{
                ?individual a dyn:PolarityType ;
                            dyn:hasPolarityValue "{polarity_str}" .
            }}
            """
            results = self.ontology_manager.sparql_executor.execute_query(query)
            return str(results[0]['individual']) if results else None
        except Exception as e:
            logger.warning(f"Failed to find polarity URI: {e}")
            return None

    def _find_metric_uri(self, metric_str: str) -> Optional[str]:
        """Find DetectionMetric individual URI by string value."""
        try:
            query = f"""
            PREFIX dyn: <https://dynamat.utep.edu/ontology#>
            SELECT ?individual WHERE {{
                ?individual a dyn:DetectionMetric ;
                            dyn:hasMetricValue "{metric_str}" .
            }}
            """
            results = self.ontology_manager.sparql_executor.execute_query(query)
            return str(results[0]['individual']) if results else None
        except Exception as e:
            logger.warning(f"Failed to find metric URI: {e}")
            return None

    def _restore_params(self) -> None:
        """Restore parameters from state form data to all three forms."""
        for pulse_type in ['incident', 'transmitted', 'reflected']:
            form_data = self.state.detection_form_data.get(pulse_type)
            if form_data:
                form_widget = self._pulse_forms[pulse_type]
                self.form_builder.set_form_data(form_widget, form_data)

    def _save_params(self) -> None:
        """Save parameters from all forms to state as form-data dicts.

        Injects computed output properties (window indices) into the form data.
        """
        for pulse_type in ['incident', 'transmitted', 'reflected']:
            form_widget = self._pulse_forms[pulse_type]
            form_data = self.form_builder.get_form_data(form_widget)

            # Inject computed window output properties
            window = self.state.pulse_windows.get(pulse_type)
            if window:
                form_data[f"{DYN_NS}hasStartIndex"] = window[0]
                form_data[f"{DYN_NS}hasEndIndex"] = window[1]
                form_data[f"{DYN_NS}hasWindowLength"] = window[1] - window[0]

            # Inject appliedToSeries link
            if self.state.test_id:
                form_data[f"{DYN_NS}appliedToSeries"] = f"dyn:{self.state.test_id}_{pulse_type}"

            self.state.detection_form_data[pulse_type] = form_data

    def _get_current_params(self, pulse_type: str) -> Dict:
        """Extract parameters for PulseDetector from ontology form.

        Args:
            pulse_type: Pulse type

        Returns:
            Parameters dictionary
        """
        form_widget = self._pulse_forms[pulse_type]
        form_data = self.form_builder.get_form_data(form_widget)

        # Map ontology properties to PulseDetector kwargs
        params = {
            'pulse_points': form_data.get(f"{DYN_NS}hasPulsePoints", 15000),
            'k_trials': self._parse_k_trials(
                form_data.get(f"{DYN_NS}hasKTrials", "6000,4000,2000")
            ),
            'polarity': self._get_polarity_value(
                form_data.get(f"{DYN_NS}hasDetectionPolarity")
            ),
            'min_separation': form_data.get(f"{DYN_NS}hasMinSeparation"),
        }

        # Detection parameters (passed to find_window)
        params['lower_bound'] = form_data.get(f"{DYN_NS}hasDetectionLowerBound")
        params['upper_bound'] = form_data.get(f"{DYN_NS}hasDetectionUpperBound")
        params['metric'] = self._get_metric_value(
            form_data.get(f"{DYN_NS}hasSelectionMetric")
        )

        return params

    def _detect_current_pulse(self) -> None:
        """Detect pulse for currently selected tab."""
        tab_index = self.pulse_tabs.currentIndex()
        pulse_type = ['incident', 'transmitted', 'reflected'][tab_index]
        self._detect_pulse(pulse_type)

    def _detect_all_pulses(self) -> None:
        """Detect all pulse windows."""
        self.show_progress()
        self.set_status("Detecting pulses...")

        try:
            for pulse_type in ['incident', 'transmitted', 'reflected']:
                self._detect_pulse(pulse_type)

            self.set_status("All pulses detected")

        except Exception as e:
            self.show_error("Detection Failed", str(e))

        finally:
            self.hide_progress()

    def _detect_pulse(self, pulse_type: str) -> None:
        """Detect a specific pulse window.

        Args:
            pulse_type: 'incident', 'transmitted', or 'reflected'
        """
        try:
            params = self._get_current_params(pulse_type)

            # Get signal
            if pulse_type == 'reflected':
                # Reflected is on the incident bar signal
                signal = self.state.get_raw_signal('incident')
            else:
                signal = self.state.get_raw_signal(pulse_type)

            if signal is None:
                raise ValueError(f"No signal data for {pulse_type}")

            # Create detector
            detector = PulseDetector(
                pulse_points=params['pulse_points'],
                k_trials=params['k_trials'],
                polarity=params['polarity'],
                min_separation=params['min_separation']
            )

            # Detect window
            window = detector.find_window(
                signal,
                lower_bound=params['lower_bound'],
                upper_bound=params['upper_bound'],
                metric=params['metric'],
                debug=True
            )

            # Store results
            self.state.pulse_windows[pulse_type] = window
            self.detectors[pulse_type] = detector

            # Update display
            self._update_result_label(pulse_type, window)
            self._update_plot()

            logger.info(f"Detected {pulse_type} window: {window}")

        except Exception as e:
            self.logger.error(f"Failed to detect {pulse_type}: {e}")
            self._update_result_label(pulse_type, None, str(e))
            raise

    def _update_result_label(
        self,
        pulse_type: str,
        window: Optional[Tuple[int, int]],
        error: str = None
    ) -> None:
        """Update result label for a pulse type."""
        label = self.result_labels.get(pulse_type)
        if not label:
            return

        if error:
            label.setText(f"Error: {error}")
            label.setStyleSheet("color: red;")
        elif window:
            label.setText(f"[{window[0]:,} - {window[1]:,}] ({window[1]-window[0]:,} pts)")
            label.setStyleSheet("color: green;")
        else:
            label.setText("Not detected")
            label.setStyleSheet("color: gray;")

    def _update_results_display(self) -> None:
        """Update all result labels from state."""
        for pulse_type in ['incident', 'transmitted', 'reflected']:
            window = self.state.pulse_windows.get(pulse_type)
            self._update_result_label(pulse_type, window)

    def _update_plot(self) -> None:
        """Update plot with raw signals and detected windows."""
        if not self.plot_widget:
            return

        try:
            self.plot_widget.clear()

            # Get time and signals
            time = self.state.get_raw_signal('time')
            incident = self.state.get_raw_signal('incident')
            transmitted = self.state.get_raw_signal('transmitted')

            if time is None:
                return

            # Plot raw signals
            if incident is not None:
                self.plot_widget.add_ontology_trace(
                    time, incident,
                    x_series_type_uri='dyn:Time',
                    y_series_type_uri='dyn:IncidentPulse',
                    label="Incident Bar", color="blue"
                )

            if transmitted is not None:
                self.plot_widget.add_ontology_trace(
                    time, transmitted,
                    y_series_type_uri='dyn:TransmittedPulse',
                    label="Transmitted Bar", color="red"
                )

            # Overlay detected windows
            colors = {'incident': 'cyan', 'transmitted': 'orange', 'reflected': 'magenta'}

            for pulse_type, window in self.state.pulse_windows.items():
                if window:
                    start, end = window
                    signal = incident if pulse_type in ['incident', 'reflected'] else transmitted

                    if signal is not None and start < len(time) and end <= len(time):
                        self.plot_widget.add_trace(
                            time[start:end],
                            signal[start:end],
                            label=f"{pulse_type.capitalize()} Window",
                            color=colors.get(pulse_type, 'gray')
                        )

            self.plot_widget.enable_grid()
            self.plot_widget.enable_legend()
            self.plot_widget.refresh()

        except Exception as e:
            self.logger.error(f"Failed to update plot: {e}")
