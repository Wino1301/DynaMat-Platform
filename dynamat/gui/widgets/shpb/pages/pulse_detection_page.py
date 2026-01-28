"""Pulse Detection Page - Detect incident, transmitted, and reflected pulse windows."""

import logging
from typing import Optional, Dict, Tuple

import numpy as np

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QSpinBox, QLineEdit,
    QComboBox, QSplitter, QFrame, QTabWidget, QWidget
)
from PyQt6.QtCore import Qt

from .base_page import BaseSHPBPage
from .....mechanical.shpb.core.pulse_windows import PulseDetector
from ...base.plot_widget_factory import create_plot_widget

logger = logging.getLogger(__name__)


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

    def _setup_ui(self) -> None:
        """Setup page UI."""
        layout = self._create_base_layout()

        # Create splitter for params and plot
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: Parameters
        params_frame = QFrame()
        params_layout = QVBoxLayout(params_frame)

        # Tab widget for each pulse type
        self.pulse_tabs = QTabWidget()

        for pulse_type in ['incident', 'transmitted', 'reflected']:
            tab = self._create_pulse_params_tab(pulse_type)
            self.pulse_tabs.addTab(tab, pulse_type.capitalize())

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

    def _create_pulse_params_tab(self, pulse_type: str) -> QWidget:
        """Create parameters tab for a pulse type.

        Args:
            pulse_type: 'incident', 'transmitted', or 'reflected'

        Returns:
            Tab widget
        """
        tab = QWidget()
        layout = QGridLayout(tab)

        row = 0

        # Pulse points
        layout.addWidget(QLabel("Pulse Points:"), row, 0)
        pulse_points_spin = QSpinBox()
        pulse_points_spin.setRange(1000, 100000)
        pulse_points_spin.setValue(15000)
        pulse_points_spin.setSingleStep(1000)
        pulse_points_spin.setObjectName(f"{pulse_type}_pulse_points")
        layout.addWidget(pulse_points_spin, row, 1)
        row += 1

        # K trials
        layout.addWidget(QLabel("K Trials:"), row, 0)
        k_trials_edit = QLineEdit("6000,4000,2000")
        k_trials_edit.setObjectName(f"{pulse_type}_k_trials")
        layout.addWidget(k_trials_edit, row, 1)
        row += 1

        # Polarity
        layout.addWidget(QLabel("Polarity:"), row, 0)
        polarity_combo = QComboBox()
        polarity_combo.addItem("Compressive", "compressive")
        polarity_combo.addItem("Tensile", "tensile")
        polarity_combo.setObjectName(f"{pulse_type}_polarity")
        # Set default polarity based on pulse type
        if pulse_type == 'reflected':
            polarity_combo.setCurrentIndex(1)  # Tensile
        layout.addWidget(polarity_combo, row, 1)
        row += 1

        # Detection metric
        layout.addWidget(QLabel("Detection Metric:"), row, 0)
        metric_combo = QComboBox()
        metric_combo.addItem("Median", "median")
        metric_combo.addItem("Peak", "peak")
        metric_combo.setObjectName(f"{pulse_type}_metric")
        layout.addWidget(metric_combo, row, 1)
        row += 1

        # Search bounds
        layout.addWidget(QLabel("Lower Bound:"), row, 0)
        lower_spin = QSpinBox()
        lower_spin.setRange(0, 1000000)
        lower_spin.setValue(0)
        lower_spin.setSpecialValueText("Auto")
        lower_spin.setObjectName(f"{pulse_type}_lower_bound")
        layout.addWidget(lower_spin, row, 1)
        row += 1

        layout.addWidget(QLabel("Upper Bound:"), row, 0)
        upper_spin = QSpinBox()
        upper_spin.setRange(0, 1000000)
        upper_spin.setValue(0)
        upper_spin.setSpecialValueText("Auto")
        upper_spin.setObjectName(f"{pulse_type}_upper_bound")
        layout.addWidget(upper_spin, row, 1)
        row += 1

        # Min separation
        layout.addWidget(QLabel("Min Separation:"), row, 0)
        min_sep_spin = QSpinBox()
        min_sep_spin.setRange(0, 100000)
        min_sep_spin.setValue(0)
        min_sep_spin.setSpecialValueText("Auto")
        min_sep_spin.setObjectName(f"{pulse_type}_min_separation")
        layout.addWidget(min_sep_spin, row, 1)
        row += 1

        layout.setRowStretch(row, 1)

        return tab

    def _get_param_widget(self, pulse_type: str, param_name: str):
        """Get a parameter widget by name.

        Args:
            pulse_type: Pulse type
            param_name: Parameter name

        Returns:
            Widget or None
        """
        tab_index = ['incident', 'transmitted', 'reflected'].index(pulse_type)
        tab = self.pulse_tabs.widget(tab_index)
        return tab.findChild(QWidget, f"{pulse_type}_{param_name}")

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

        return True

    def _restore_params(self) -> None:
        """Restore parameters from state."""
        for pulse_type in ['incident', 'transmitted', 'reflected']:
            params = self.state.detection_params.get(pulse_type, {})

            # Pulse points
            widget = self._get_param_widget(pulse_type, 'pulse_points')
            if widget and params.get('pulse_points'):
                widget.setValue(params['pulse_points'])

            # K trials
            widget = self._get_param_widget(pulse_type, 'k_trials')
            if widget and params.get('k_trials'):
                widget.setText(params['k_trials'])

            # Polarity
            widget = self._get_param_widget(pulse_type, 'polarity')
            if widget and params.get('polarity'):
                index = widget.findData(params['polarity'])
                if index >= 0:
                    widget.setCurrentIndex(index)

            # Detection metric
            widget = self._get_param_widget(pulse_type, 'metric')
            if widget and params.get('detection_metric'):
                index = widget.findData(params['detection_metric'])
                if index >= 0:
                    widget.setCurrentIndex(index)

            # Bounds
            widget = self._get_param_widget(pulse_type, 'lower_bound')
            if widget and params.get('lower_bound') is not None:
                widget.setValue(params['lower_bound'])

            widget = self._get_param_widget(pulse_type, 'upper_bound')
            if widget and params.get('upper_bound') is not None:
                widget.setValue(params['upper_bound'])

    def _save_params(self) -> None:
        """Save parameters to state."""
        for pulse_type in ['incident', 'transmitted', 'reflected']:
            params = {}

            # Pulse points
            widget = self._get_param_widget(pulse_type, 'pulse_points')
            if widget:
                params['pulse_points'] = widget.value()

            # K trials
            widget = self._get_param_widget(pulse_type, 'k_trials')
            if widget:
                params['k_trials'] = widget.text()

            # Polarity
            widget = self._get_param_widget(pulse_type, 'polarity')
            if widget:
                params['polarity'] = widget.currentData()

            # Detection metric
            widget = self._get_param_widget(pulse_type, 'metric')
            if widget:
                params['detection_metric'] = widget.currentData()

            # Bounds
            widget = self._get_param_widget(pulse_type, 'lower_bound')
            if widget:
                val = widget.value()
                params['lower_bound'] = val if val > 0 else None

            widget = self._get_param_widget(pulse_type, 'upper_bound')
            if widget:
                val = widget.value()
                params['upper_bound'] = val if val > 0 else None

            widget = self._get_param_widget(pulse_type, 'min_separation')
            if widget:
                val = widget.value()
                params['min_separation'] = val if val > 0 else None

            self.state.detection_params[pulse_type] = params

    def _get_current_params(self, pulse_type: str) -> Dict:
        """Get current parameters for a pulse type.

        Args:
            pulse_type: Pulse type

        Returns:
            Parameters dictionary
        """
        params = {}

        widget = self._get_param_widget(pulse_type, 'pulse_points')
        params['pulse_points'] = widget.value() if widget else 15000

        widget = self._get_param_widget(pulse_type, 'k_trials')
        k_str = widget.text() if widget else "6000,4000,2000"
        params['k_trials'] = tuple(float(k) for k in k_str.split(','))

        widget = self._get_param_widget(pulse_type, 'polarity')
        params['polarity'] = widget.currentData() if widget else 'compressive'

        widget = self._get_param_widget(pulse_type, 'metric')
        params['metric'] = widget.currentData() if widget else 'median'

        widget = self._get_param_widget(pulse_type, 'lower_bound')
        val = widget.value() if widget else 0
        params['lower_bound'] = val if val > 0 else None

        widget = self._get_param_widget(pulse_type, 'upper_bound')
        val = widget.value() if widget else 0
        params['upper_bound'] = val if val > 0 else None

        widget = self._get_param_widget(pulse_type, 'min_separation')
        val = widget.value() if widget else 0
        params['min_separation'] = val if val > 0 else None

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

            self.logger.info(f"Detected {pulse_type} window: {window}")

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
        """Update result label for a pulse type.

        Args:
            pulse_type: Pulse type
            window: Detected window or None
            error: Error message if detection failed
        """
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
                self.plot_widget.add_trace(time, incident, label="Incident Bar", color="blue")

            if transmitted is not None:
                self.plot_widget.add_trace(time, transmitted, label="Transmitted Bar", color="red")

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

            self.plot_widget.set_xlabel("Time")
            self.plot_widget.set_ylabel("Signal")
            self.plot_widget.refresh()

        except Exception as e:
            self.logger.error(f"Failed to update plot: {e}")
