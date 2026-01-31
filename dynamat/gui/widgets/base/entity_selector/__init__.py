"""
DynaMat Platform - Entity Selector Module
Reusable components for selecting ontology entity instances

This module provides a composable entity selection system that can be
used both as an embedded widget and as a modal dialog.

Components:
    EntitySelectorConfig: Configuration dataclass for the widget
    SelectionMode: Enum for single/multiple selection
    FilterPanel: Composable filter dropdown panel
    DetailsPanel: Composable details display panel
    EntitySelectorWidget: Core embeddable widget
    EntitySelectorDialog: Modal dialog wrapper

Example - Embedded Widget:
    from dynamat.gui.widgets.base.entity_selector import (
        EntitySelectorConfig, EntitySelectorWidget
    )

    config = EntitySelectorConfig(
        class_uri="https://dynamat.utep.edu/ontology#Specimen",
        display_properties=["dyn:hasSpecimenID", "dyn:hasMaterial"],
        filter_properties=["dyn:hasMaterial"],
        show_details_panel=True
    )

    selector = EntitySelectorWidget(config, query_builder=qb)
    selector.entity_selected.connect(self._on_entity_selected)
    layout.addWidget(selector)

Example - Modal Dialog:
    from dynamat.gui.widgets.base.entity_selector import (
        EntitySelectorConfig, EntitySelectorDialog
    )

    config = EntitySelectorConfig(
        class_uri="https://dynamat.utep.edu/ontology#Specimen",
        display_properties=["dyn:hasSpecimenID", "dyn:hasMaterial"],
    )

    data = EntitySelectorDialog.select_entity(
        config=config,
        query_builder=qb,
        title="Load Specimen",
        parent=self
    )
    if data:
        self.load_specimen(data)
"""

from .entity_selector_config import EntitySelectorConfig, SelectionMode
from .filter_panel import FilterPanel
from .details_panel import DetailsPanel
from .entity_selector_widget import EntitySelectorWidget
from .entity_selector_dialog import EntitySelectorDialog

__all__ = [
    'EntitySelectorConfig',
    'SelectionMode',
    'FilterPanel',
    'DetailsPanel',
    'EntitySelectorWidget',
    'EntitySelectorDialog',
]
