"""Results Page - Calculate and display stress-strain results."""

import logging
from typing import Optional, Dict

import numpy as np

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QSplitter, QFrame,
    QTabWidget, QWidget
)
from PyQt6.QtCore import Qt
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

from .base_page import BaseSHPBPage
from .....mechanical.shpb.core.stress_strain import StressStrainCalculator
from .....mechanical.shpb.io.series_config import (
    get_series_metadata, get_windowed_series_metadata, SHPB_DERIVATION_MAP
)
from ...base.plotting import create_plot_widget
from ....builders.customizable_form_builder import CustomizableFormBuilder

logger = logging.getLogger(__name__)

DYN_NS = "https://dynamat.utep.edu/ontology#"

# Metric URI to metrics dict key mapping
METRIC_URI_MAP = {
    f"{DYN_NS}hasFBC": "FBC",
    f"{DYN_NS}hasSEQI": "SEQI",
    f"{DYN_NS}hasSOI": "SOI",
    f"{DYN_NS}hasDSUF": "DSUF",
    f"{DYN_NS}hasFBCLoading": "windowed_FBC_loading",
    f"{DYN_NS}hasDSUFLoading": "windowed_DSUF_loading",
    f"{DYN_NS}hasFBCPlateau": "windowed_FBC_plateau",
    f"{DYN_NS}hasDSUFPlateau": "windowed_DSUF_plateau",
    f"{DYN_NS}hasFBCUnloading": "windowed_FBC_unloading",
    f"{DYN_NS}hasDSUFUnloading": "windowed_DSUF_unloading",
}

# Color thresholds for overall metrics
METRIC_THRESHOLDS = {
    "FBC": lambda v: "green" if v > 0.95 else "orange" if v > 0.90 else "red",
    "SEQI": lambda v: "green" if v > 0.90 else "orange" if v > 0.80 else "red",
    "SOI": lambda v: "green" if v < 0.05 else "orange" if v < 0.10 else "red",
    "DSUF": lambda v: "green" if v > 0.98 else "orange" if v > 0.95 else "red",
}


