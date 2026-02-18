"""
State-to-Instances Converter for SHPB Analysis

Converts a form-data-driven SHPBAnalysisState directly to InstanceWriter
tuples for RDF/TTL export. Replaces the SHPBTestMetadata + FormDataConverter
pipeline with a simpler, direct conversion from analysis state.

Each form-data dict in the state (equipment_form_data, detection_form_data,
alignment_form_data, etc.) is already in property_uri -> value format,
making it directly usable by InstanceWriter.
"""

import logging
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

import numpy as np

from .series_config import SERIES_METADATA, get_windowed_series_metadata
from .rdf_helpers import apply_type_conversion_to_dict

logger = logging.getLogger(__name__)

DYN_NS = "https://dynamat.utep.edu/ontology#"


class StateToInstancesConverter:
    """Converts form-data-driven SHPBAnalysisState to InstanceWriter tuples.

    All metadata is read directly from form-data dicts stored on the state.
    Processing objects (detection params, alignment params, etc.) are already
    in the right format. Equipment form data becomes the main test instance.

    Example:
        >>> converter = StateToInstancesConverter()
        >>> instances = converter.build_all_instances(state, raw_df)
        >>> writer.write_multi_instance_file(instances, output_path)
    """

    def build_all_instances(
        self,
        state,
        raw_df,
        processed_results: Optional[Dict[str, np.ndarray]] = None
    ) -> List[Tuple[Dict[str, Any], str, str]]:
        """Build all RDF instances from analysis state.

        Args:
            state: SHPBAnalysisState with form-data dicts populated
            raw_df: DataFrame with columns 'time', 'incident', 'transmitted'
            processed_results: Optional dict from StressStrainCalculator.calculate()

        Returns:
            List of (form_data, class_uri, instance_id) tuples for InstanceWriter
        """
        instances = []
        test_id = state.test_id
        test_id_clean = test_id.replace('-', '_')

        # 1. Raw AnalysisFile
        if state.raw_file_metadata:
            file_form = apply_type_conversion_to_dict(dict(state.raw_file_metadata))
            file_form[f'{DYN_NS}hasCreatedDate'] = datetime.now().strftime('%Y-%m-%d')
            instances.append((file_form, 'dyn:AnalysisFile', f'{test_id_clean}_raw_csv'))

        # 2. Raw DataSeries (time, incident, transmitted)
        raw_series_uris = {}
        data_point_count = len(raw_df)
        for column_name in ['time', 'incident', 'transmitted']:
            if column_name not in raw_df.columns:
                continue
            series_meta = SERIES_METADATA.get(column_name, {})
            form_data = apply_type_conversion_to_dict({
                'rdf:type': 'dyn:DataSeries',
                'dyn:hasDataFile': f'dyn:{test_id_clean}_raw_csv',
                'dyn:hasColumnName': column_name,
                'dyn:hasColumnIndex': raw_df.columns.get_loc(column_name),
                'dyn:hasLegendName': series_meta.get('legend_name', column_name),
                'dyn:hasSeriesType': series_meta.get('series_type'),
                'dyn:hasDataPointCount': data_point_count,
                'dyn:hasSeriesUnit': series_meta.get('unit'),
                'dyn:hasQuantityKind': series_meta.get('quantity_kind'),
            })
            instance_id = f'{test_id_clean}_{column_name}'
            instances.append((form_data, series_meta.get('class_uri', 'dyn:RawSignal'), instance_id))
            raw_series_uris[column_name] = f'dyn:{instance_id}'

        # 3. Windowed DataSeries
        windowed_series_uris = {}
        segment_points = state.get_segmentation_param('hasSegmentPoints')
        if segment_points:
            windowed_metadata = get_windowed_series_metadata()
            for series_name, series_meta in windowed_metadata.items():
                raw_source = series_meta.get('raw_source')
                if not raw_source or raw_source not in raw_series_uris:
                    continue
                form_data = apply_type_conversion_to_dict({
                    'rdf:type': 'dyn:DataSeries',
                    'dyn:hasDataFile': f'dyn:{test_id_clean}_processed_csv',
                    'dyn:hasLegendName': series_meta.get('legend_name'),
                    'dyn:hasSeriesType': series_meta.get('series_type'),
                    'dyn:hasDataPointCount': segment_points,
                    'dyn:hasProcessingMethod': 'Pulse windowing and segmentation',
                    'dyn:derivedFrom': raw_series_uris[raw_source],
                    'dyn:hasSeriesUnit': series_meta.get('unit'),
                    'dyn:hasQuantityKind': series_meta.get('quantity_kind'),
                })
                instance_id = f'{test_id_clean}_{series_name}'
                instances.append((form_data, 'dyn:ProcessedData', instance_id))
                windowed_series_uris[series_name] = f'dyn:{instance_id}'

        # 4. Detection params (3x from state.detection_form_data)
        for pulse_type, form in state.detection_form_data.items():
            if form:
                instances.append((
                    apply_type_conversion_to_dict(dict(form)),
                    'dyn:PulseDetectionParams',
                    f'{test_id_clean}_{pulse_type}_detect'
                ))

        # 5. Segmentation params
        if state.segmentation_form_data:
            instances.append((
                apply_type_conversion_to_dict(dict(state.segmentation_form_data)),
                'dyn:SegmentationParams',
                f'{test_id_clean}_segmentation'
            ))

        # 6. Alignment params
        if state.alignment_form_data:
            instances.append((
                apply_type_conversion_to_dict(dict(state.alignment_form_data)),
                'dyn:AlignmentParams',
                f'{test_id_clean}_alignment'
            ))

        # 7. Equilibrium metrics
        if state.equilibrium_form_data:
            instances.append((
                apply_type_conversion_to_dict(dict(state.equilibrium_form_data)),
                'dyn:EquilibriumMetrics',
                f'{test_id_clean}_equilibrium'
            ))

        # 8. Tukey alpha is stored directly on SHPBCompression (no sub-instance)

        # 9. Processed AnalysisFile + DataSeries (if results provided)
        if processed_results is not None:
            # Processed file instance
            processed_file_form = apply_type_conversion_to_dict({
                'dyn:hasFileFormat': 'csv',
                'dyn:hasDataPointCount': len(next(iter(processed_results.values()))),
                'dyn:hasColumnCount': len(processed_results),
                'dyn:hasCreatedDate': datetime.now().strftime('%Y-%m-%d'),
            })
            instances.append((processed_file_form, 'dyn:AnalysisFile', f'{test_id_clean}_processed_csv'))

            # Processed DataSeries
            for column_name, data in processed_results.items():
                if column_name in ('time', 'incident', 'transmitted', 'reflected'):
                    continue
                series_meta = SERIES_METADATA.get(column_name, {})
                if not series_meta:
                    continue

                form_data = apply_type_conversion_to_dict({
                    'rdf:type': 'dyn:DataSeries',
                    'dyn:hasDataFile': f'dyn:{test_id_clean}_processed_csv',
                    'dyn:hasColumnName': column_name,
                    'dyn:hasLegendName': series_meta.get('legend_name'),
                    'dyn:hasSeriesType': series_meta.get('series_type'),
                    'dyn:hasDataPointCount': len(data),
                    'dyn:hasProcessingMethod': 'SHPB stress-strain calculation',
                    'dyn:hasSeriesUnit': series_meta.get('unit'),
                    'dyn:hasQuantityKind': series_meta.get('quantity_kind'),
                    'dyn:hasAnalysisMethod': series_meta.get('analysis_method'),
                })
                instance_id = f'{test_id_clean}_{column_name}'
                instances.append((form_data, series_meta.get('class_uri', 'dyn:ProcessedData'), instance_id))

        # 10. Main SHPBCompression test instance
        test_form = self._build_test_instance(state, instances, test_id_clean)
        instances.append((test_form, 'dyn:SHPBCompression', test_id_clean))

        logger.info(f"Built {len(instances)} instances from state for test {test_id}")
        return instances

    def _build_test_instance(
        self,
        state,
        all_instances: List[Tuple],
        test_id_clean: str
    ) -> Dict[str, Any]:
        """Build the main SHPBCompression test instance form data.

        Merges equipment form data with links to sub-instances and export metadata.
        """
        # Start with equipment form data (contains bar URIs, test conditions, etc.)
        form = dict(state.equipment_form_data or {})

        # Add links to processing objects
        if state.alignment_form_data:
            form[f'{DYN_NS}hasAlignmentParams'] = f'dyn:{test_id_clean}_alignment'
        if state.equilibrium_form_data:
            form[f'{DYN_NS}hasEquilibriumMetrics'] = f'dyn:{test_id_clean}_equilibrium'

        # Add all DataSeries links
        series_uris = []
        for (_, cls, inst_id) in all_instances:
            if cls in ('dyn:RawSignal', 'dyn:ProcessedData'):
                series_uris.append(f'dyn:{inst_id}')
        if series_uris:
            form[f'{DYN_NS}hasDataSeries'] = series_uris

        # Add detection params links
        detect_uris = [f'dyn:{inst_id}' for (_, cls, inst_id) in all_instances
                       if cls == 'dyn:PulseDetectionParams']
        if detect_uris:
            form[f'{DYN_NS}hasPulseDetectionParams'] = detect_uris

        # Add export metadata (validity, test type)
        if state.export_form_data:
            form.update(state.export_form_data)

        # Add analysis timestamp
        form[f'{DYN_NS}hasAnalysisTimestamp'] = datetime.now().isoformat()

        return apply_type_conversion_to_dict(form)
