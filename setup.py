### `setup.py`
```python
from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

# Read version
exec(open('dynamat/__version__.py').read())

setup(
    name='dynamat-platform',
    version=__version__,
    author='Your Name',
    author_email='your.email@utep.edu',
    description='Ontology-based platform for dynamic materials testing',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/yourusername/DynaMat-Platform',
    packages=find_packages(),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Physics',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    python_requires='>=3.9',
    install_requires=[
        'numpy>=1.21.0',
        'scipy>=1.7.0',
        'matplotlib>=3.4.0',
        'pandas>=1.3.0',
        'rdflib>=6.0.0',
        'PyQt6>=6.2.0',
        'pyqtgraph>=0.12.0',
    ],
    extras_require={
        'dev': [
            'pytest>=6.0',
            'pytest-cov',
            'pytest-qt',
            'black',
            'flake8',
            'mypy',
        ],
        'ml': [
            'torch>=2.0.0',
            'scikit-learn>=1.0.0',
        ],
        'imaging': [
            'opencv-python>=4.5.0',
            'scikit-image>=0.18.0',
            'Pillow>=8.0.0',
        ],
    },
    entry_points={
        'console_scripts': [
            'dynamat-gui=dynamat.gui.app:main',
            'dynamat-shpb=dynamat.shpb.cli:main',
        ],
    },
    include_package_data=True,
    package_data={
        'dynamat': ['ontology/core/*.ttl', 'ontology/shapes/*.ttl'],
    },
)