class ResultsPage(BaseSHPBPage):
    """Results calculation page for SHPB analysis.

    Features:
    - Calculate 1-wave and 3-wave stress-strain curves
    - Display equilibrium metrics (ontology-driven)
    - Visualize stress-strain plots
    """

    def __init__(self, state, ontology_manager, qudt_manager=None, parent=None):
        super().__init__(state, ontology_manager, qudt_manager, parent)

        self.setTitle("Analysis Results")
        self.setSubTitle("Calculate stress-strain curves and equilibrium metrics.")

        self.calculator: Optional[StressStrainCalculator] = None

        # Ontology-driven form for metrics
        self.form_builder = CustomizableFormBuilder(ontology_manager)
        self._metrics_form: Optional[QWidget] = None

    def _setup_ui(self) -> None:
        """Setup page UI with ontology-driven metrics form."""
        layout = self._create_base_layout()

        # Create splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Metrics and controls
        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)

        # Calculate button
        calc_btn = QPushButton("Calculate Results")
        calc_btn.clicked.connect(self._calculate_results)
        left_layout.addWidget(calc_btn)

        # Ontology-driven equilibrium metrics form (read-only)
        METRICS_CLASS = f"{DYN_NS}EquilibriumMetrics"
        self._metrics_form = self.form_builder.build_form(
            METRICS_CLASS, parent=left_frame
        )
        left_layout.addWidget(self._metrics_form)

        # Calculated characteristics (hardcoded for now - future ontology-driven)
        chars_group = self._create_group_box("Calculated Characteristics")
        chars_layout = QGridLayout(chars_group)

        char_labels = [
            ("Peak Stress (1-wave):", "peak_stress_1w"),
            ("Peak Strain (1-wave):", "peak_strain_1w"),
            ("Max Strain Rate:", "max_strain_rate"),
            ("Flow Stress:", "flow_stress"),
        ]

        self.char_labels = {}
        for row, (label, key) in enumerate(char_labels):
            chars_layout.addWidget(QLabel(label), row, 0)
            value_label = QLabel("--")
            self.char_labels[key] = value_label
            chars_layout.addWidget(value_label, row, 1)

        left_layout.addWidget(chars_group)
        left_layout.addStretch()

        splitter.addWidget(left_frame)

        # Right: Plots
        right_frame = QFrame()
        right_layout = QVBoxLayout(right_frame)

        self.plot_tabs = QTabWidget()

        # Stress-strain plot
        try:
            self.stress_strain_plot = create_plot_widget(
                self.ontology_manager,
                self.qudt_manager,
                show_toolbar=True
            )
            self.plot_tabs.addTab(self.stress_strain_plot, "Stress-Strain")
        except Exception as e:
            logger.warning(f"Could not create stress-strain plot: {e}")
            self.stress_strain_plot = None
            self.plot_tabs.addTab(QLabel("Plot unavailable"), "Stress-Strain")

        # Strain rate plot
        try:
            self.strain_rate_plot = create_plot_widget(
                self.ontology_manager,
                self.qudt_manager,
                show_toolbar=True
            )
            self.plot_tabs.addTab(self.strain_rate_plot, "Strain Rate")
        except Exception as e:
            logger.warning(f"Could not create strain rate plot: {e}")
            self.strain_rate_plot = None
            self.plot_tabs.addTab(QLabel("Plot unavailable"), "Strain Rate")

        # Stress vs time plot
        try:
            self.stress_time_plot = create_plot_widget(
                self.ontology_manager,
                self.qudt_manager,
                show_toolbar=True
            )
            self.plot_tabs.addTab(self.stress_time_plot, "Stress vs Time")
        except Exception as e:
            logger.warning(f"Could not create stress vs time plot: {e}")
            self.stress_time_plot = None
            self.plot_tabs.addTab(QLabel("Plot unavailable"), "Stress vs Time")

        # Strain vs time plot
        try:
            self.strain_time_plot = create_plot_widget(
                self.ontology_manager,
                self.qudt_manager,
                show_toolbar=True
            )
            self.plot_tabs.addTab(self.strain_time_plot, "Strain vs Time")
        except Exception as e:
            logger.warning(f"Could not create strain vs time plot: {e}")
            self.strain_time_plot = None
            self.plot_tabs.addTab(QLabel("Plot unavailable"), "Strain vs Time")

        # Bar displacement plot
        try:
            self.displacement_plot = create_plot_widget(
                self.ontology_manager,
                self.qudt_manager,
                show_toolbar=True
            )
            self.plot_tabs.addTab(self.displacement_plot, "Bar Displacement")
        except Exception as e:
            logger.warning(f"Could not create displacement plot: {e}")
            self.displacement_plot = None
            self.plot_tabs.addTab(QLabel("Plot unavailable"), "Bar Displacement")

        # Bar force plot
        try:
            self.force_plot = create_plot_widget(
                self.ontology_manager,
                self.qudt_manager,
                show_toolbar=True
            )
            self.plot_tabs.addTab(self.force_plot, "Bar Force")
        except Exception as e:
            logger.warning(f"Could not create force plot: {e}")
            self.force_plot = None
            self.plot_tabs.addTab(QLabel("Plot unavailable"), "Bar Force")

        right_layout.addWidget(self.plot_tabs)
        splitter.addWidget(right_frame)
        splitter.setSizes([350, 650])

        layout.addWidget(splitter)
        self._add_status_area()

    def initializePage(self) -> None:
        """Initialize page when it becomes current."""
        super().initializePage()

        # If results already calculated, show them
        if self.state.has_results():
            self._update_metrics_display()
            self._update_plots()

    def validatePage(self) -> bool:
        """Validate before allowing Next."""
        if not self.state.has_results():
            self.show_warning(
                "Calculation Required",
                "Please calculate results before continuing."
            )
            return False

        # Run SHACL validation on equilibrium metrics graph
        validation_graph = self._build_validation_graph()
        if validation_graph and not self._validate_page_data(
            validation_graph, page_key="results"
        ):
            return False

        return True

    def _build_validation_graph(self) -> Optional[Graph]:
        """Build partial RDF graph for SHACL validation.

        Merges EquilibriumMetrics instance with windowed + processed DataSeries
        and the processed AnalysisFile.

        Returns:
            RDF graph with all results instances, or None if no data.
        """
        if not self.state.equilibrium_form_data:
            return None

        try:
            # Build equilibrium metrics graph
            eq_graph = self._build_graph_from_form_data(
                self.state.equilibrium_form_data,
                f"{DYN_NS}EquilibriumMetrics",
                "_val_equilibrium",
            )

            # Build series graph (windowed + processed + analysis file)
            series_graph = self._build_series_graph()

            if series_graph and eq_graph:
                for triple in series_graph:
                    eq_graph.add(triple)

            return eq_graph
        except Exception as e:
            self.logger.error(f"Failed to build validation graph: {e}")
            return None

    def _build_series_graph(self) -> Optional[Graph]:
        """Build RDF graph for windowed + processed DataSeries and AnalysisFile.

        Creates:
        - 1 processed AnalysisFile instance
        - 4 windowed DataSeries (time, incident, transmitted, reflected)
        - 16 processed DataSeries (8 x 1-wave + 8 x 3-wave)

        All metadata is ontology-driven via get_series_metadata() and
        get_windowed_series_metadata().

        Returns:
            RDF graph with all series instances, or None on error.
        """
        if not self.state.calculation_results:
            return None

        try:
            DYN = Namespace(DYN_NS)
            writer = self._instance_writer
            g = Graph()
            writer._setup_namespaces(g)

            test_id = (
                f"{self.state.specimen_id}_SHPBTest"
                if self.state.specimen_id
                else "_val"
            )

            results = self.state.calculation_results

            # Determine data point count from results
            first_key = next(iter(results))
            n_points = len(results[first_key])

            # ---- Processed AnalysisFile ----
            processed_file_form = {
                f"{DYN_NS}hasFilePath": "processed_results.csv",
                f"{DYN_NS}hasFileFormat": "csv",
                f"{DYN_NS}hasDataPointCount": n_points,
                f"{DYN_NS}hasColumnCount": len(results),
            }
            processed_file_ref = writer.create_single_instance(
                g, processed_file_form, f"{DYN_NS}AnalysisFile",
                f"{test_id}_processed_csv"
            )
            self.state.processed_file_uri = str(processed_file_ref)

            # ---- Windowed DataSeries (4 instances) ----
            windowed_meta = get_windowed_series_metadata()

            # Gauge URI mapping for windowed series
            inc_gauge = self.state.gauge_mapping.get('incident')
            tra_gauge = self.state.gauge_mapping.get('transmitted')
            gauge_for_windowed = {
                'incident_windowed': inc_gauge,
                'transmitted_windowed': tra_gauge,
                'reflected_windowed': inc_gauge,  # Reflected is on incident bar
            }

            proc_col_idx = 0  # Column index counter for processed CSV

            for series_name, meta in windowed_meta.items():
                raw_source = meta.get('raw_source')
                raw_uri = self.state.raw_series_uris.get(raw_source) if raw_source else None

                form_data: Dict = {
                    f"{DYN_NS}hasSeriesType": meta['series_type'],
                    f"{DYN_NS}hasColumnName": series_name,
                    f"{DYN_NS}hasLegendName": meta['legend_name'],
                    f"{DYN_NS}hasDataFile": str(processed_file_ref),
                    f"{DYN_NS}hasDataPointCount": n_points,
                    f"{DYN_NS}hasProcessingMethod": "Pulse windowing and segmentation",
                    f"{DYN_NS}hasFilterApplied": False,
                }
                if meta.get('unit'):
                    form_data[f"{DYN_NS}hasSeriesUnit"] = meta['unit']
                if meta.get('quantity_kind'):
                    form_data[f"{DYN_NS}hasQuantityKind"] = meta['quantity_kind']
                if raw_uri:
                    form_data[f"{DYN_NS}derivedFrom"] = raw_uri

                # Strain gauge link
                gauge_uri = gauge_for_windowed.get(series_name)
                if gauge_uri and meta.get('requires_gauge'):
                    form_data[f"{DYN_NS}measuredBy"] = gauge_uri

                form_data[f"{DYN_NS}hasColumnIndex"] = proc_col_idx
                proc_col_idx += 1

                ref = writer.create_single_instance(
                    g, form_data, f"{DYN_NS}ProcessedData",
                    f"{test_id}_{series_name}"
                )
                g.add((ref, RDF.type, DYN.DataSeries))

                # Declare SeriesType individual
                st_ref = URIRef(meta['series_type'])
                g.add((st_ref, RDF.type, DYN.SeriesType))

                self.state.windowed_series_uris[series_name] = str(ref)

            # ---- Processed DataSeries (16 instances) ----
            series_meta = get_series_metadata()

            for col_name, data_array in results.items():
                # Skip raw columns - already handled
                if col_name in ('time', 'incident', 'transmitted', 'reflected'):
                    continue

                meta = series_meta.get(col_name)
                if not meta:
                    continue

                # Determine analysis method and base series name
                if col_name.endswith('_1w'):
                    method = '1-wave'
                    base_name = col_name[:-3]
                elif col_name.endswith('_3w'):
                    method = '3-wave'
                    base_name = col_name[:-3]
                else:
                    method = meta.get('analysis_method')
                    base_name = col_name

                # Build derivedFrom from SHPB_DERIVATION_MAP
                derived_uris = []
                if method:
                    sources = SHPB_DERIVATION_MAP.get(method, {}).get(base_name, [])
                    for source in sources:
                        w_key = f"{source}_windowed"
                        if w_key in self.state.windowed_series_uris:
                            derived_uris.append(self.state.windowed_series_uris[w_key])

                form_data: Dict = {
                    f"{DYN_NS}hasSeriesType": meta['series_type'],
                    f"{DYN_NS}hasLegendName": meta['legend_name'],
                    f"{DYN_NS}hasColumnName": col_name,
                    f"{DYN_NS}hasDataFile": str(processed_file_ref),
                    f"{DYN_NS}hasDataPointCount": len(data_array),
                    f"{DYN_NS}hasProcessingMethod": "SHPB stress-strain calculation",
                    f"{DYN_NS}hasFilterApplied": False,
                }
                if meta.get('unit'):
                    form_data[f"{DYN_NS}hasSeriesUnit"] = meta['unit']
                if meta.get('quantity_kind'):
                    form_data[f"{DYN_NS}hasQuantityKind"] = meta['quantity_kind']
                if method:
                    form_data[f"{DYN_NS}hasAnalysisMethod"] = method

                # derivedFrom: single or multiple
                if len(derived_uris) == 1:
                    form_data[f"{DYN_NS}derivedFrom"] = derived_uris[0]
                elif len(derived_uris) > 1:
                    form_data[f"{DYN_NS}derivedFrom"] = derived_uris

                form_data[f"{DYN_NS}hasColumnIndex"] = proc_col_idx
                proc_col_idx += 1

                ref = writer.create_single_instance(
                    g, form_data, f"{DYN_NS}ProcessedData",
                    f"{test_id}_{col_name}"
                )
                g.add((ref, RDF.type, DYN.DataSeries))

                # Declare SeriesType individual
                st_ref = URIRef(meta['series_type'])
                g.add((st_ref, RDF.type, DYN.SeriesType))

                self.state.processed_series_uris[col_name] = str(ref)

            self.logger.info(
                f"Built series graph: {len(self.state.windowed_series_uris)} windowed, "
                f"{len(self.state.processed_series_uris)} processed"
            )
            return g

        except Exception as e:
            self.logger.error(f"Failed to build series graph: {e}", exc_info=True)
            return None

    def _calculate_results(self) -> None:
        """Calculate stress-strain results."""
        self.show_progress()
        self.set_status("Calculating stress-strain curves...")

        try:
            # Get equipment properties
            equipment = self.state.equipment_properties
            if not equipment:
                raise ValueError("Equipment properties not available")

            # Get bar properties
            bar_area = equipment.get('incident_bar', {}).get('cross_section')
            bar_wave_speed = equipment.get('incident_bar', {}).get('wave_speed')
            bar_modulus = equipment.get('incident_bar', {}).get('elastic_modulus')

            if not all([bar_area, bar_wave_speed, bar_modulus]):
                raise ValueError("Missing bar properties")

            # Get specimen properties
            specimen_data = self.state.specimen_data or {}

            specimen_area = specimen_data.get(
                f'{DYN_NS}hasOriginalCrossSection'
            )
            specimen_height = specimen_data.get(
                f'{DYN_NS}hasOriginalHeight'
            )

            # Handle measurement dictionaries
            if isinstance(specimen_area, dict):
                specimen_area = specimen_area.get('value')
            if isinstance(specimen_height, dict):
                specimen_height = specimen_height.get('value')

            if not specimen_area or not specimen_height:
                raise ValueError("Missing specimen dimensions")

            # Get aligned pulses
            incident = self.state.aligned_pulses.get('incident')
            transmitted = self.state.aligned_pulses.get('transmitted')
            reflected = self.state.aligned_pulses.get('reflected')
            time_vector = self.state.time_vector

            if incident is None or transmitted is None or reflected is None:
                raise ValueError("Aligned pulses not available")

            # Create calculator
            self.calculator = StressStrainCalculator(
                bar_area=float(bar_area),
                bar_wave_speed=float(bar_wave_speed),
                bar_elastic_modulus=float(bar_modulus),
                specimen_area=float(specimen_area),
                specimen_height=float(specimen_height),
                strain_scale_factor=1e4,  # Assuming voltage input
                use_voltage_input=False
            )

            # Calculate results
            results = self.calculator.calculate(
                incident,
                transmitted,
                reflected,
                time_vector
            )

            # Store results (flat dict for backward compat)
            self.state.calculation_results = results

            # Calculate equilibrium metrics and store as form data
            metrics = self.calculator.calculate_equilibrium_metrics(results)
            self.state.equilibrium_form_data = {}
            for uri, metric_key in METRIC_URI_MAP.items():
                value = metrics.get(metric_key)
                if value is not None:
                    self.state.equilibrium_form_data[uri] = value

            # Update display
            self._update_metrics_display()
            self._update_plots()

            self.set_status("Calculation completed successfully")
            self.logger.info("Stress-strain calculation completed")

        except Exception as e:
            self.logger.error(f"Calculation failed: {e}")
            self.set_status(f"Error: {e}", is_error=True)
            self.show_error("Calculation Failed", str(e))

        finally:
            self.hide_progress()

    def _update_metrics_display(self) -> None:
        """Update metrics display using ontology form and color coding."""
        if not self.state.equilibrium_form_data:
            return

        # Populate the ontology form with metric values from form data
        self.form_builder.set_form_data(self._metrics_form, self.state.equilibrium_form_data)

        # Build reverse lookup for color coding
        metrics = {}
        for uri, metric_key in METRIC_URI_MAP.items():
            value = self.state.equilibrium_form_data.get(uri)
            if value is not None:
                metrics[metric_key] = value

        # Apply color coding to overall metrics
        self._apply_metric_colors(metrics)

        # Update calculated characteristics
        self._update_characteristics()

    def _apply_metric_colors(self, metrics: Dict[str, float]) -> None:
        """Apply color stylesheets to FBC/SEQI/SOI/DSUF fields based on thresholds."""
        for metric_key, threshold_fn in METRIC_THRESHOLDS.items():
            value = metrics.get(metric_key)
            if value is None:
                continue

            # Find the URI for this metric
            uri = f"{DYN_NS}has{metric_key}"
            form_fields = self._metrics_form.form_fields
            if uri in form_fields:
                color = threshold_fn(value)
                form_fields[uri].widget.setStyleSheet(
                    f"color: {color}; font-weight: bold;"
                )

    def _update_characteristics(self) -> None:
        """Update calculated characteristics labels."""
        results = self.state.calculation_results
        if not results:
            return

        stress_1w = results.get('stress_1w', [])
        strain_1w = results.get('strain_1w', [])
        strain_rate_1w = results.get('strain_rate_1w', [])

        if len(stress_1w) > 0:
            self.char_labels['peak_stress_1w'].setText(f"{np.max(np.abs(stress_1w)):.1f} MPa")

        if len(strain_1w) > 0:
            self.char_labels['peak_strain_1w'].setText(f"{np.max(np.abs(strain_1w)):.4f}")

        if len(strain_rate_1w) > 0:
            self.char_labels['max_strain_rate'].setText(f"{np.max(np.abs(strain_rate_1w)):.0f} /s")

        # Flow stress (simplified: use plateau region)
        if len(stress_1w) > 10:
            mid_start = len(stress_1w) // 4
            mid_end = 3 * len(stress_1w) // 4
            flow = np.mean(np.abs(stress_1w[mid_start:mid_end]))
            self.char_labels['flow_stress'].setText(f"{flow:.1f} MPa")

    def _update_plots(self) -> None:
        """Update plots with results."""
        results = self.state.calculation_results
        if not results:
            return

        self._update_stress_strain_plot(results)
        self._update_strain_rate_plot(results)
        self._update_stress_time_plot(results)
        self._update_strain_time_plot(results)
        self._update_displacement_plot(results)
        self._update_force_plot(results)

    def _update_stress_strain_plot(self, results: Dict) -> None:
        """Update stress-strain plot with engineering and true curves."""
        if not self.stress_strain_plot:
            return

        try:
            self.stress_strain_plot.clear()

            # Engineering 1-wave (solid blue)
            strain_1w = results.get('strain_1w', [])
            stress_1w = results.get('stress_1w', [])
            if len(strain_1w) > 0 and len(stress_1w) > 0:
                self.stress_strain_plot.add_ontology_trace(
                    strain_1w, stress_1w,
                    x_series_type_uri='dyn:Strain',
                    y_series_type_uri='dyn:Stress',
                    label="1-wave", color="blue", linewidth=2
                )

            # Engineering 3-wave (dashed blue)
            strain_3w = results.get('strain_3w', [])
            stress_3w = results.get('stress_3w', [])
            if len(strain_3w) > 0 and len(stress_3w) > 0:
                self.stress_strain_plot.add_trace(
                    strain_3w, stress_3w,
                    label="3-wave", color="blue",
                    linestyle='--', linewidth=2, alpha=0.7
                )

            # True 1-wave (solid red)
            true_strain_1w = results.get('true_strain_1w', [])
            true_stress_1w = results.get('true_stress_1w', [])
            if len(true_strain_1w) > 0 and len(true_stress_1w) > 0:
                self.stress_strain_plot.add_trace(
                    true_strain_1w, true_stress_1w,
                    label="True (1-wave)", color="red", linewidth=2
                )

            # True 3-wave (dashed red)
            true_strain_3w = results.get('true_strain_3w', [])
            true_stress_3w = results.get('true_stress_3w', [])
            if len(true_strain_3w) > 0 and len(true_stress_3w) > 0:
                self.stress_strain_plot.add_trace(
                    true_strain_3w, true_stress_3w,
                    label="True (3-wave)", color="red",
                    linestyle='--', linewidth=2, alpha=0.7
                )

            self.stress_strain_plot.enable_grid()
            self.stress_strain_plot.enable_legend()
            self.stress_strain_plot.refresh()

        except Exception as e:
            self.logger.error(f"Failed to update stress-strain plot: {e}")

    def _update_strain_rate_plot(self, results: Dict) -> None:
        """Update strain rate vs time plot."""
        if not self.strain_rate_plot:
            return

        try:
            self.strain_rate_plot.clear()

            time = results.get('time', [])
            if len(time) == 0:
                return

            # Engineering 1-wave (solid blue)
            sr_1w = results.get('strain_rate_1w', [])
            if len(sr_1w) > 0:
                self.strain_rate_plot.add_ontology_trace(
                    time[:len(sr_1w)], sr_1w,
                    x_series_type_uri='dyn:Time',
                    y_series_type_uri='dyn:StrainRate',
                    label="1-wave", color="blue", linewidth=1.5
                )

            # Engineering 3-wave (dashed blue)
            sr_3w = results.get('strain_rate_3w', [])
            if len(sr_3w) > 0:
                self.strain_rate_plot.add_trace(
                    time[:len(sr_3w)], sr_3w,
                    label="3-wave", color="blue",
                    linestyle='--', linewidth=2, alpha=0.7
                )

            # True 1-wave (solid red)
            true_sr_1w = results.get('true_strain_rate_1w', [])
            if len(true_sr_1w) > 0:
                self.strain_rate_plot.add_trace(
                    time[:len(true_sr_1w)], true_sr_1w,
                    label="True 1-wave", color="red", linewidth=1.5
                )

            # True 3-wave (dashed red)
            true_sr_3w = results.get('true_strain_rate_3w', [])
            if len(true_sr_3w) > 0:
                self.strain_rate_plot.add_trace(
                    time[:len(true_sr_3w)], true_sr_3w,
                    label="True 3-wave", color="red",
                    linestyle='--', linewidth=2, alpha=0.7
                )

            self.strain_rate_plot.enable_grid()
            self.strain_rate_plot.enable_legend()
            self.strain_rate_plot.refresh()

        except Exception as e:
            self.logger.error(f"Failed to update strain rate plot: {e}")

    def _update_stress_time_plot(self, results: Dict) -> None:
        """Update stress vs time plot."""
        if not self.stress_time_plot:
            return

        try:
            self.stress_time_plot.clear()

            time = results.get('time', [])
            if len(time) == 0:
                return

            # Engineering 1-wave (solid blue)
            stress_1w = results.get('stress_1w', [])
            if len(stress_1w) > 0:
                self.stress_time_plot.add_ontology_trace(
                    time[:len(stress_1w)], stress_1w,
                    x_series_type_uri='dyn:Time',
                    y_series_type_uri='dyn:Stress',
                    label="1-wave", color="blue", linewidth=1.5
                )

            # Engineering 3-wave (dashed blue)
            stress_3w = results.get('stress_3w', [])
            if len(stress_3w) > 0:
                self.stress_time_plot.add_trace(
                    time[:len(stress_3w)], stress_3w,
                    label="3-wave", color="blue",
                    linestyle='--', linewidth=1.5, alpha=0.7
                )

            # True 1-wave (solid red)
            true_stress_1w = results.get('true_stress_1w', [])
            if len(true_stress_1w) > 0:
                self.stress_time_plot.add_trace(
                    time[:len(true_stress_1w)], true_stress_1w,
                    label="True 1-wave", color="red", linewidth=1.5
                )

            # True 3-wave (dashed red)
            true_stress_3w = results.get('true_stress_3w', [])
            if len(true_stress_3w) > 0:
                self.stress_time_plot.add_trace(
                    time[:len(true_stress_3w)], true_stress_3w,
                    label="True 3-wave", color="red",
                    linestyle='--', linewidth=1.5, alpha=0.7
                )

            self.stress_time_plot.enable_grid()
            self.stress_time_plot.enable_legend()
            self.stress_time_plot.refresh()

        except Exception as e:
            self.logger.error(f"Failed to update stress vs time plot: {e}")

    def _update_strain_time_plot(self, results: Dict) -> None:
        """Update strain vs time plot with engineering and true curves."""
        if not self.strain_time_plot:
            return

        try:
            self.strain_time_plot.clear()

            time = results.get('time', [])
            if len(time) == 0:
                return

            # Engineering 1-wave (solid blue)
            strain_1w = results.get('strain_1w', [])
            if len(strain_1w) > 0:
                self.strain_time_plot.add_ontology_trace(
                    time[:len(strain_1w)], strain_1w,
                    x_series_type_uri='dyn:Time',
                    y_series_type_uri='dyn:Strain',
                    label="1-wave", color="blue", linewidth=1.5
                )

            # Engineering 3-wave (dashed blue)
            strain_3w = results.get('strain_3w', [])
            if len(strain_3w) > 0:
                self.strain_time_plot.add_trace(
                    time[:len(strain_3w)], strain_3w,
                    label="3-wave", color="blue",
                    linestyle='--', linewidth=1.5, alpha=0.7
                )

            # True 1-wave (solid red)
            true_strain_1w = results.get('true_strain_1w', [])
            if len(true_strain_1w) > 0:
                self.strain_time_plot.add_trace(
                    time[:len(true_strain_1w)], true_strain_1w,
                    label="True 1-wave", color="red", linewidth=1.5
                )

            # True 3-wave (dashed red)
            true_strain_3w = results.get('true_strain_3w', [])
            if len(true_strain_3w) > 0:
                self.strain_time_plot.add_trace(
                    time[:len(true_strain_3w)], true_strain_3w,
                    label="True 3-wave", color="red",
                    linestyle='--', linewidth=1.5, alpha=0.7
                )

            self.strain_time_plot.enable_grid()
            self.strain_time_plot.enable_legend()
            self.strain_time_plot.refresh()

        except Exception as e:
            self.logger.error(f"Failed to update strain vs time plot: {e}")

    def _update_displacement_plot(self, results: Dict) -> None:
        """Update bar displacement vs time plot."""
        if not self.displacement_plot:
            return

        try:
            self.displacement_plot.clear()

            time = results.get('time', [])
            if len(time) == 0:
                return

            # 1-wave (solid blue)
            disp_1w = results.get('bar_displacement_1w', [])
            if len(disp_1w) > 0:
                self.displacement_plot.add_ontology_trace(
                    time[:len(disp_1w)], disp_1w,
                    x_series_type_uri='dyn:Time',
                    y_series_type_uri='dyn:BarDisplacement',
                    label="1-wave", color="blue", linewidth=1.5
                )

            # 3-wave (dashed blue)
            disp_3w = results.get('bar_displacement_3w', [])
            if len(disp_3w) > 0:
                self.displacement_plot.add_trace(
                    time[:len(disp_3w)], disp_3w,
                    label="3-wave", color="blue",
                    linestyle='--', linewidth=1.5, alpha=0.7
                )

            self.displacement_plot.enable_grid()
            self.displacement_plot.enable_legend()
            self.displacement_plot.refresh()

        except Exception as e:
            self.logger.error(f"Failed to update displacement plot: {e}")

    def _update_force_plot(self, results: Dict) -> None:
        """Update bar force vs time plot."""
        if not self.force_plot:
            return

        try:
            self.force_plot.clear()

            time = results.get('time', [])
            if len(time) == 0:
                return

            # 1-wave (solid blue)
            force_1w = results.get('bar_force_1w', [])
            if len(force_1w) > 0:
                self.force_plot.add_ontology_trace(
                    time[:len(force_1w)], force_1w,
                    x_series_type_uri='dyn:Time',
                    y_series_type_uri='dyn:BarForce',
                    label="1-wave", color="blue", linewidth=1.5
                )

            # 3-wave (dashed blue)
            force_3w = results.get('bar_force_3w', [])
            if len(force_3w) > 0:
                self.force_plot.add_trace(
                    time[:len(force_3w)], force_3w,
                    label="3-wave", color="blue",
                    linestyle='--', linewidth=1.5, alpha=0.7
                )

            self.force_plot.enable_grid()
            self.force_plot.enable_legend()
            self.force_plot.refresh()

        except Exception as e:
            self.logger.error(f"Failed to update force plot: {e}")
