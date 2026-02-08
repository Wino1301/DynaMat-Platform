from pathlib import Path
import os
import platformdirs
from .__version__ import __version__ as DYNAMAT_APP_VERSION


class Config:
    """Central configuration class"""

    APP_NAME = "dynamat"
    APP_AUTHOR = ""

    # Version
    VERSION = DYNAMAT_APP_VERSION

    # Project Root (D:\DynaMat-Platform)
    # Assumes config.py is at src/dynamat/config.py
    # Path(__file__).parent (src/dynamat)
    # Path(__file__).parent.parent (src)
    # Path(__file__).parent.parent.parent (D:\DynaMat-Platform)
    PROJECT_ROOT = Path(__file__).parent.parent.parent

    # Application Data Directory (e.g., D:\DynaMat-Platform\data) - for read-only app-specific data
    DATA_DIR = PROJECT_ROOT / "data"

    # Ontology Directory (e.g., src/dynamat/ontology) - part of the installed package
    ONTOLOGY_DIR = Path(__file__).parent / "ontology"
    TEMPLATE_DIR = ONTOLOGY_DIR / "templates"
    QUDT_CACHE_DIR = ONTOLOGY_DIR / "qudt" / "cache"

    # User-specific Data Directory (OS-dependent, e.g., C:\Users\User\AppData\Local\DynaMat Devs\dynamat)
    USER_DATA_ROOT = Path(platformdirs.user_data_dir(
        appname=APP_NAME,
        appauthor="",
        version=VERSION,
        ensure_exists=True  # Ensure this root directory exists
    ))
    # Create a 'data' subfolder within the platformdirs base for clarity
    USER_DATA_DIR = USER_DATA_ROOT / "data"

    # Specific user data subdirectories within the new USER_DATA_DIR
    SPECIMENS_DIR = USER_DATA_DIR / "specimens"
    USER_INDIVIDUALS_DIR = USER_DATA_DIR / "individuals"

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

    # Plotting settings
    PLOT_BACKEND = "matplotlib"  # Options: "plotly", "matplotlib"

    # Cache settings (for GUI forms, metadata, etc.)
    USE_FORM_CACHE = True  # Enable/disable form widget caching
    USE_METADATA_CACHE = True  # Enable/disable ontology metadata caching
    USE_SCHEMA_CACHE = True  # Enable/disable GUI schema caching

    @classmethod
    def get_config_dict(cls):
        """Return configuration as dictionary"""
        return {
            key: getattr(cls, key)
            for key in dir(cls)
            if not key.startswith('_') and not callable(getattr(cls, key))
            and not key in ['APP_NAME', 'APP_AUTHOR', 'PROJECT_ROOT', 'USER_DATA_ROOT'] # Exclude internal path vars
        }

    @classmethod
    def ensure_directories(cls):
        """Create necessary directories if they don't exist."""
        # Application-level data dirs
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
        cls.QUDT_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # User-specific data dirs (handled by platformdirs for USER_DATA_ROOT)
        cls.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.SPECIMENS_DIR.mkdir(parents=True, exist_ok=True)
        cls.USER_INDIVIDUALS_DIR.mkdir(parents=True, exist_ok=True)

# Create global config instance
config = Config()
