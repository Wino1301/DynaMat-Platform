"""
DynaMat Platform - Action Panel Widget
Left panel with action buttons for templates, recent files, etc.
"""

import logging
from typing import Dict, Any, List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QFrame,
    QListWidget, QListWidgetItem, QGroupBox, QHBoxLayout,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

from ...ontology.manager import OntologyManager

logger = logging.getLogger(__name__)


class ActionPanelWidget(QWidget):
    """
    Action panel widget providing quick access to common operations.
    
    Features:
    - Template loading and saving
    - Recent files list
    - New instance creation
    - Common shortcuts
    """
    
    # Signals
    template_loaded = pyqtSignal(dict)
    template_saved = pyqtSignal(str)
    new_instance = pyqtSignal(str)
    recent_file_opened = pyqtSignal(str)
    
    def __init__(self, ontology_manager: OntologyManager, parent=None):
        super().__init__(parent)
        
        self.ontology_manager = ontology_manager
        self.recent_files = []  # List of recent file paths
        self.available_templates = {}  # Dict of template name -> data
        
        self._setup_ui()
        self._load_recent_files()
        self._load_available_templates()
        
        logger.info("Action panel widget initialized")
    
    def _setup_ui(self):
        """Setup the action panel UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # Quick Actions Group
        self._create_quick_actions_group(layout)
        
        # Templates Group
        self._create_templates_group(layout)
        
        # Recent Files Group
        self._create_recent_files_group(layout)
        
        # Stretch to push everything to top
        layout.addStretch()
    
    def _create_quick_actions_group(self, parent_layout):
        """Create quick actions group"""
        group = QGroupBox("Quick Actions")
        layout = QVBoxLayout(group)
        
        # New Specimen button
        new_specimen_btn = QPushButton("New Specimen")
        new_specimen_btn.setToolTip("Create a new specimen instance")
        new_specimen_btn.clicked.connect(
            lambda: self.new_instance.emit("https://dynamat.utep.edu/ontology#Specimen")
        )
        layout.addWidget(new_specimen_btn)
        
        # New Test button
        new_test_btn = QPushButton("New Test")
        new_test_btn.setToolTip("Create a new test instance")
        new_test_btn.setEnabled(False)  # Disabled until implemented
        layout.addWidget(new_test_btn)
        
        # Search button
        search_btn = QPushButton("Search Database")
        search_btn.setToolTip("Search existing specimens and tests")
        search_btn.clicked.connect(self._show_search_dialog)
        layout.addWidget(search_btn)
        
        # Validate button
        validate_btn = QPushButton("Validate All")
        validate_btn.setToolTip("Validate current data against ontology")
        validate_btn.clicked.connect(self._validate_current_data)
        layout.addWidget(validate_btn)
        
        parent_layout.addWidget(group)
    
    def _create_templates_group(self, parent_layout):
        """Create templates group"""
        group = QGroupBox("Templates")
        layout = QVBoxLayout(group)
        
        # Template buttons
        load_template_btn = QPushButton("Load Template")
        load_template_btn.setToolTip("Load a specimen or test template")
        load_template_btn.clicked.connect(self._load_template)
        layout.addWidget(load_template_btn)
        
        save_template_btn = QPushButton("Save Template")
        save_template_btn.setToolTip("Save current data as template")
        save_template_btn.clicked.connect(self._save_template)
        layout.addWidget(save_template_btn)
        
        # Template list (show available templates)
        self.template_list = QListWidget()
        self.template_list.setMaximumHeight(100)
        self.template_list.itemDoubleClicked.connect(self._load_template_from_list)
        layout.addWidget(self.template_list)
        
        parent_layout.addWidget(group)
    
    def _create_recent_files_group(self, parent_layout):
        """Create recent files group"""
        group = QGroupBox("Recent Files")
        layout = QVBoxLayout(group)
        
        # Recent files list
        self.recent_list = QListWidget()
        self.recent_list.setMaximumHeight(120)
        self.recent_list.itemDoubleClicked.connect(self._open_recent_file)
        layout.addWidget(self.recent_list)
        
        # Clear recent button
        clear_recent_btn = QPushButton("Clear Recent")
        clear_recent_btn.setMaximumHeight(25)
        clear_recent_btn.clicked.connect(self._clear_recent_files)
        layout.addWidget(clear_recent_btn)
        
        parent_layout.addWidget(group)
    
    def _load_template(self):
        """Load a template file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Template",
            "", "Template Files (*.ttl *.json);;All Files (*)"
        )
        
        if file_path:
            try:
                # This would load the actual template file
                # For now, show placeholder
                template_data = {
                    "name": "Loaded Template",
                    "file_path": file_path,
                    "data": {}  # Actual template data would go here
                }
                
                self.template_loaded.emit(template_data)
                self._add_recent_file(file_path)
                
                logger.info(f"Template loaded: {file_path}")
                
            except Exception as e:
                logger.error(f"Failed to load template: {e}")
                QMessageBox.critical(
                    self, "Error",
                    f"Failed to load template:\n{str(e)}"
                )
    
    def _save_template(self):
        """Save current data as template"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Template",
            "", "Template Files (*.ttl *.json);;All Files (*)"
        )
        
        if file_path:
            try:
                # This would save the actual template file
                # For now, just show success message
                QMessageBox.information(
                    self, "Template Saved",
                    f"Template saved to:\n{file_path}"
                )
                
                self.template_saved.emit(file_path)
                self._add_recent_file(file_path)
                
                logger.info(f"Template saved: {file_path}")
                
            except Exception as e:
                logger.error(f"Failed to save template: {e}")
                QMessageBox.critical(
                    self, "Error",
                    f"Failed to save template:\n{str(e)}"
                )
    
    def _load_template_from_list(self, item: QListWidgetItem):
        """Load template from the template list"""
        template_name = item.text()
        if template_name in self.available_templates:
            template_data = self.available_templates[template_name]
            self.template_loaded.emit(template_data)
            logger.info(f"Template loaded from list: {template_name}")
    
    def _open_recent_file(self, item: QListWidgetItem):
        """Open a recent file"""
        file_path = item.text()
        self.recent_file_opened.emit(file_path)
        logger.info(f"Recent file opened: {file_path}")
    
    def _clear_recent_files(self):
        """Clear recent files list"""
        self.recent_files.clear()
        self.recent_list.clear()
        self._save_recent_files()
        logger.info("Recent files cleared")
    
    def _show_search_dialog(self):
        """Show database search dialog"""
        QMessageBox.information(
            self, "Search Database",
            "Database search functionality will be implemented with the database interface."
        )
    
    def _validate_current_data(self):
        """Validate current data"""
        QMessageBox.information(
            self, "Validation",
            "Data validation will be performed based on the current activity."
        )
    
    def _add_recent_file(self, file_path: str):
        """Add file to recent files list"""
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        
        self.recent_files.insert(0, file_path)
        
        # Limit to 10 recent files
        if len(self.recent_files) > 10:
            self.recent_files = self.recent_files[:10]
        
        self._update_recent_files_display()
        self._save_recent_files()
    
    def _update_recent_files_display(self):
        """Update the recent files list display"""
        self.recent_list.clear()
        
        for file_path in self.recent_files:
            # Show just filename, store full path
            filename = file_path.split('/')[-1] if '/' in file_path else file_path.split('\\')[-1]
            item = QListWidgetItem(file_path)
            item.setToolTip(file_path)  # Full path in tooltip
            self.recent_list.addItem(item)
    
    def _load_recent_files(self):
        """Load recent files from settings"""
        # This would load from application settings/config
        # For now, use empty list
        self.recent_files = []
        self._update_recent_files_display()
    
    def _save_recent_files(self):
        """Save recent files to settings"""
        # This would save to application settings/config
        pass
    
    def _load_available_templates(self):
        """Load available templates"""
        # This would scan the templates directory
        # For now, create some example templates
        self.available_templates = {
            "Al6061 Cylindrical": {
                "name": "Al6061 Cylindrical",
                "description": "Aluminum 6061 cylindrical specimen template",
                "data": {
                    "https://dynamat.utep.edu/ontology#hasMaterialID": "AL6061",
                    "https://dynamat.utep.edu/ontology#hasShape": "https://dynamat.utep.edu/ontology#CylindricalShape"
                }
            },
            "Steel Rectangular": {
                "name": "Steel Rectangular", 
                "description": "Steel rectangular specimen template",
                "data": {
                    "https://dynamat.utep.edu/ontology#hasMaterialID": "STEEL",
                    "https://dynamat.utep.edu/ontology#hasShape": "https://dynamat.utep.edu/ontology#RectangularShape"
                }
            }
        }
        
        # Update template list display
        self.template_list.clear()
        for template_name in self.available_templates:
            item = QListWidgetItem(template_name)
            item.setToolTip(self.available_templates[template_name]["description"])
            self.template_list.addItem(item)