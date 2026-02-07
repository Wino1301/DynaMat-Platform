"""
DynaMat Platform - Action Panel Widget
Left panel with action buttons for templates, recent files, etc.
"""

import logging
from typing import Dict, Any, List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QFrame,
    QListWidget, QListWidgetItem, QGroupBox, QHBoxLayout,
    QFileDialog, QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPixmap

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
    user_changed = pyqtSignal(str)
    
    def __init__(self, ontology_manager: OntologyManager, parent=None):
        super().__init__(parent)
        
        self.ontology_manager = ontology_manager
        self.recent_files = []  # List of recent file paths
        self.available_templates = {}  # Dict of template name -> data
        self.user_selector = None  # User selection combo box
        
        self._setup_ui()
        self._load_recent_files()
        self._load_available_templates()
        
        logger.info("Action panel widget initialized")
    
    def _setup_ui(self):
        """Setup the action panel UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # DynaMat Logo at the top
        self._create_logo_section(layout)

        # User Selector (between logo and quick actions)
        self._create_user_selector(layout)

        # Quick Actions Group
        self._create_quick_actions_group(layout)

        # Recent Files Group
        self._create_recent_files_group(layout)

        # Stretch to push everything to top
        layout.addStretch()

    def _create_logo_section(self, parent_layout):
        """Create logo section at the top of the panel"""
        import os

        # Create logo label
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Get path to logo image (misc/Dynamat_Icon.png)
        # Navigate from dynamat/gui/widgets/ up to project root, then to misc/
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        logo_path = os.path.join(project_root, "misc", "Dynamat_Icon.png")

        # Load and scale the logo
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            # Scale to fit sidebar width (around 220px wide, maintaining aspect ratio)
            scaled_pixmap = pixmap.scaledToWidth(220, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
            logger.info(f"DynaMat logo loaded from {logo_path}")
        else:
            # Fallback if logo not found
            logo_label.setText("DynaMat Platform")
            logo_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px;")
            logger.warning(f"Logo not found at {logo_path}")

        parent_layout.addWidget(logo_label)

        # Add a separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        parent_layout.addWidget(separator)

    def _create_user_selector(self, parent_layout):
        """Create user selector group"""
        group = QGroupBox("Current User")
        layout = QVBoxLayout(group)

        # User combo box
        self.user_selector = QComboBox()
        self.user_selector.setToolTip("Select the current user for metadata tracking")

        # Add placeholder text
        self.user_selector.addItem("Select User...")

        # Populate with User individuals from ontology
        try:
            # Use domain_queries to get full user instances with labels
            user_class_uri = "https://dynamat.utep.edu/ontology#User"
            users = self.ontology_manager.domain_queries.get_instances_of_class(user_class_uri)

            if users:
                for user in users:
                    user_uri = user['uri']
                    # Use label if available, otherwise use local name
                    user_label = user.get('label', user_uri.split('#')[-1])
                    self.user_selector.addItem(user_label, user_uri)

                logger.info(f"Loaded {len(users)} user(s) into user selector")
            else:
                logger.warning("No User individuals found in ontology")
                self.user_selector.addItem("No users available")
                self.user_selector.setEnabled(False)

        except Exception as e:
            logger.error(f"Failed to load users from ontology: {e}")
            self.user_selector.addItem("Error loading users")
            self.user_selector.setEnabled(False)

        # Connect signal
        self.user_selector.currentIndexChanged.connect(self._on_user_changed)

        layout.addWidget(self.user_selector)
        parent_layout.addWidget(group)

    def _on_user_changed(self, index):
        """Handle user selection change"""
        if index > 0:  # Skip placeholder at index 0
            user_uri = self.user_selector.itemData(index)
            if user_uri:
                self.user_changed.emit(user_uri)
                logger.info(f"User changed to: {self.user_selector.currentText()} ({user_uri})")

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
        """Load available templates (placeholder for backwards compatibility)"""
        # Templates functionality moved to individual activity forms
        # Keeping method stub to avoid breaking existing code
        self.available_templates = {}
        logger.info("Template loading skipped - templates now managed per activity form")

    def get_selected_user(self) -> Optional[str]:
        """
        Get the currently selected user URI.

        Returns:
            User URI string, or None if no user selected
        """
        if self.user_selector and self.user_selector.currentIndex() > 0:
            return self.user_selector.currentData()
        return None