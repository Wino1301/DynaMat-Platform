"""Segmentation Page - Extract and center pulse segments."""

import logging
from typing import Optional

import numpy as np

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QSpinBox, QDoubleSpinBox,
    QSplitter, QFrame
)
from PyQt6.QtCore import Qt

from .base_page import BaseSHPBPage
from .....mechanical.shpb.core.pulse_windows import PulseDetector
from ...base.plot_widget_factory import create_plot_widget

logger = logging.getLogger(__name__)


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

    def _setup_ui(self) -> None:
        """Setup page UI."""
        layout = self._create_base_layout()

        # Create splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Parameters
        params_frame = QFrame()
        params_layout = QVBoxLayout(params_frame)

        # Segmentation parameters
        params_group = self._create_group_box("Segmentation Parameters")
        params_grid = QGridLayout(params_group)

        params_grid.addWidget(QLabel("Segment Length (n_points):"), 0, 0)
        self.n_points_spin = QSpinBox()
        self.n_points_spin.setRange(1000, 100000)
        self.n_points_spin.setValue(25000)
        self.n_points_spin.setSingleStep(1000)
        params_grid.addWidget(self.n_points_spin, 0, 1)

        params_grid.addWidget(QLabel("Threshold Ratio:"), 1, 0)
        self.thresh_spin = QDoubleSpinBox()
        self.thresh_spin.setRange(0.001, 0.5)
        self.thresh_spin.setValue(0.01)
        self.thresh_spin.setDecimals(3)
        self.thresh_spin.setSingleStep(0.005)
        params_grid.addWidget(self.thresh_spin, 1, 1)

        info_label = QLabel(
            "Threshold ratio controls noise suppression.\n"
            "Lower values preserve more signal detail.\n"
            "Typical range: 0.005 - 0.05"
        )
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        params_grid.addWidget(info_label, 2, 0, 1, 2)

        params_layout.addWidget(params_group)

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
        self.n_points_spin.setValue(self.state.segment_n_points)
        self.thresh_spin.setValue(self.state.segment_thresh_ratio)

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
        self.state.segment_n_points = self.n_points_spin.value()
        self.state.segment_thresh_ratio = self.thresh_spin.value()

        return True

    def _segment_pulses(self) -> None:
        """Segment all detected pulses."""
        self.show_progress()
        self.set_status("Segmenting pulses...")

        try:
            n_points = self.n_points_spin.value()
            thresh_ratio = self.thresh_spin.value()

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

                # Get detector parameters
                params = self.state.detection_params.get(pulse_type, {})
                pulse_points = params.get('pulse_points', 15000)

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

                # Calculate centering shift
                i0, i1 = window
                half_pad = max(0, (n_points - (i1 - i0)) // 2)
                start = max(0, i0 - half_pad)

                # Store results
                self.state.segmented_pulses[pulse_type] = segment

                # Note: The shift is calculated internally in segment_and_center
                # We approximate it here based on the energy centering
                idx = np.arange(len(segment))
                energy = segment ** 2
                if np.sum(energy) > 0:
                    c = int(np.round(np.sum(idx * energy) / np.sum(energy)))
                    shift = (n_points // 2) - c
                else:
                    shift = 0

                self.state.centering_shifts[pulse_type] = shift

                self.logger.info(f"Segmented {pulse_type}: {len(segment)} points, shift={shift}")

            # Update state
            self.state.segment_n_points = n_points
            self.state.segment_thresh_ratio = thresh_ratio

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

            n_points = self.state.segment_n_points

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
            self.plot_widget.refresh()

        except Exception as e:
            self.logger.error(f"Failed to update plot: {e}")
