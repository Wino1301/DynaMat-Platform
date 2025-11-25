"""Global configuration for DynaMat Platform"""

from pathlib import Path
import os


class Config:
    """Central configuration class"""
    
    # Base paths
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR / "data"
    USER_DATA_DIR = BASE_DIR / "user_data"
    ONTOLOGY_DIR = BASE_DIR / "dynamat" / "ontology"
    TEMPLATE_DIR = ONTOLOGY_DIR / "templates"
    QUDT_CACHE_DIR = ONTOLOGY_DIR / "qudt" / "cache"

    # User data paths
    SPECIMENS_DIR = USER_DATA_DIR / "specimens"
    USER_INDIVIDUALS_DIR = USER_DATA_DIR / "individuals"

    # Ensure directories exist
    DATA_DIR.mkdir(exist_ok=True)
    USER_DATA_DIR.mkdir(exist_ok=True)
    SPECIMENS_DIR.mkdir(exist_ok=True)
    USER_INDIVIDUALS_DIR.mkdir(exist_ok=True)
    
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

    # Version
    VERSION = "2.0.0"

    # Cache settings
    USE_FORM_CACHE = False  # Enable/disable form widget caching
    USE_METADATA_CACHE = False  # Enable/disable ontology metadata caching
    USE_SCHEMA_CACHE = False  # Enable/disable GUI schema caching

    @classmethod
    def get_config_dict(cls):
        """Return configuration as dictionary"""
        return {
            key: getattr(cls, key)
            for key in dir(cls)
            if not key.startswith('_') and not callable(getattr(cls, key))
        }

    # Ensure directories exist
    @classmethod
    def ensure_directories(cls):
        """Create necessary directories if they don't exist."""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.SPECIMENS_DIR.mkdir(parents=True, exist_ok=True)
        cls.USER_INDIVIDUALS_DIR.mkdir(parents=True, exist_ok=True)
        cls.TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
        cls.QUDT_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Create global config instance
config = Config()
# Create directories on import
Config.ensure_directories()