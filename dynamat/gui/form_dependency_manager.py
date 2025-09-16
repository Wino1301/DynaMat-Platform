"""
DynaMat Platform - Form Dependency Manager
Manages dynamic form field visibility based on field values
"""

import logging
from typing import Dict, Set, Optional, Any
from PyQt6.QtWidgets import (
    QWidget, QComboBox, QGroupBox, QFormLayout,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class FormDependencyManager(QObject):
    """
    Manages form field dependencies and dynamic visibility.
    """
    
    # Signal emitted when visibility changes
    visibility_changed = pyqtSignal()
    
    def __init__(self, ontology_manager):
        super().__init__()
        self.ontology_manager = ontology_manager
        
        # Track form elements
        self.form_widget = None
        self.group_boxes = {}  # group_name -> QGroupBox
        self.field_widgets = {}  # uri -> widget
        self.field_labels = {}  # widget -> label
        
        # Composite-specific configuration
        self.COMPOSITE_URI = "https://dynamat.utep.edu/ontology#Composite"
        self.MATERIAL_FIELD_URI = "https://dynamat.utep.edu/ontology#hasMaterial"
        
        logger.info("Form dependency manager initialized")
    
    def register_form(self, form_widget: QWidget):
        """
        Register a form widget and set up dependencies.
        
        Args:
            form_widget: Form widget created by OntologyFormBuilder
        """
        self.form_widget = form_widget
        
        # Clear previous registrations
        self.group_boxes.clear()
        self.field_widgets.clear()
        self.field_labels.clear()
        
        # Find all group boxes in the form
        for group_box in form_widget.findChildren(QGroupBox):
            group_name = group_box.title()
            self.group_boxes[group_name] = group_box
            logger.debug(f"Found group: {group_name}")
        
        # Register fields if form has form_fields attribute
        if hasattr(form_widget, 'form_fields'):
            for uri, field in form_widget.form_fields.items():
                self.field_widgets[uri] = field.widget
                
                # Connect material field change signal
                if uri == self.MATERIAL_FIELD_URI:
                    if isinstance(field.widget, QComboBox):
                        field.widget.currentIndexChanged.connect(
                            self.on_material_changed
                        )
                        logger.info("Connected material field change signal")
                    
                # Find and store field labels (for hiding/showing)
                self._find_field_label(field.widget)
        
        # Apply initial visibility rules
        self._apply_initial_visibility()
        
        logger.info(f"Registered form with {len(self.field_widgets)} fields and {len(self.group_boxes)} groups")
    
    def _find_field_label(self, widget: QWidget):
        """Find the label associated with a field widget in a QFormLayout."""
        parent = widget.parent()
        if parent and parent.layout() and isinstance(parent.layout(), QFormLayout):
            layout = parent.layout()
            for i in range(layout.rowCount()):
                label_item = layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
                field_item = layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
                if field_item and field_item.widget() == widget:
                    if label_item and label_item.widget():
                        self.field_labels[widget] = label_item.widget()
                        break
    
    def on_material_changed(self):
        """Handle material selection change."""
        material_widget = self.field_widgets.get(self.MATERIAL_FIELD_URI)
        if not material_widget or not isinstance(material_widget, QComboBox):
            return
        
        # Get selected material URI
        material_uri = material_widget.currentData()
        
        if material_uri:
            logger.info(f"Material changed to: {material_uri}")
            
            # Check if material is a composite
            is_composite = self.ontology_manager.is_instance_of_type(
                material_uri, self.COMPOSITE_URI
            )
            
            logger.info(f"Material is composite: {is_composite}")
            
            # Show/hide composite properties group
            self.set_group_visibility("Composite Properties", is_composite)
        else:
            # No material selected, hide composite fields
            self.set_group_visibility("Composite Properties", False)
        
        self.visibility_changed.emit()
    
    def set_group_visibility(self, group_name: str, visible: bool):
        """
        Show or hide a form group.
        
        Args:
            group_name: Name of the group to show/hide
            visible: True to show, False to hide
        """
        if group_name in self.group_boxes:
            group_box = self.group_boxes[group_name]
            group_box.setVisible(visible)
            
            # Also update the visibility of all fields in the group
            # This ensures proper form layout updates
            for child in group_box.findChildren(QWidget):
                child.setVisible(visible)
            
            logger.debug(f"Set group '{group_name}' visibility to {visible}")
        else:
            logger.warning(f"Group '{group_name}' not found in form")
    
    def _apply_initial_visibility(self):
        """Apply initial visibility rules based on current form state."""
        # Initially hide composite properties group
        self.set_group_visibility("Composite Properties", False)
        
        # Check if material is already selected
        material_widget = self.field_widgets.get(self.MATERIAL_FIELD_URI)
        if material_widget and isinstance(material_widget, QComboBox):
            material_uri = material_widget.currentData()
            if material_uri:
                # Check material type and apply visibility
                is_composite = self.ontology_manager.is_instance_of_type(
                    material_uri, self.COMPOSITE_URI
                )
                self.set_group_visibility("Composite Properties", is_composite)
    
    def get_visible_fields(self) -> Dict[str, QWidget]:
        """Get currently visible fields."""
        visible = {}
        for uri, widget in self.field_widgets.items():
            if widget.isVisible():
                visible[uri] = widget
        return visible
    
    def get_hidden_groups(self) -> Set[str]:
        """Get list of currently hidden groups."""
        hidden = set()
        for name, group_box in self.group_boxes.items():
            if not group_box.isVisible():
                hidden.add(name)
        return hidden