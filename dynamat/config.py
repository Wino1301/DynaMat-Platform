"""Global configuration for DynaMat Platform"""

from pathlib import Path
import os


class Config:
    """Central configuration class"""
    
    # Base paths
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR / "data"
    ONTOLOGY_DIR = BASE_DIR / "dynamat" / "ontology"
    TEMPLATE_DIR = ONTOLOGY_DIR / "templates"
    
    # Ensure directories exist
    DATA_DIR.mkdir(exist_ok=True)
    
    # Ontology URIs
    ONTOLOGY_URI = "https://github.com/UTEP-Dynamic-Materials-Lab/ontology#"
    TEMPLATE_URI = "https://dynamat.utep.edu/templates/"
    SPECIMEN_URI = "https://dynamat.utep.edu/specimens/"
    
    # SHPB defaults
    DEFAULT_SAMPLING_RATE = 1e6  # Hz
    DEFAULT_WAVE_SPEED = 5000    # m/s
    
    # GUI settings
    WINDOW_TITLE = "DynaMat Platform"
    DEFAULT_THEME = "fusion"
    
    @classmethod
    def get_config_dict(cls):
        """Return configuration as dictionary"""
        return {
            key: getattr(cls, key)
            for key in dir(cls)
            if not key.startswith('_') and not callable(getattr(cls, key))
        }


# Create global config instance
config = Config()