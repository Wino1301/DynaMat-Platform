"""Export Page - Save SHPB test results to RDF.

Merges all cumulative page_graphs, renames validation-time instance IDs
to production IDs, runs final SHACL validation, and serializes to TTL.
"""

import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QLineEdit, QComboBox,
    QTextEdit, QCheckBox, QScrollArea, QWidget, QFrame,
    QMessageBox,
)
from PyQt6.QtCore import Qt
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

from .base_page import BaseSHPBPage
from .....mechanical.shpb.io.csv_data_handler import CSVDataHandler
from .....config import config

logger = logging.getLogger(__name__)

DYN_NS = "https://dynamat.utep.edu/ontology#"


class ExportPage(BaseSHPBPage):
    """Export page for SHPB analysis.

    Features:
    - Auto-generate or customize test ID
    - Set test type (specimen, calibration, elastic)
    - Display validity assessment
    - Override validity if needed
    - Export to RDF/TTL by merging all page_graphs
    """

    def __init__(self, state, ontology_manager, qudt_manager=None, parent=None):
        super().__init__(state, ontology_manager, qudt_manager, parent)

        self.setTitle("Export Test")
        self.setSubTitle("Review and save the SHPB test results.")

    def _setup_ui(self) -> None:
        """Setup page UI."""
        layout = self._create_base_layout()

        # Create scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)

        # Test identification
        id_group = self._create_group_box("Test Identification")
        id_layout = QGridLayout(id_group)

        id_layout.addWidget(QLabel("Test ID:"), 0, 0)
        self.test_id_edit = QLineEdit()
        self.test_id_edit.setPlaceholderText("Auto-generated if empty")
        id_layout.addWidget(self.test_id_edit, 0, 1)

        generate_btn = QPushButton("Generate")
        generate_btn.clicked.connect(self._generate_test_id)
        id_layout.addWidget(generate_btn, 0, 2)

        id_layout.addWidget(QLabel("Test Type:"), 1, 0)
        self.test_type_combo = QComboBox()
        self.test_type_combo.addItem("Specimen Test", "specimen")
        self.test_type_combo.addItem("Calibration Test", "calibration")
        self.test_type_combo.addItem("Elastic Test", "elastic")
        id_layout.addWidget(self.test_type_combo, 1, 1, 1, 2)

        content_layout.addWidget(id_group)

        # Validity assessment
        validity_group = self._create_group_box("Validity Assessment")
        validity_layout = QGridLayout(validity_group)

        validity_layout.addWidget(QLabel("Assessed Validity:"), 0, 0)
        self.validity_label = QLabel("--")
        self.validity_label.setStyleSheet("font-weight: bold;")
        validity_layout.addWidget(self.validity_label, 0, 1)

        validity_layout.addWidget(QLabel("Criteria Met:"), 1, 0)
        self.criteria_label = QLabel("--")
        self.criteria_label.setWordWrap(True)
        validity_layout.addWidget(self.criteria_label, 1, 1)

        validity_layout.addWidget(QLabel("Notes:"), 2, 0)
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)
        self.notes_edit.setPlaceholderText("Auto-generated validity notes...")
        validity_layout.addWidget(self.notes_edit, 2, 1)

        # Override section
        self.override_check = QCheckBox("Override Validity Assessment")
        self.override_check.stateChanged.connect(self._on_override_changed)
        validity_layout.addWidget(self.override_check, 3, 0, 1, 2)

        validity_layout.addWidget(QLabel("Override To:"), 4, 0)
        self.override_combo = QComboBox()
        self.override_combo.addItem("Valid Test", "dyn:ValidTest")
        self.override_combo.addItem("Questionable Test", "dyn:QuestionableTest")
        self.override_combo.addItem("Invalid Test", "dyn:InvalidTest")
        self.override_combo.setEnabled(False)
        validity_layout.addWidget(self.override_combo, 4, 1)

        validity_layout.addWidget(QLabel("Override Reason:"), 5, 0)
        self.override_reason_edit = QLineEdit()
        self.override_reason_edit.setEnabled(False)
        self.override_reason_edit.setPlaceholderText("Reason for override...")
        validity_layout.addWidget(self.override_reason_edit, 5, 1)

        content_layout.addWidget(validity_group)

        # Summary
        summary_group = self._create_group_box("Test Summary")
        summary_layout = QGridLayout(summary_group)

        summary_items = [
            ("Specimen:", "specimen"),
            ("Test Date:", "date"),
            ("Equipment:", "equipment"),
            ("Peak Stress:", "stress"),
            ("Peak Strain:", "strain"),
            ("FBC Metric:", "fbc"),
        ]

        self.summary_labels = {}
        for row, (label, key) in enumerate(summary_items):
            summary_layout.addWidget(QLabel(label), row, 0)
            value_label = QLabel("--")
            self.summary_labels[key] = value_label
            summary_layout.addWidget(value_label, row, 1)

        content_layout.addWidget(summary_group)

        # Output path
        output_group = self._create_group_box("Output")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("Output File:"), 0, 0)
        self.output_label = QLabel("--")
        self.output_label.setWordWrap(True)
        self.output_label.setStyleSheet("color: gray;")
        output_layout.addWidget(self.output_label, 0, 1)

        content_layout.addWidget(output_group)

        scroll.setWidget(content)
        layout.addWidget(scroll)

        self._add_status_area()

    def initializePage(self) -> None:
        """Initialize page when it becomes current."""
        super().initializePage()

        # Auto-generate test ID if not set
        if not self.state.test_id:
            self._generate_test_id()
        else:
            self.test_id_edit.setText(self.state.test_id)

        # Assess validity from metrics
        self._assess_validity()

        # Update summary
        self._update_summary()

        # Update output path
        self._update_output_path()

    def validatePage(self) -> bool:
        """Validate and export test."""
        # Get test ID
        test_id = self.test_id_edit.text().strip()
        if not test_id:
            self._generate_test_id()
            test_id = self.test_id_edit.text().strip()

        if not test_id:
            self.show_warning("Test ID Required", "Please enter or generate a test ID.")
            return False

        # Save to state as form data
        self.state.test_id = test_id
        self.state.export_form_data = {
            f"{DYN_NS}hasTestType": self.test_type_combo.currentData(),
            f"{DYN_NS}hasValidityNotes": self.notes_edit.toPlainText(),
        }

        # Handle validity
        if self.override_check.isChecked():
            self.state.export_form_data[f"{DYN_NS}hasTestValidity"] = self.override_combo.currentData()
            self.state.export_form_data[f"{DYN_NS}hasValidityOverrideReason"] = self.override_reason_edit.text()
        elif hasattr(self, '_assessed_validity'):
            self.state.export_form_data[f"{DYN_NS}hasTestValidity"] = self._assessed_validity
            if hasattr(self, '_assessed_criteria'):
                self.state.export_form_data[f"{DYN_NS}hasValidityCriteria"] = self._assessed_criteria

        # Build export validation graph and store it
        validation_graph = self._build_validation_graph()
        if validation_graph:
            self.state.page_graphs["export"] = validation_graph

        # Export test
        return self._export_test()

    # ------------------------------------------------------------------
    # Validation graph
    # ------------------------------------------------------------------

    def _build_validation_graph(self) -> Optional[Graph]:
        """Build graph with export metadata and sub-instance links on the test node.

        Adds export-specific properties (validity, test type, notes, timestamp)
        and links to all sub-instances (alignment, equilibrium, detection params,
        segmentation, tukey, data series) on the equipment/test node.

        Returns:
            RDF graph with export metadata, or None on error.
        """
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
                    rdf_value = writer._convert_to_rdf_value(value)
                    graph.add((test_node, prop_ref, rdf_value))

            # Add timestamp
            graph.add((test_node, DYN.hasAnalysisTimestamp,
                        writer._convert_to_rdf_value(datetime.now().isoformat())))

            # Link to sub-instances
            sub_links = {
                "hasAlignmentParams": "_val_alignment",
                "hasEquilibriumMetrics": "_val_equilibrium",
                "hasSegmentationParams": "_val_segmentation",
                "hasTukeyWindowParams": "_val_tukey_window",
            }
            for prop_name, inst_id in sub_links.items():
                # Only add link if the page graph exists
                page_key = {
                    "_val_alignment": "alignment",
                    "_val_equilibrium": "results",
                    "_val_segmentation": "segmentation",
                    "_val_tukey_window": "tukey_window",
                }.get(inst_id)
                if page_key and page_key in self.state.page_graphs:
                    target = URIRef(writer._create_instance_uri(inst_id))
                    graph.add((test_node, DYN[prop_name], target))

            # Link detection params (3x)
            if "pulse_detection" in self.state.page_graphs:
                for pulse_type in ["incident", "transmitted", "reflected"]:
                    target = URIRef(writer._create_instance_uri(f"_val_{pulse_type}_detection"))
                    graph.add((test_node, DYN.hasPulseDetectionParams, target))

            # Link DataSeries from raw_data page graph
            if "raw_data" in self.state.page_graphs:
                raw_graph = self.state.page_graphs["raw_data"]
                for s in raw_graph.subjects(RDF.type, DYN.DataSeries):
                    graph.add((test_node, DYN.hasDataSeries, s))
                # Link AnalysisFile
                for s in raw_graph.subjects(RDF.type, DYN.AnalysisFile):
                    graph.add((test_node, DYN.hasAnalysisFile, s))

            return graph

        except Exception as e:
            self.logger.error(f"Failed to build validation graph: {e}")
            return None

    # ------------------------------------------------------------------
    # Instance ID renaming
    # ------------------------------------------------------------------

    def _rename_instance_ids(self, graph: Graph, test_id: str) -> Graph:
        """Rename validation-time instance IDs to production IDs.

        Replaces ``_val_`` prefixed URIs with the actual test ID.

        Args:
            graph: Merged graph with _val_ prefixed URIs.
            test_id: Production test ID.

        Returns:
            New graph with renamed URIs.
        """
        DYN = Namespace(DYN_NS)
        test_id_clean = test_id.replace('-', '_')

        # Build URI replacement map
        replacements = {
            str(DYN["_val_equipment"]): str(DYN[test_id_clean]),
            str(DYN["_val_alignment"]): str(DYN[f"{test_id_clean}_alignment"]),
            str(DYN["_val_equilibrium"]): str(DYN[f"{test_id_clean}_equilibrium"]),
            str(DYN["_val_segmentation"]): str(DYN[f"{test_id_clean}_segmentation"]),
            str(DYN["_val_tukey_window"]): str(DYN[f"{test_id_clean}_tukey"]),
        }
        for pulse_type in ["incident", "transmitted", "reflected"]:
            replacements[str(DYN[f"_val_{pulse_type}_detection"])] = str(
                DYN[f"{test_id_clean}_{pulse_type}_detect"]
            )

        final = Graph()
        self._instance_writer._setup_namespaces(final)

        for s, p, o in graph:
            new_s = URIRef(replacements.get(str(s), str(s)))
            new_o = URIRef(replacements[str(o)]) if isinstance(o, URIRef) and str(o) in replacements else o
            final.add((new_s, p, new_o))

        return final

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_test(self) -> bool:
        """Merge all page_graphs, rename instance IDs, validate, serialize.

        Also saves CSV files (raw + processed) to the specimen directory.

        Returns:
            True if export successful.
        """
        self.show_progress()
        self.set_status("Exporting test...")

        try:
            writer = self._instance_writer
            test_id = self.state.test_id

            # Merge all page graphs
            merged = Graph()
            writer._setup_namespaces(merged)

            for key, page_graph in self.state.page_graphs.items():
                for triple in page_graph:
                    merged.add(triple)

            # Rename _val_ prefixed URIs to production test ID
            final = self._rename_instance_ids(merged, test_id)

            # Resolve specimen directory and save CSV
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

            # Rename columns to standard names
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

            # Save processed CSV if results available
            if self.state.calculation_results:
                import pandas as pd
                processed_dir = specimen_dir / "processed"
                processed_dir.mkdir(parents=True, exist_ok=True)
                processed_path = processed_dir / f"{test_id_clean}_processed.csv"
                pd.DataFrame(self.state.calculation_results).to_csv(
                    processed_path, index=False, float_format='%.6e'
                )

            # Final SHACL validation
            validator = self._get_cached_validator()
            result = validator.validate(final)

            if result.has_blocking_issues():
                from ...validation_results_dialog import ValidationResultsDialog
                dialog = ValidationResultsDialog(result, parent=self)
                dialog.exec()
                return False

            # Serialize to TTL
            output_path = specimen_dir / f"{test_id_clean}.ttl"
            writer._save_graph(final, output_path)

            # Link test to specimen
            self._link_test_to_specimen(specimen_dir, test_id_clean)

            # Success
            self.state.exported_file_path = str(output_path)

            self.set_status(f"Exported successfully: {output_path}")
            self.logger.info(f"Test exported to {output_path}")

            # Get validity from export form data for display
            validity = (self.state.export_form_data or {}).get(
                f"{DYN_NS}hasTestValidity", "Unknown"
            )

            # Show warnings if any
            if result.has_any_issues():
                self.show_warning(
                    "Export Complete with Warnings",
                    f"Test saved to:\n{output_path}\n\n"
                    f"Warnings:\n{result.get_summary()}"
                )
            else:
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Test saved successfully!\n\n"
                    f"File: {output_path}\n\n"
                    f"Test ID: {self.state.test_id}\n"
                    f"Validity: {validity}"
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
        """Link test to specimen by updating specimen TTL.

        Args:
            specimen_dir: Specimen directory path.
            test_id_clean: Cleaned test ID (underscores, no hyphens).
        """
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

    # ------------------------------------------------------------------
    # UI helpers (unchanged)
    # ------------------------------------------------------------------

    def _generate_test_id(self) -> None:
        """Generate a unique test ID."""
        specimen_id = self.state.specimen_id or "UNKNOWN"
        # Read test date from equipment form data, fall back to now
        test_date = self.state.get_equipment_value('hasTestDate')
        date_str = test_date or datetime.now().strftime("%Y%m%d")
        date_str = date_str.replace("-", "")

        test_id = f"{specimen_id}_SHPB_{date_str}"

        self.test_id_edit.setText(test_id)
        self.state.test_id = test_id

        self._update_output_path()

    def _assess_validity(self) -> None:
        """Assess test validity from equilibrium form data metrics."""
        if not self.state.equilibrium_form_data:
            self.validity_label.setText("Cannot assess - no metrics")
            self.validity_label.setStyleSheet("color: gray; font-weight: bold;")
            return

        try:
            fbc = self.state.get_equilibrium_metric('hasFBC')
            dsuf = self.state.get_equilibrium_metric('hasDSUF')
            seqi = self.state.get_equilibrium_metric('hasSEQI')

            # Simple validity assessment based on metrics
            criteria = []
            if fbc is not None and fbc > 0.95:
                criteria.append("dyn:FBCAbove95")
            if dsuf is not None and dsuf > 0.98:
                criteria.append("dyn:DSUFAbove98")
            if seqi is not None and seqi > 0.90:
                criteria.append("dyn:SEQIAbove90")

            # Determine validity
            if fbc is not None and fbc > 0.95 and dsuf is not None and dsuf > 0.98:
                validity = "dyn:ValidTest"
                notes = "Test meets equilibrium criteria."
            elif fbc is not None and fbc > 0.90:
                validity = "dyn:QuestionableTest"
                notes = "Test partially meets equilibrium criteria."
            else:
                validity = "dyn:InvalidTest"
                notes = "Test does not meet equilibrium criteria."

            # Store for use in validatePage
            self._assessed_validity = validity
            self._assessed_criteria = criteria

            # Update display
            if validity == "dyn:ValidTest":
                self.validity_label.setText("VALID")
                self.validity_label.setStyleSheet("color: green; font-weight: bold;")
            elif validity == "dyn:QuestionableTest":
                self.validity_label.setText("QUESTIONABLE")
                self.validity_label.setStyleSheet("color: orange; font-weight: bold;")
            else:
                self.validity_label.setText("INVALID")
                self.validity_label.setStyleSheet("color: red; font-weight: bold;")

            # Criteria
            criteria_text = ", ".join([c.replace("dyn:", "") for c in criteria]) or "None"
            self.criteria_label.setText(criteria_text)

            # Notes
            self.notes_edit.setText(notes)

        except Exception as e:
            self.logger.error(f"Failed to assess validity: {e}")
            self.validity_label.setText("Assessment Error")
            self.validity_label.setStyleSheet("color: red; font-weight: bold;")

    def _on_override_changed(self, state: int) -> None:
        """Handle override checkbox change."""
        enabled = state == Qt.CheckState.Checked.value
        self.override_combo.setEnabled(enabled)
        self.override_reason_edit.setEnabled(enabled)

    def _update_summary(self) -> None:
        """Update test summary display."""
        import numpy as np

        # Specimen
        self.summary_labels['specimen'].setText(self.state.specimen_id or "--")

        # Date (from equipment form data)
        test_date = self.state.get_equipment_value('hasTestDate')
        self.summary_labels['date'].setText(test_date or "--")

        # Equipment (from equipment form data)
        incident_bar_uri = self.state.get_equipment_value('hasIncidentBar')
        if incident_bar_uri:
            bar_name = incident_bar_uri.split('#')[-1] if '#' in incident_bar_uri else incident_bar_uri
            self.summary_labels['equipment'].setText(bar_name)
        else:
            self.summary_labels['equipment'].setText("--")

        # Results
        results = self.state.calculation_results
        if results:
            stress_1w = results.get('stress_1w', [])
            strain_1w = results.get('strain_1w', [])

            if len(stress_1w) > 0:
                self.summary_labels['stress'].setText(f"{np.max(np.abs(stress_1w)):.1f} MPa")
            if len(strain_1w) > 0:
                self.summary_labels['strain'].setText(f"{np.max(np.abs(strain_1w)):.4f}")

        # FBC (from equilibrium form data)
        fbc = self.state.get_equilibrium_metric('hasFBC')
        if fbc is not None:
            self.summary_labels['fbc'].setText(f"{fbc:.4f}")

    def _update_output_path(self) -> None:
        """Update output path display."""
        test_id = self.test_id_edit.text().strip()
        specimen_id = self.state.specimen_id

        if test_id and specimen_id:
            output_path = config.SPECIMENS_DIR / specimen_id / f"{test_id}.ttl"
            self.output_label.setText(str(output_path))
        else:
            self.output_label.setText("(will be determined on export)")
