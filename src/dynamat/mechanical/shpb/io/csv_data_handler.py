"""
CSV Data Handler for SHPB Raw Data

Handles validation and saving of pandas DataFrames containing SHPB raw signal data.
"""

import logging
from pathlib import Path
from typing import Dict, List
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class CSVDataHandler:
    """
    Handle and validate raw SHPB signal data from pandas DataFrame.

    This class validates that the DataFrame has the required structure
    (time, incident, transmitted columns) and provides methods to save
    the data as CSV with proper metadata.

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({
        ...     'time': [0.0, 0.001, 0.002],
        ...     'incident': [0.1, 0.2, 0.3],
        ...     'transmitted': [0.05, 0.1, 0.15]
        ... })
        >>> handler = CSVDataHandler(df)
        >>> handler.validate_structure()  # Raises ValueError if invalid
        >>> handler.save_to_csv(Path('output.csv'))
    """

    REQUIRED_COLUMNS = ['time', 'incident', 'transmitted']
    MIN_DATA_POINTS = 10

    def __init__(self, data: pd.DataFrame):
        """
        Initialize CSV data handler with DataFrame.

        Args:
            data: pandas DataFrame with SHPB raw signal data

        Example:
            >>> df = pd.DataFrame({'time': [...], 'incident': [...], 'transmitted': [...]})
            >>> handler = CSVDataHandler(df)
        """
        self.data = data
        logger.debug(f"CSVDataHandler initialized with DataFrame shape: {data.shape}")

    def validate_structure(self):
        """
        Validate DataFrame structure and data quality.

        Checks:
        - Required columns exist (time, incident, transmitted)
        - Data types are numeric
        - No NaN or Inf values
        - Time column is monotonically increasing
        - Minimum number of data points

        Raises:
            ValueError: If validation fails with detailed error message

        Example:
            >>> handler = CSVDataHandler(df)
            >>> handler.validate_structure()  # Raises ValueError if invalid
        """
        # Check required columns exist
        missing_cols = set(self.REQUIRED_COLUMNS) - set(self.data.columns)
        if missing_cols:
            raise ValueError(
                f"DataFrame missing required columns: {missing_cols}. "
                f"Required: {self.REQUIRED_COLUMNS}, "
                f"Found: {list(self.data.columns)}"
            )

        # Check for extra columns (warn but don't fail)
        extra_cols = set(self.data.columns) - set(self.REQUIRED_COLUMNS)
        if extra_cols:
            logger.warning(f"DataFrame contains extra columns (will be ignored): {extra_cols}")

        # Check minimum data points
        if len(self.data) < self.MIN_DATA_POINTS:
            raise ValueError(
                f"DataFrame has insufficient data points. "
                f"Minimum: {self.MIN_DATA_POINTS}, Found: {len(self.data)}"
            )

        # Check data types are numeric
        for col in self.REQUIRED_COLUMNS:
            if not pd.api.types.is_numeric_dtype(self.data[col]):
                raise ValueError(
                    f"Column '{col}' must be numeric, "
                    f"found type: {self.data[col].dtype}"
                )

        # Check for NaN values
        for col in self.REQUIRED_COLUMNS:
            nan_count = self.data[col].isna().sum()
            if nan_count > 0:
                raise ValueError(
                    f"Column '{col}' contains {nan_count} NaN values. "
                    f"All values must be valid numbers."
                )

        # Check for Inf values
        for col in self.REQUIRED_COLUMNS:
            inf_count = np.isinf(self.data[col]).sum()
            if inf_count > 0:
                raise ValueError(
                    f"Column '{col}' contains {inf_count} Inf values. "
                    f"All values must be finite."
                )

        # Check time column is monotonically increasing
        time_diff = self.data['time'].diff()[1:]  # Skip first NaN
        if (time_diff <= 0).any():
            raise ValueError(
                "Time column must be monotonically increasing. "
                "Found non-increasing values."
            )

        logger.info(
            f"DataFrame validation passed: {len(self.data)} data points, "
            f"columns: {list(self.data.columns)}"
        )

    def get_column_names(self) -> List[str]:
        """
        Get list of column names in the DataFrame.

        Returns:
            List of column names

        Example:
            >>> handler.get_column_names()
            ['time', 'incident', 'transmitted']
        """
        return list(self.data.columns)

    def get_data_point_count(self) -> int:
        """
        Get number of data points (rows) in DataFrame.

        Returns:
            Number of rows

        Example:
            >>> handler.get_data_point_count()
            10000
        """
        return len(self.data)

    def detect_sampling_rate(self) -> float:
        """
        Calculate sampling rate from time column.

        Uses mean time difference between consecutive samples.

        Returns:
            Sampling rate in Hz

        Example:
            >>> handler.detect_sampling_rate()
            1000000.0  # 1 MHz
        """
        time_diff = self.data['time'].diff()[1:]  # Skip first NaN
        mean_dt = time_diff.mean()

        if mean_dt <= 0:
            raise ValueError("Cannot calculate sampling rate: invalid time differences")

        sampling_rate = 1.0 / mean_dt
        logger.debug(f"Detected sampling rate: {sampling_rate:.2f} Hz (mean dt: {mean_dt:.6e} s)")

        return sampling_rate

    def save_to_csv(self, output_path: Path):
        """
        Save DataFrame to CSV file with proper encoding.

        Format:
        - UTF-8 encoding
        - Comma delimiter
        - Header row included
        - Float precision: 6 decimal places

        Args:
            output_path: Path where CSV will be saved

        Raises:
            IOError: If file cannot be written

        Example:
            >>> handler.save_to_csv(Path('data/raw_signals.csv'))
        """
        try:
            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Save with specific formatting
            self.data.to_csv(
                output_path,
                index=False,
                encoding='utf-8',
                float_format='%.6f'
            )

            file_size = output_path.stat().st_size
            logger.info(
                f"DataFrame saved to {output_path} "
                f"({len(self.data)} rows, {file_size} bytes)"
            )

        except Exception as e:
            logger.error(f"Failed to save CSV to {output_path}: {e}")
            raise IOError(f"Could not save CSV file: {e}") from e

    def get_file_metadata_for_saving(self) -> Dict[str, any]:
        """
        Get metadata dictionary for creating AnalysisFile instance.

        Returns metadata that will be used when creating the AnalysisFile
        RDF instance.

        Returns:
            Dict with file format metadata:
            - delimiter: ','
            - encoding: 'UTF-8'
            - has_header: True
            - skip_rows: 0
            - file_format: 'CSV'

        Example:
            >>> metadata = handler.get_file_metadata_for_saving()
            >>> metadata['delimiter']
            ','
        """
        return {
            'delimiter': ',',
            'encoding': 'UTF-8',
            'has_header': True,
            'skip_rows': 0,
            'file_format': 'CSV'
        }
