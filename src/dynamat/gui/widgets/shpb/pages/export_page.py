"""Export Page - Save SHPB test results to RDF.

Merges all cumulative page_graphs, renames validation-time instance IDs
to production IDs, runs final SHACL validation, and serializes to TTL.

Identification section is ontology-driven (read-only mirror of equipment page).
Fitness assessment section shows DQV fitness annotations from the Science
Trust Card; the override checkbox allows manual annotation changes.
"""

import logging
import os
from pathlib import Path
from typing import Optional
from datetime import datetime, date

from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel,
    QGroupBox, QGridLayout, QLineEdit,
    QCheckBox, QScrollArea, QWidget, QFrame,
    QMessageBox,
)
from PyQt6.QtCore import Qt
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

from .base_page import BaseSHPBPage
from .....mechanical.shpb.io.csv_data_handler import CSVDataHandler
from .....config import config
from ....builders.customizable_form_builder import CustomizableFormBuilder

logger = logging.getLogger(__name__)

DYN_NS = "https://dynamat.utep.edu/ontology#"
SHPB_COMPRESSION_URI = f"{DYN_NS}SHPBCompression"


class ExportPage(BaseSHPBPage):
    """Export page for SHPB analysis.

    Layout (top → bottom inside scroll):
      1. Test Identification   – ontology-driven, read-only
      2. Fitness Assessment    – DQV fitness/diagnostic annotations from
                                Science Trust Card; override checkbox for
                                manual annotation changes
      3. Test Summary          – computed metrics display
      4. Output                – destination file path
    """

    def __init__(self, state, ontology_manager, qudt_manager=None, parent=None):
        super().__init__(state, ontology_manager, qudt_manager, parent)

        self.setTitle("Export Test")
        self.setSubTitle("Review and save the SHPB test results.")

        self.id_form_widget: Optional[QWidget] = None
        self._form_builder: Optional[CustomizableFormBuilder] = None

    def _setup_ui(self) -> None:
        """Setup page UI using ontology-driven form builder."""
        layout = self._create_base_layout()

        self._form_builder = CustomizableFormBuilder(self.ontology_manager)

        # ── Outer scroll area ────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(8)

        # ── 1. Test Identification (ontology-driven, read-only) ───────────────
        id_section = self._create_group_box("Test Identification")
        id_section_layout = QVBoxLayout(id_section)
        id_section_layout.setContentsMargins(4, 4, 4, 4)

        try:
            self.id_form_widget = self._form_builder.build_form(
                SHPB_COMPRESSION_URI,
                parent=id_section,
                include_groups={"Identification"},
                use_scroll_area=False,
            )
            id_section_layout.addWidget(self.id_form_widget)
        except Exception as e:
            self.logger.error(f"Failed to build identification form: {e}", exc_info=True)
            id_section_layout.addWidget(QLabel(f"Error: {e}"))

        content_layout.addWidget(id_section)

        # ── 2. Fitness Assessment (DQV annotations) ─────────────────────────
        fitness_section = self._create_group_box("Fitness Assessment")
        fitness_layout = QVBoxLayout(fitness_section)
        fitness_layout.setContentsMargins(4, 4, 4, 4)
        fitness_layout.setSpacing(6)

        # Stages completed
        self._stages_label = QLabel("--")
        self._stages_label.setStyleSheet("color: gray;")
        fitness_layout.addWidget(self._stages_label)

        # Critical failure banner (hidden by default)
        self._critical_banner = QLabel("CRITICAL FAILURE — Signal integrity compromised")
        self._critical_banner.setStyleSheet(
            "background-color: #c62828; color: white; padding: 6px; "
            "font-weight: bold; border-radius: 4px;"
        )
        self._critical_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._critical_banner.setVisible(False)
        fitness_layout.addWidget(self._critical_banner)

        # Fitness annotations display
        fitness_layout.addWidget(QLabel("Fitness for Purpose:"))
        self._fitness_label = QLabel("--")
        self._fitness_label.setTextFormat(Qt.TextFormat.RichText)
        self._fitness_label.setWordWrap(True)
        fitness_layout.addWidget(self._fitness_label)

        # Diagnostic annotations display
        fitness_layout.addWidget(QLabel("Diagnostics:"))
        self._diagnostics_label = QLabel("--")
        self._diagnostics_label.setTextFormat(Qt.TextFormat.RichText)
        self._diagnostics_label.setWordWrap(True)
        fitness_layout.addWidget(self._diagnostics_label)

        # Override checkbox (always visible)
        self.override_check = QCheckBox("Override Fitness Assessment")
        self.override_check.stateChanged.connect(self._on_override_changed)
        fitness_layout.addWidget(self.override_check)

        # Override notes — plain text field, hidden by default
        self._override_notes_label = QLabel("Override Reason:")
        self._override_notes_label.setVisible(False)
        fitness_layout.addWidget(self._override_notes_label)

        self._override_notes = QLineEdit()
        self._override_notes.setPlaceholderText(
            "Describe why the auto-assessment is being overridden..."
        )
        self._override_notes.setVisible(False)
        fitness_layout.addWidget(self._override_notes)

        content_layout.addWidget(fitness_section)

        # ── 3. Test Summary ──────────────────────────────────────────────────
        summary_group = self._create_group_box("Test Summary")
        summary_layout = QGridLayout(summary_group)

        summary_items = [
            ("Specimen:", "specimen"),
            ("Test Date:", "date"),
            ("Equipment:", "equipment"),
            ("Peak Stress:", "stress"),
            ("Peak Strain:", "strain"),
            ("FBC (Plateau):", "fbc"),
        ]

        self.summary_labels = {}
        for row, (label, key) in enumerate(summary_items):
            summary_layout.addWidget(QLabel(label), row, 0)
            value_label = QLabel("--")
            self.summary_labels[key] = value_label
            summary_layout.addWidget(value_label, row, 1)

        content_layout.addWidget(summary_group)

        # ── 4. Output ────────────────────────────────────────────────────────
        output_group = self._create_group_box("Output")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("Output File:"), 0, 0)
        self.output_label = QLabel("--")
        self.output_label.setWordWrap(True)
        self.output_label.setStyleSheet("color: gray;")
        output_layout.addWidget(self.output_label, 0, 1)

        content_layout.addWidget(output_group)
        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

        self._add_status_area()

    # ── Initialization ────────────────────────────────────────────────────────

    def initializePage(self) -> None:
        """Initialize page when it becomes current."""
        super().initializePage()

        # Populate identification form from equipment state (read-only)
        if self.id_form_widget and self.state.equipment_form_data:
            self._form_builder.set_form_data(self.id_form_widget, self.state.equipment_form_data)
        self._make_id_form_readonly()

        # Display fitness/diagnostic annotations from Science Trust Card
        self._display_fitness_assessment()

        # Always start with override unchecked and notes hidden
        self.override_check.blockSignals(True)
        self.override_check.setChecked(False)
        self.override_check.blockSignals(False)
        self._override_notes_label.setVisible(False)
        self._override_notes.setVisible(False)
        self._override_notes.clear()

        # Restore from previous export
        if getattr(self.state, '_loaded_from_previous', False) and self.state.export_form_data:
            override_reason = self.state.export_form_data.get(
                f"{DYN_NS}hasOverrideReason", ""
            )
            was_overridden = self.state.export_form_data.get(
                f"{DYN_NS}isAssessmentOverridden", False
            )
            if was_overridden:
                self.override_check.blockSignals(True)
                self.override_check.setChecked(True)
                self.override_check.blockSignals(False)
                self._override_notes_label.setVisible(True)
                self._override_notes.setVisible(True)
                if override_reason:
                    self._override_notes.setText(str(override_reason))

        # Update summary and output path
        self._update_summary()
        self._update_output_path()

    # ── Validation / Export ───────────────────────────────────────────────────

    def validatePage(self) -> bool:
        """Validate and export test."""
        export_data = {}
        is_overriding = self.override_check.isChecked()
        export_data[f"{DYN_NS}isAssessmentOverridden"] = is_overriding
        if is_overriding:
            export_data[f"{DYN_NS}hasOverrideReason"] = self._override_notes.text().strip()

        self.state.export_form_data = export_data

        # Build export validation graph and store it
        validation_graph = self._build_validation_graph()
        if validation_graph:
            self.state.page_graphs["export"] = validation_graph

        return self._export_test()

    # ── Validation graph ──────────────────────────────────────────────────────

    def _build_validation_graph(self) -> Optional[Graph]:
        """Build graph with export metadata, ScienceTrustCard, and sub-instance links."""
        try:
            DYN = Namespace(DYN_NS)
            writer = self._instance_writer
            graph = Graph()
            writer._setup_namespaces(graph)

            test_node = URIRef(writer._create_instance_uri("_val_equipment"))

            # Add export metadata
            if self.state.export_form_data:
                for uri, value in self.state.export_form_data.items():
                    if value is None or value == "":
                        continue
                    prop_ref = writer._resolve_uri(uri)
                    if isinstance(value, list):
                        for item in value:
                            if item is not None and item != "":
                                rdf_value = writer._convert_to_rdf_value(item)
                                graph.add((test_node, prop_ref, rdf_value))
                    else:
                        rdf_value = writer._convert_to_rdf_value(value)
                        graph.add((test_node, prop_ref, rdf_value))

            # Add timestamp
            graph.add((test_node, DYN.hasAnalysisTimestamp,
                        writer._convert_to_rdf_value(datetime.now().isoformat())))

            # Build ScienceTrustCard sub-instance from metrics form data
            if self.state.metrics_form_data:
                card_ref = writer.create_single_instance(
                    graph, self.state.metrics_form_data,
                    f"{DYN_NS}ScienceTrustCard", "_val_trust_card"
                )
                graph.add((test_node, DYN.hasScienceTrustCard, card_ref))

            # Link to sub-instances
            sub_links = {
                "hasAlignmentParams": "_val_alignment",
                "hasSegmentationParams": "_val_segmentation",
            }
            for prop_name, inst_id in sub_links.items():
                page_key = {
                    "_val_alignment": "alignment",
                    "_val_segmentation": "segmentation",
                }.get(inst_id)
                if page_key and page_key in self.state.page_graphs:
                    target = URIRef(writer._create_instance_uri(inst_id))
                    graph.add((test_node, DYN[prop_name], target))

            # Tukey alpha stored directly on test node
            tukey = self.state.tukey_form_data or {}
            if tukey.get(f"{DYN_NS}isTukeyEnabled"):
                alpha = tukey.get(f"{DYN_NS}hasTukeyAlphaParam")
                if alpha is not None:
                    graph.add((test_node, DYN.hasTukeyAlphaParam,
                               writer._convert_to_rdf_value(alpha)))

            # Link detection params (3×)
            if "pulse_detection" in self.state.page_graphs:
                for pulse_type in ["incident", "transmitted", "reflected"]:
                    target = URIRef(writer._create_instance_uri(f"_val_{pulse_type}_detection"))
                    graph.add((test_node, DYN.hasPulseDetectionParams, target))

            # Link ALL DataSeries
            for uri in self.state.raw_series_uris.values():
                graph.add((test_node, DYN.hasDataSeries, URIRef(uri)))
            for uri in self.state.windowed_series_uris.values():
                graph.add((test_node, DYN.hasDataSeries, URIRef(uri)))
            for uri in self.state.processed_series_uris.values():
                graph.add((test_node, DYN.hasDataSeries, URIRef(uri)))

            # Link AnalysisFiles
            if "raw_data" in self.state.page_graphs:
                raw_graph = self.state.page_graphs["raw_data"]
                for s in raw_graph.subjects(RDF.type, DYN.AnalysisFile):
                    graph.add((test_node, DYN.hasAnalysisFile, s))
            if self.state.processed_file_uri:
                graph.add((test_node, DYN.hasAnalysisFile,
                           URIRef(self.state.processed_file_uri)))

            return graph

        except Exception as e:
            self.logger.error(f"Failed to build validation graph: {e}")
            return None

    # ── Instance ID renaming ──────────────────────────────────────────────────

    def _rename_instance_ids(self, graph: Graph, test_id: str) -> Graph:
        """Rename validation-time instance IDs to production IDs."""
        DYN = Namespace(DYN_NS)
        test_id_clean = test_id.replace('-', '_')

        old_test_id = (
            f"{self.state.specimen_id}_SHPBTest"
            if self.state.specimen_id
            else "_val"
        ).replace(" ", "_").replace("-", "_")

        replacements = {
            str(DYN["_val_equipment"]): str(DYN[test_id_clean]),
            str(DYN["_val_alignment"]): str(DYN[f"{test_id_clean}_alignment"]),
            str(DYN["_val_trust_card"]): str(DYN[f"{test_id_clean}_trust_card"]),
            str(DYN["_val_segmentation"]): str(DYN[f"{test_id_clean}_segmentation"]),
        }
        for pulse_type in ["incident", "transmitted", "reflected"]:
            replacements[str(DYN[f"_val_{pulse_type}_detection"])] = str(
                DYN[f"{test_id_clean}_{pulse_type}_detect"]
            )

        for key in ('time', 'incident', 'transmitted'):
            replacements[str(DYN[f"{old_test_id}_{key}"])] = str(
                DYN[f"{test_id_clean}_{key}"]
            )

        replacements[str(DYN[f"{old_test_id}_raw_csv"])] = str(
            DYN[f"{test_id_clean}_raw_csv"]
        )

        for key in self.state.windowed_series_uris:
            replacements[str(DYN[f"{old_test_id}_{key}"])] = str(
                DYN[f"{test_id_clean}_{key}"]
            )

        for key in self.state.processed_series_uris:
            replacements[str(DYN[f"{old_test_id}_{key}"])] = str(
                DYN[f"{test_id_clean}_{key}"]
            )

        replacements[str(DYN[f"{old_test_id}_processed_csv"])] = str(
            DYN[f"{test_id_clean}_processed_csv"]
        )

        final = Graph()
        self._instance_writer._setup_namespaces(final)

        for s, p, o in graph:
            # Only rename URIRef subjects that are in the replacements map.
            # BNode subjects (e.g. qudt:QuantityValue blank nodes) must be
            # preserved as BNodes — converting them to URIRefs would
            # disconnect the blank node object references from their
            # sub-triples and produce bare, invalid qudt:QuantityValue nodes.
            if isinstance(s, URIRef):
                new_s = URIRef(replacements.get(str(s), str(s)))
            else:
                new_s = s  # preserve BNodes as-is
            new_o = URIRef(replacements[str(o)]) if isinstance(o, URIRef) and str(o) in replacements else o
            final.add((new_s, p, new_o))

        return final

    # ── Export ────────────────────────────────────────────────────────────────

    def _export_test(self) -> bool:
        """Merge all page_graphs, rename instance IDs, validate, serialize."""
        self.show_progress()
        self.set_status("Exporting test...")

        try:
            writer = self._instance_writer
            test_id = self.state.test_id
            if not test_id:
                raise ValueError("No test ID available")

            # Merge all page graphs
            merged = Graph()
            writer._setup_namespaces(merged)
            for key, page_graph in self.state.page_graphs.items():
                for triple in page_graph:
                    merged.add(triple)

            # Rename _val_ prefixed URIs to production test ID
            final = self._rename_instance_ids(merged, test_id)

            # Resolve specimen directory
            specimen_id = self.state.specimen_id
            if not specimen_id:
                raise ValueError("No specimen ID available")

            specimen_dir = config.SPECIMENS_DIR / specimen_id
            if not specimen_dir.exists():
                raise FileNotFoundError(f"Specimen directory not found: {specimen_dir}")

            # Save raw CSV
            raw_dir = specimen_dir / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            raw_df = self.state.raw_df
            if raw_df is None:
                raise ValueError("Raw data not available")

            column_mapping = self.state.column_mapping
            rename_map = {source: target for target, source in column_mapping.items() if source}
            export_df = raw_df.rename(columns=rename_map)

            required_cols = ['time', 'incident', 'transmitted']
            missing = [c for c in required_cols if c not in export_df.columns]
            if missing:
                raise ValueError(f"Missing columns for export: {missing}")

            csv_handler = CSVDataHandler(export_df)
            csv_handler.validate_structure()

            test_id_clean = test_id.replace('-', '_')
            csv_path = raw_dir / f"{test_id_clean}_raw.csv"
            csv_handler.save_to_csv(csv_path)

            DYN = Namespace(DYN_NS)
            raw_file_id = f"{test_id_clean}_raw_csv"
            raw_file_node = URIRef(writer._create_instance_uri(raw_file_id))
            raw_rel_path = csv_path.relative_to(specimen_dir).as_posix()
            final.remove((raw_file_node, DYN.hasFilePath, None))
            final.add((raw_file_node, DYN.hasFilePath, writer._convert_to_rdf_value(raw_rel_path)))
            final.add((raw_file_node, DYN.hasFileName, writer._convert_to_rdf_value(csv_path.name)))
            final.add((raw_file_node, DYN.hasFileSize, writer._convert_to_rdf_value(os.path.getsize(csv_path))))
            final.add((raw_file_node, DYN.hasCreatedDate, writer._convert_to_rdf_value(date.today().isoformat())))

            # Save processed CSV if results available
            if self.state.calculation_results:
                import pandas as pd
                processed_dir = specimen_dir / "processed"
                processed_dir.mkdir(parents=True, exist_ok=True)
                processed_path = processed_dir / f"{test_id_clean}_processed.csv"
                pd.DataFrame(self.state.calculation_results).to_csv(
                    processed_path, index=False, float_format='%.6e'
                )

                processed_file_id = f"{test_id_clean}_processed_csv"
                processed_file_node = URIRef(writer._create_instance_uri(processed_file_id))
                processed_rel_path = processed_path.relative_to(specimen_dir).as_posix()
                final.remove((processed_file_node, DYN.hasFilePath, None))
                final.add((processed_file_node, DYN.hasFilePath, writer._convert_to_rdf_value(processed_rel_path)))
                final.add((processed_file_node, DYN.hasFileName, writer._convert_to_rdf_value(processed_path.name)))
                final.add((processed_file_node, DYN.hasFileSize, writer._convert_to_rdf_value(os.path.getsize(processed_path))))
                final.add((processed_file_node, DYN.hasCreatedDate, writer._convert_to_rdf_value(date.today().isoformat())))

            # Final SHACL validation
            validator = self._get_cached_validator()
            result = validator.validate(final)

            if result.has_blocking_issues():
                from ...validation_results_dialog import ValidationResultsDialog
                dialog = ValidationResultsDialog(result, parent=self)
                dialog.exec()
                return False

            # Strip class declarations for ontology-defined individuals
            INFRASTRUCTURE_TYPES = [
                DYN.SeriesType, DYN.PolarityType, DYN.DetectionMetric,
                DYN.MeasurementEquipment, DYN.StrainGauge, DYN.TestType,
                DYN.IncidentBar, DYN.TransmissionBar, DYN.StrikerBar,
                DYN.PulseShaper, DYN.MomentumTrap,
            ]
            for infra_type in INFRASTRUCTURE_TYPES:
                for s in list(final.subjects(RDF.type, infra_type)):
                    other_preds = set(final.predicates(s)) - {RDF.type}
                    if not other_preds:
                        final.remove((s, RDF.type, infra_type))

            # Serialize to TTL
            output_path = specimen_dir / f"{test_id_clean}.ttl"
            writer._save_graph(final, output_path)

            # Link test to specimen
            self._link_test_to_specimen(specimen_dir, test_id_clean)

            self.state.exported_file_path = str(output_path)
            self.set_status(f"Exported successfully: {output_path}")
            self.logger.info(f"Test exported to {output_path}")

            # Summarize fitness annotations for display
            fitness_summary = "None"
            if self.state.metrics_result and self.state.metrics_result.fitness_annotations:
                fitness_summary = ", ".join(self.state.metrics_result.fitness_annotations)

            if result.has_any_issues():
                self.show_warning(
                    "Export Complete with Warnings",
                    f"Test saved to:\n{output_path}\n\nWarnings:\n{result.get_summary()}"
                )
            else:
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Test saved successfully!\n\n"
                    f"File: {output_path}\n\n"
                    f"Test ID: {self.state.test_id}\n"
                    f"Fitness: {fitness_summary}"
                )

            return True

        except Exception as e:
            self.logger.error(f"Export failed: {e}", exc_info=True)
            self.set_status(f"Export failed: {e}", is_error=True)
            self.show_error("Export Failed", str(e))
            return False

        finally:
            self.hide_progress()

    def _link_test_to_specimen(self, specimen_dir: Path, test_id_clean: str) -> None:
        """Link test to specimen by updating specimen TTL."""
        specimen_id = self.state.specimen_id
        if not specimen_id:
            return

        specimen_ttl = specimen_dir / f"{specimen_id}_specimen.ttl"
        if not specimen_ttl.exists():
            self.logger.warning(f"Specimen TTL not found: {specimen_ttl}")
            return

        try:
            test_uri = f"dyn:{test_id_clean}"
            self._instance_writer.update_instance(
                instance_uri=self.state.specimen_uri or f"dyn:{specimen_id.replace('-', '_')}",
                updates={'dyn:hasSHPBCompressionTest': test_uri},
                ttl_file=specimen_ttl,
                skip_validation=True,
            )
            self.logger.info(f"Linked test {test_uri} to specimen")
        except Exception as e:
            self.logger.error(f"Failed to link test to specimen: {e}")

    # ── UI helpers ────────────────────────────────────────────────────────────

    def _make_id_form_readonly(self) -> None:
        """Set all identification form widgets to read-only."""
        if not self.id_form_widget or not hasattr(self.id_form_widget, 'form_fields'):
            return
        for field_info in self.id_form_widget.form_fields.values():
            w = field_info.widget
            if isinstance(w, QLineEdit):
                w.setReadOnly(True)
            elif hasattr(w, 'setEnabled'):
                w.setEnabled(False)

    def _on_override_changed(self, state: int) -> None:
        """Handle override checkbox — confirm, then show/hide override notes."""
        if state == Qt.CheckState.Checked.value:
            reply = QMessageBox.question(
                self,
                "Override Fitness Assessment",
                "Are you sure you want to manually override the fitness assessment?\n\n"
                "The assessment is based on 29 contextual validity metrics evaluated\n"
                "across 8 stages. Only override if you have expert knowledge that\n"
                "the auto-assessment is incorrect.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.override_check.blockSignals(True)
                self.override_check.setChecked(False)
                self.override_check.blockSignals(False)
                return
            self._override_notes_label.setVisible(True)
            self._override_notes.setVisible(True)
        else:
            self._override_notes_label.setVisible(False)
            self._override_notes.setVisible(False)

    def _display_fitness_assessment(self) -> None:
        """Display fitness/diagnostic annotations from the Science Trust Card."""
        result = self.state.metrics_result

        if not result:
            self._stages_label.setText("No metrics available")
            self._fitness_label.setText("--")
            self._diagnostics_label.setText("--")
            self._critical_banner.setVisible(False)
            return

        try:
            # Stages completed
            self._stages_label.setText(
                f"{result.evaluation_stages_completed}/8 stages completed"
            )

            # Critical failure banner
            self._critical_banner.setVisible(result.critical_failure)

            # Fitness annotations (green chips)
            if result.fitness_annotations:
                fitness_html = "  ".join(
                    f'<span style="background-color: #2e7d32; color: white; '
                    f'padding: 2px 6px; border-radius: 3px;">{a}</span>'
                    for a in result.fitness_annotations
                )
                self._fitness_label.setText(fitness_html)
            else:
                self._fitness_label.setText(
                    '<span style="color: gray;">No fitness annotations</span>'
                )

            # Diagnostic annotations (orange chips)
            if result.diagnostic_annotations:
                diag_html = "  ".join(
                    f'<span style="background-color: #e65100; color: white; '
                    f'padding: 2px 6px; border-radius: 3px;">{a}</span>'
                    for a in result.diagnostic_annotations
                )
                self._diagnostics_label.setText(diag_html)
            else:
                self._diagnostics_label.setText(
                    '<span style="color: gray;">No diagnostic flags</span>'
                )

        except Exception as e:
            self.logger.error(f"Failed to display fitness assessment: {e}")
            self._fitness_label.setText("Assessment Error")
            self._diagnostics_label.setText("")

    def _update_summary(self) -> None:
        """Update test summary display."""
        import numpy as np

        self.summary_labels['specimen'].setText(self.state.specimen_id or "--")

        test_date = self.state.get_equipment_value('hasTestDate')
        self.summary_labels['date'].setText(str(test_date) if test_date else "--")

        incident_bar_uri = self.state.get_equipment_value('hasIncidentBar')
        if incident_bar_uri:
            bar_name = incident_bar_uri.split('#')[-1] if '#' in incident_bar_uri else incident_bar_uri
            self.summary_labels['equipment'].setText(bar_name)
        else:
            self.summary_labels['equipment'].setText("--")

        results = self.state.calculation_results
        if results:
            stress_1w = results.get('stress_1w', [])
            strain_1w = results.get('strain_1w', [])
            if len(stress_1w) > 0:
                self.summary_labels['stress'].setText(f"{np.max(np.abs(stress_1w)):.1f} MPa")
            if len(strain_1w) > 0:
                self.summary_labels['strain'].setText(f"{np.max(np.abs(strain_1w)):.4f}")

        # Show FBC from Science Trust Card metrics
        fbc_metric = self.state.get_metric('FBC_Plateau') if self.state.has_metrics() else None
        if fbc_metric is not None and not fbc_metric.skipped:
            self.summary_labels['fbc'].setText(f"{fbc_metric.value:.4f}")

    def _update_output_path(self) -> None:
        """Update output path display."""
        test_id = self.state.test_id
        specimen_id = self.state.specimen_id

        if test_id and specimen_id:
            test_id_clean = test_id.replace('-', '_')
            output_path = config.SPECIMENS_DIR / specimen_id / f"{test_id_clean}.ttl"
            self.output_label.setText(str(output_path))
        else:
            self.output_label.setText("(will be determined on export)")
