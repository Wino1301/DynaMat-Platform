import pytest
import sys
import os
from pathlib import Path

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from dynamat.ontology import OntologyManager
from dynamat.ontology.qudt.qudt_manager import QUDTManager

@pytest.fixture(scope="session")
def ontology_manager():
    """
    Fixture to provide a loaded OntologyManager.
    Scope is 'session' to avoid reloading the ontology for every test.
    """
    # Use default ontology directory
    om = OntologyManager()
    return om

@pytest.fixture(scope="session")
def qudt_manager():
    """
    Fixture to provide a loaded QUDTManager.
    """
    qm = QUDTManager()
    qm.load()
    return qm
