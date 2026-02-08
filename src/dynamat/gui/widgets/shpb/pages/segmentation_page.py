"""Segmentation Page - Extract and center pulse segments."""

import logging
from typing import Optional

import numpy as np

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QSplitter, QFrame, QWidget
)
from PyQt6.QtCore import Qt
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, XSD

from .base_page import BaseSHPBPage
from .....mechanical.shpb.core.pulse_windows import PulseDetector
from ...base.plotting import create_plot_widget
from ....builders.customizable_form_builder import CustomizableFormBuilder

logger = logging.getLogger(__name__)

DYN_NS = "https://dynamat.utep.edu/ontology#"


class SegmentationPage(BaseSHPBPage):
    """Pulse segmentation page for SHPB analysis.

    Features:
    - Configure segment length (n_points)
    - Set noise threshold ratio
    - Visualize centered segments
    """

    def __init__(self, state, ontology_manager, qudt_manager=None, parent=None):
        super().__init__(state, ontology_manager, qudt_manager, parent)

        self.setTitle("Segment Pulses")
        self.setSubTitle("Extract and center pulse segments from detected windows.")

        self.plot_widget = None

        # Ontology-driven form
        self.form_builder = CustomizableFormBuilder(ontology_manager)
        self._form_widget: Optional[QWidget] = None

    def _setup_ui(self) -> None:
        """Setup page UI with ontology-driven form."""
        layout = self._create_base_layout()

        # Create splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Parameters
        params_frame = QFrame()
        params_layout = QVBoxLayout(params_frame)

        # Ontology-driven segmentation parameters form
        SEGMENTATION_CLASS = f"{DYN_NS}SegmentationParams"
        self._form_widget = self.form_builder.build_form(
            SEGMENTATION_CLASS, parent=params_frame
        )
        params_layout.addWidget(self._form_widget)

        # Info label
        info_label = QLabel(
            "Threshold ratio controls noise suppression.\n"
            "Lower values preserve more signal detail.\n"
            "Typical range: 0.005 - 0.05"
        )
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        params_layout.addWidget(info_label)

        # Segment button
        segment_btn = QPushButton("Segment All Pulses")
        segment_btn.clicked.connect(self._segment_pulses)
        params_layout.addWidget(segment_btn)

        # Results display
        results_group = self._create_group_box("Segmentation Results")
        results_layout = QGridLayout(results_group)

        self.result_labels = {}
        for row, pulse_type in enumerate(['incident', 'transmitted', 'reflected']):
            results_layout.addWidget(QLabel(f"{pulse_type.capitalize()}:"), row, 0)
            label = QLabel("Not segmented")
            label.setStyleSheet("color: gray;")
            self.result_labels[pulse_type] = label
            results_layout.addWidget(label, row, 1)

        # Centering shifts
        results_layout.addWidget(QLabel(""), 3, 0)  # Spacer
        results_layout.addWidget(QLabel("Centering Shifts:"), 4, 0, 1, 2)

        self.shift_labels = {}
        for row, pulse_type in enumerate(['incident', 'transmitted', 'reflected'], start=5):
            results_layout.addWidget(QLabel(f"  {pulse_type.capitalize()}:"), row, 0)
            label = QLabel("--")
            self.shift_labels[pulse_type] = label
            results_layout.addWidget(label, row, 1)

        params_layout.addWidget(results_group)
        params_layout.addStretch()

        splitter.addWidget(params_frame)

        # Right: Plot
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
        splitter.setSizes([350, 650])

        layout.addWidget(splitter)
        self._add_status_area()

    def initializePage(self) -> None:
        """Initialize page when it becomes current."""
        super().initializePage()

        # Restore parameters from state
        self._restore_params()

        # If already segmented, show results
        if self.state.has_segmented_pulses():
            self._update_results_display()
            self._update_plot()

    def validatePage(self) -> bool:
        """Validate before allowing Next."""
        if not self.state.has_segmented_pulses():
            self.show_warning(
                "Segmentation Required",
                "Please segment all pulses before continuing."
            )
            return False

        # Save parameters
        self._save_params()

        # Run SHACL validation on partial graph
        validation_graph = self._build_validation_graph()
        if validation_graph and not self._validate_page_data(
            validation_graph, page_key="segmentation"
        ):
            return False

        return True

    def _build_validation_graph(self) -> Optional[Graph]:
        """Build partial RDF graph for SHACL validation of segmentation data.

        Returns:
            RDF graph with SegmentationParams instance, or None on error.
        """
        if not self.state.segmentation_form_data:
            return None

        try:
            DYN = Namespace(DYN_NS)
            g = Graph()
            g.bind("dyn", DYN)

            instance = DYN["_val_segmentation"]
            g.add((instance, RDF.type, DYN.SegmentationParams))

            form_data = self.state.segmentation_form_data

            # hasSegmentPoints -> xsd:integer
            seg_points = form_data.get(f"{DYN_NS}hasSegmentPoints")
            if seg_points is not None:
                g.add((instance, DYN.hasSegmentPoints,
                       Literal(int(seg_points), datatype=XSD.integer)))

            # hasSegmentThreshold -> xsd:double
            threshold = form_data.get(f"{DYN_NS}hasSegmentThreshold")
            if threshold is not None:
                g.add((instance, DYN.hasSegmentThreshold,
                       Literal(float(threshold), datatype=XSD.double)))

            return g

        except Exception as e:
            self.logger.error(f"Failed to build validation graph: {e}")
            return None

    def _restore_params(self) -> None:
        """Restore parameters from state form data to ontology form."""
        if self.state.segmentation_form_data:
            self.form_builder.set_form_data(self._form_widget, self.state.segmentation_form_data)

    def _save_params(self) -> None:
        """Save parameters from ontology form to state as form-data dict."""
        self.state.segmentation_form_data = self.form_builder.get_form_data(self._form_widget)

    def _get_n_points(self) -> int:
        """Get segment points from form data."""
        form_data = self.form_builder.get_form_data(self._form_widget)
        return form_data.get(f"{DYN_NS}hasSegmentPoints", 25000)

    def _get_thresh_ratio(self) -> float:
        """Get threshold ratio from form data."""
        form_data = self.form_builder.get_form_data(self._form_widget)
        return form_data.get(f"{DYN_NS}hasSegmentThreshold", 0.01)

    def _segment_pulses(self) -> None:
        """Segment all detected pulses."""
        self.show_progress()
        self.set_status("Segmenting pulses...")

        try:
            # Get parameters from form
            n_points = self._get_n_points()
            thresh_ratio = self._get_thresh_ratio()

            # Get raw signals
            incident_signal = self.state.get_raw_signal('incident')
            transmitted_signal = self.state.get_raw_signal('transmitted')

            if incident_signal is None or transmitted_signal is None:
                raise ValueError("Raw signals not available")

            # Segment each pulse
            for pulse_type in ['incident', 'transmitted', 'reflected']:
                window = self.state.pulse_windows.get(pulse_type)
                if not window:
                    raise ValueError(f"No window detected for {pulse_type}")

                # Get appropriate signal
                if pulse_type == 'reflected':
                    signal = incident_signal
                    polarity = 'tensile'
                elif pulse_type == 'incident':
                    signal = incident_signal
                    polarity = 'compressive'
                else:
                    signal = transmitted_signal
                    polarity = 'compressive'

                # Get detector parameters from detection form data
                detect_form = self.state.detection_form_data.get(pulse_type, {})
                pulse_points = detect_form.get(f"{DYN_NS}hasPulsePoints", 15000)

                # Create detector for segmentation
                detector = PulseDetector(
                    pulse_points=pulse_points,
                    polarity=polarity
                )

                # Segment and center
                segment = detector.segment_and_center(
                    signal,
                    window,
                    n_points,
                    polarity=polarity,
                    thresh_ratio=thresh_ratio,
                    debug=True
                )

                # Store results
                self.state.segmented_pulses[pulse_type] = segment

                # Calculate centering shift approximation
                idx = np.arange(len(segment))
                energy = segment ** 2
                if np.sum(energy) > 0:
                    c = int(np.round(np.sum(idx * energy) / np.sum(energy)))
                    shift = (n_points // 2) - c
                else:
                    shift = 0

                self.state.centering_shifts[pulse_type] = shift

                self.logger.info(f"Segmented {pulse_type}: {len(segment)} points, shift={shift}")

            # Save form data with computed values
            self._save_params()

            # Update display
            self._update_results_display()
            self._update_plot()

            self.set_status("All pulses segmented successfully")

        except Exception as e:
            self.logger.error(f"Segmentation failed: {e}")
            self.set_status(f"Error: {e}", is_error=True)
            self.show_error("Segmentation Failed", str(e))

        finally:
            self.hide_progress()

    def _update_results_display(self) -> None:
        """Update results labels."""
        for pulse_type in ['incident', 'transmitted', 'reflected']:
            segment = self.state.segmented_pulses.get(pulse_type)
            shift = self.state.centering_shifts.get(pulse_type)

            if segment is not None:
                # Calculate some stats
                peak = np.max(np.abs(segment))
                nonzero = np.count_nonzero(segment)

                self.result_labels[pulse_type].setText(
                    f"{len(segment):,} pts, peak={peak:.4e}, nonzero={nonzero:,}"
                )
                self.result_labels[pulse_type].setStyleSheet("color: green;")

                if shift is not None:
                    self.shift_labels[pulse_type].setText(f"{shift:+d} pts")
            else:
                self.result_labels[pulse_type].setText("Not segmented")
                self.result_labels[pulse_type].setStyleSheet("color: gray;")
                self.shift_labels[pulse_type].setText("--")

    def _update_plot(self) -> None:
        """Update plot with segmented pulses."""
        if not self.plot_widget:
            return

        try:
            self.plot_widget.clear()

            n_points = self._get_n_points()

            # Create time vector for segment
            sampling_interval = self.state.sampling_interval or 1.0
            time = np.arange(n_points) * sampling_interval

            # Plot each segment
            colors = {
                'incident': 'blue',
                'transmitted': 'red',
                'reflected': 'green'
            }

            for pulse_type, segment in self.state.segmented_pulses.items():
                if segment is not None:
                    self.plot_widget.add_trace(
                        time[:len(segment)],
                        segment,
                        label=pulse_type.capitalize(),
                        color=colors.get(pulse_type, 'gray')
                    )

            self.plot_widget.set_xlabel("Time (ms)")
            self.plot_widget.set_ylabel("Signal")
            self.plot_widget.enable_grid()
            self.plot_widget.enable_legend()
            self.plot_widget.refresh()

        except Exception as e:
            self.logger.error(f"Failed to update plot: {e}")
