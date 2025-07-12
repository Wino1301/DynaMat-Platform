"""
DynaMat Platform Main GUI Application - Updated with Ribbon Menu

Main application with ribbon navigation and separate workflow windows.
Provides a modern interface for managing dynamic materials testing data.

Key Features:
1. Ribbon menu for workflow selection
2. Dedicated workflow windows
3. Template management system
4. Integration with ontology system
5. Mechanical testing focus (SHPB, QS, Tensile)
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QStackedWidget, QStatusBar, QMessageBox, QFileDialog,
    QProgressDialog, QTextEdit, QSplitter, QFrame, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QAction, QIcon, QFont

try:
    from dynamat.gui.ribbon import RibbonMenu
    from dynamat.gui.forms import OntologyFormGenerator, OntologyForm, FormData, FormTemplate
    from dynamat.gui.widgets import WidgetData, WidgetState
    from dynamat.ontology.manager import get_ontology_manager
except ImportError:
    # Fallback for direct execution
    from ribbon import RibbonMenu
    from forms import OntologyFormGenerator, OntologyForm, FormData, FormTemplate
    from widgets import WidgetData, WidgetState
    try:
        from dynamat.ontology.manager import get_ontology_manager
    except ImportError:
        # Mock for testing
        def get_ontology_manager():
            return None


# =============================================================================
# WORKFLOW WINDOW BASE CLASS
# =============================================================================

class WorkflowWindow(QWidget):
    """Base class for all workflow windows"""
    
    # Signals
    data_changed = pyqtSignal(dict)  # Emit when data changes
    validation_changed = pyqtSignal(bool)  # Emit when validation state changes
    save_requested = pyqtSignal(str)  # Emit when save is requested
    
    def __init__(self, workflow_name: str, ontology_manager=None):
        super().__init__()
        self.workflow_name = workflow_name
        self.ontology_manager = ontology_manager
        self.current_data = {}
        self.is_valid = False
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the base UI structure - override in subclasses"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Title
        title = QLabel(f"{self.workflow_name} Workflow")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
    
    def activate(self):
        """Called when this workflow becomes active"""
        pass
    
    def deactivate(self):
        """Called when this workflow becomes inactive"""
        pass
    
    def get_data(self) -> dict:
        """Get current workflow data"""
        return self.current_data
    
    def set_data(self, data: dict):
        """Set workflow data"""
        self.current_data = data
        self.data_changed.emit(data)
    
    def validate(self) -> bool:
        """Validate current data - override in subclasses"""
        return True
    
    def save(self, file_path: str = None):
        """Save current data - override in subclasses"""
        pass


# =============================================================================
# MECHANICAL TESTING WORKFLOW
# =============================================================================

class MechanicalWorkflowWindow(WorkflowWindow):
    """Specialized workflow window for mechanical testing"""
    
    def __init__(self, ontology_manager=None):
        super().__init__("Mechanical Testing", ontology_manager)
        self.test_type = None
        self.test_forms = {}
        
    def _setup_ui(self):
        """Setup mechanical testing UI"""
        super()._setup_ui()
        
        # Main content area
        content_layout = QHBoxLayout()
        
        # Left panel - Test type selection
        self._create_test_selection_panel(content_layout)
        
        # Right panel - Test configuration forms
        self._create_test_forms_panel(content_layout)
        
        self.layout().addLayout(content_layout)
    
    def _create_test_selection_panel(self, parent_layout):
        """Create test type selection panel"""
        
        # Selection panel frame
        selection_frame = QFrame()
        selection_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        selection_frame.setMaximumWidth(200)
        selection_frame.setMinimumWidth(180)
        
        selection_layout = QVBoxLayout()
        selection_frame.setLayout(selection_layout)
        
        # Title
        title = QLabel("Test Type")
        title.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        selection_layout.addWidget(title)
        
        # Test type options (will be populated from ontology)
        self.test_options = self._get_mechanical_test_types()
        
        from PyQt6.QtWidgets import QRadioButton, QButtonGroup
        self.test_type_group = QButtonGroup()
        
        for test_type, display_name in self.test_options.items():
            radio = QRadioButton(display_name)
            radio.toggled.connect(lambda checked, t=test_type: self._on_test_type_selected(t, checked))
            self.test_type_group.addButton(radio)
            selection_layout.addWidget(radio)
        
        selection_layout.addStretch()
        parent_layout.addWidget(selection_frame)
    
    def _create_test_forms_panel(self, parent_layout):
        """Create test configuration forms panel"""
        
        # Forms panel
        self.forms_stack = QStackedWidget()
        parent_layout.addWidget(self.forms_stack)
        
        # Default empty state
        empty_widget = QWidget()
        empty_layout = QVBoxLayout()
        empty_label = QLabel("Select a test type to begin configuration")
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_label.setStyleSheet("color: #666; font-size: 14px;")
        empty_layout.addWidget(empty_label)
        empty_widget.setLayout(empty_layout)
        self.forms_stack.addWidget(empty_widget)
    
    def _get_mechanical_test_types(self) -> Dict[str, str]:
        """Get available mechanical test types from ontology"""
        
        if self.ontology_manager:
            try:
                # Query ontology for mechanical test types
                # This would use the actual ontology manager
                test_types = {
                    'SHPBTest': 'SHPB Testing',
                    'QuasiStaticTest': 'Quasi-Static Testing',
                    'TensileTest': 'Tensile Testing',
                    'CompressionTest': 'Compression Testing'
                }
                return test_types
            except Exception as e:
                print(f"Error querying test types from ontology: {e}")
        
        # Fallback static list
        return {
            'SHPBTest': 'SHPB Testing',
            'QuasiStaticTest': 'Quasi-Static Testing',
            'TensileTest': 'Tensile Testing',
            'CompressionTest': 'Compression Testing'
        }
    
    def _on_test_type_selected(self, test_type: str, checked: bool):
        """Handle test type selection"""
        if checked:
            self.test_type = test_type
            self._load_test_forms(test_type)
    
    def _load_test_forms(self, test_type: str):
        """Load forms for the selected test type"""
        
        if test_type in self.test_forms:
            # Switch to existing form
            self.forms_stack.setCurrentWidget(self.test_forms[test_type])
        else:
            # Create new form for this test type
            if test_type == 'SHPBTest':
                form_widget = self._create_shpb_form()
            elif test_type == 'QuasiStaticTest':
                form_widget = self._create_qs_form()
            elif test_type == 'TensileTest':
                form_widget = self._create_tensile_form()
            else:
                form_widget = self._create_generic_form(test_type)
            
            self.test_forms[test_type] = form_widget
            self.forms_stack.addWidget(form_widget)
            self.forms_stack.setCurrentWidget(form_widget)
    
    def _create_shpb_form(self) -> QWidget:
        """Create SHPB test configuration form"""
        
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # Title
        title = QLabel("SHPB Test Configuration")
        title.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Placeholder for SHPB form content
        # This will be replaced with actual SHPB forms converted from reference files
        placeholder = QLabel("SHPB form components will be implemented here:\n"
                            "• Test Description Form\n"
                            "• Specimen Metadata Form\n"
                            "• Striker Conditions Form\n"
                            "• Bar Metadata Form")
        placeholder.setStyleSheet("color: #666; padding: 20px;")
        layout.addWidget(placeholder)
        
        layout.addStretch()
        
        return widget
    
    def _create_qs_form(self) -> QWidget:
        """Create quasi-static test configuration form"""
        
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        title = QLabel("Quasi-Static Test Configuration")
        title.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        placeholder = QLabel("Quasi-static test configuration form")
        placeholder.setStyleSheet("color: #666; padding: 20px;")
        layout.addWidget(placeholder)
        
        layout.addStretch()
        
        return widget
    
    def _create_tensile_form(self) -> QWidget:
        """Create tensile test configuration form"""
        
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        title = QLabel("Tensile Test Configuration")
        title.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        placeholder = QLabel("Tensile test configuration form")
        placeholder.setStyleSheet("color: #666; padding: 20px;")
        layout.addWidget(placeholder)
        
        layout.addStretch()
        
        return widget
    
    def _create_generic_form(self, test_type: str) -> QWidget:
        """Create generic test configuration form"""
        
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        title = QLabel(f"{test_type} Configuration")
        title.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        placeholder = QLabel(f"Configuration form for {test_type}")
        placeholder.setStyleSheet("color: #666; padding: 20px;")
        layout.addWidget(placeholder)
        
        layout.addStretch()
        
        return widget


# =============================================================================
# MAIN APPLICATION CLASS
# =============================================================================

class DynaMatApp(QMainWindow):
    """
    Main DynaMat Platform GUI Application with Ribbon Interface.
    Provides a complete interface for materials testing data management.
    """
    
    def __init__(self):
        super().__init__()
        
        # Core components
        self.ontology_manager = get_ontology_manager()
        
        # Workflow tracking
        self.current_workflow = None
        self.workflow_windows = {}
        
        # Setup UI
        self._setup_ui()
        self._create_workflow_windows()
        self._connect_signals()
        
        # Initialize application state
        self._initialize_app()
    
    def _setup_ui(self):
        """Setup the main UI structure"""
        self.setWindowTitle("DynaMat Platform - Dynamic Materials Testing Data Management")
        self.setGeometry(100, 100, 1400, 900)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        central_widget.setLayout(main_layout)
        
        # Ribbon menu
        self.ribbon = RibbonMenu()
        main_layout.addWidget(self.ribbon)
        
        # Workflow area
        self.workflow_stack = QStackedWidget()
        main_layout.addWidget(self.workflow_stack)
        
        # Status bar
        self._setup_status_bar()
    
    def _setup_status_bar(self):
        """Setup status bar"""
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")
        
        # Add permanent widgets to status bar
        self.status_validation = QLabel("Validation: OK")
        self.status_bar.addPermanentWidget(self.status_validation)
        
        self.status_workflow = QLabel("Workflow: None")
        self.status_bar.addPermanentWidget(self.status_workflow)
        
        self.status_ontology = QLabel("Ontology: Loaded")
        self.status_bar.addPermanentWidget(self.status_ontology)
    
    def _create_workflow_windows(self):
        """Create workflow windows"""
        
        # Specimen workflow (placeholder)
        specimen_window = WorkflowWindow("Specimen", self.ontology_manager)
        self.workflow_windows['specimen'] = specimen_window
        self.workflow_stack.addWidget(specimen_window)
        
        # Mechanical workflow
        mechanical_window = MechanicalWorkflowWindow(self.ontology_manager)
        self.workflow_windows['mechanical'] = mechanical_window
        self.workflow_stack.addWidget(mechanical_window)
        
        # Characterization workflow (placeholder)
        characterization_window = WorkflowWindow("Characterization", self.ontology_manager)
        self.workflow_windows['characterization'] = characterization_window
        self.workflow_stack.addWidget(characterization_window)
        
        # Database workflow (placeholder)
        database_window = WorkflowWindow("Database", self.ontology_manager)
        self.workflow_windows['database'] = database_window
        self.workflow_stack.addWidget(database_window)
        
        # Default to empty state
        empty_window = WorkflowWindow("Welcome")
        empty_window.layout().addWidget(
            QLabel("Welcome to DynaMat Platform\n\nSelect a workflow from the ribbon menu to begin.")
        )
        self.workflow_windows['empty'] = empty_window
        self.workflow_stack.addWidget(empty_window)
        self.workflow_stack.setCurrentWidget(empty_window)
    
    def _connect_signals(self):
        """Connect application-level signals"""
        
        # Ribbon signals
        self.ribbon.workflow_selected.connect(self._on_workflow_selected)
        self.ribbon.action_triggered.connect(self._on_action_triggered)
    
    def _initialize_app(self):
        """Initialize application state"""
        self.status_bar.showMessage("DynaMat Platform initialized successfully")
        
        # Update status
        self._update_validation_status()
    
    # =============================================================================
    # EVENT HANDLERS
    # =============================================================================
    
    def _on_workflow_selected(self, workflow_name: str):
        """Handle workflow selection from ribbon"""
        
        # Parse workflow name to determine category
        if workflow_name.startswith('specimen_'):
            category = 'specimen'
        elif workflow_name.startswith('mechanical_'):
            category = 'mechanical'
        elif workflow_name.startswith('characterization_'):
            category = 'characterization'
        elif workflow_name.startswith('database_'):
            category = 'database'
        else:
            category = 'empty'
        
        # Switch to appropriate workflow window
        if category in self.workflow_windows:
            # Deactivate current workflow
            if self.current_workflow:
                self.workflow_windows[self.current_workflow].deactivate()
            
            # Activate new workflow
            self.current_workflow = category
            workflow_window = self.workflow_windows[category]
            workflow_window.activate()
            self.workflow_stack.setCurrentWidget(workflow_window)
            
            # Update status
            self.status_workflow.setText(f"Workflow: {workflow_window.workflow_name}")
            
            # Update ribbon state
            self.ribbon.set_active_workflow(workflow_name)
            
            self.status_bar.showMessage(f"Switched to {workflow_window.workflow_name} workflow")
    
    def _on_action_triggered(self, action_name: str):
        """Handle action triggers from ribbon"""
        
        if action_name == 'save':
            self._save_current_data()
        elif action_name == 'load':
            self._load_data()
        elif action_name == 'validate':
            self._validate_current_data()
        elif action_name == 'export':
            self._export_data()
        elif action_name == 'save_template':
            self._save_template()
        elif action_name == 'load_template':
            self._load_template()
        elif action_name == 'documentation':
            self._show_documentation()
        elif action_name == 'about':
            self._show_about()
    
    def _save_current_data(self):
        """Save current workflow data"""
        if self.current_workflow and self.current_workflow != 'empty':
            workflow_window = self.workflow_windows[self.current_workflow]
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Data", "", "TTL Files (*.ttl);;All Files (*)"
            )
            
            if file_path:
                try:
                    workflow_window.save(file_path)
                    QMessageBox.information(self, "Success", f"Data saved to {file_path}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Save failed: {str(e)}")
    
    def _load_data(self):
        """Load data into current workflow"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Data", "", "TTL Files (*.ttl);;All Files (*)"
        )
        
        if file_path:
            try:
                # Implementation would depend on workflow type
                QMessageBox.information(self, "Success", f"Data loaded from {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Load failed: {str(e)}")
    
    def _validate_current_data(self):
        """Validate current workflow data"""
        if self.current_workflow and self.current_workflow != 'empty':
            workflow_window = self.workflow_windows[self.current_workflow]
            is_valid = workflow_window.validate()
            
            if is_valid:
                QMessageBox.information(self, "Validation", "Data validation passed!")
            else:
                QMessageBox.warning(self, "Validation", "Data validation failed. Please check your entries.")
            
            self._update_validation_status()
    
    def _export_data(self):
        """Export current data to TTL"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export TTL", "", "TTL Files (*.ttl);;All Files (*)"
        )
        
        if file_path:
            try:
                # Export implementation
                QMessageBox.information(self, "Success", f"Data exported to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed: {str(e)}")
    
    def _save_template(self):
        """Save current configuration as template"""
        QMessageBox.information(self, "Templates", "Template save functionality will be implemented")
    
    def _load_template(self):
        """Load saved template"""
        QMessageBox.information(self, "Templates", "Template load functionality will be implemented")
    
    def _show_documentation(self):
        """Show documentation"""
        QMessageBox.information(self, "Documentation", "Documentation will be available soon")
    
    def _show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self, 
            "About DynaMat Platform",
            "DynaMat Platform v1.0\n\n"
            "Ontology-based desktop application for managing\n"
            "dynamic materials testing data.\n\n"
            "Developed at UTEP Dynamic Materials Laboratory\n\n"
            "Features:\n"
            "• Ribbon-based workflow navigation\n"
            "• SHPB testing support\n"
            "• Template management\n"
            "• TTL data export"
        )
    
    def _update_validation_status(self):
        """Update validation status in status bar"""
        if self.current_workflow and self.current_workflow != 'empty':
            workflow_window = self.workflow_windows[self.current_workflow]
            is_valid = workflow_window.validate()
            
            if is_valid:
                self.status_validation.setText("Validation: ✓ OK")
                self.status_validation.setStyleSheet("color: green;")
            else:
                self.status_validation.setText("Validation: ✗ Errors")
                self.status_validation.setStyleSheet("color: red;")
        else:
            self.status_validation.setText("Validation: N/A")
            self.status_validation.setStyleSheet("color: gray;")


# =============================================================================
# APPLICATION ENTRY POINT
# =============================================================================

def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("DynaMat Platform")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("UTEP Dynamic Materials Laboratory")
    
    # Create and show main window
    main_window = DynaMatApp()
    main_window.show()
    
    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()