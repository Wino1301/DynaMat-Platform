import pandas as pd
import numpy as np
import base64

class RawExperimentDataHandler:
    def __init__(self, experiment):
        self.experiment = experiment  # Assuming an RDF experiment object is passed
    
    def fetch_gauge_signals(self, gauge_sensor_class):
        """
        Retrieves all instances for a given class as a pandas DataFrame.
        
        Args:
            gauge_sensor_class (str): The class of gauge sensors to fetch signals for.
        
        Returns:
            pd.DataFrame: A DataFrame where each column represents a signal with the column name as the gauge sensor name.
        """
        # Initialize an empty DataFrame to store signals
        signals_df = pd.DataFrame()
    
        # Retrieve all sensor instances of the given class
        sensor_data_instances = self.experiment.get_instances_of_class(gauge_sensor_class)
    
        for sensor_name in sensor_data_instances:
            # Fetch relevant properties for the sensor
            signal_data = self.experiment.get_objects(sensor_name, "dynamat:hasEncodedData")[0]
            signal_encoding = self.experiment.get_objects(sensor_name, "dynamat:hasEncoding")[0]
            signal_size = int(self.experiment.get_objects(sensor_name, "dynamat:hasSize")[0])
            signal_units = self.experiment.get_objects(sensor_name, "dynamat:hasUnits")[0]
            signal_gauge = self.experiment.get_objects(sensor_name, "dynamat:hasStrainGauge")[0]
    
            try:
                if signal_encoding == "base64Binary":
                    # Decode the base64 string into bytes
                    signal_data_decoded = base64.b64decode(signal_data)
                    
                    # Convert the bytes to a NumPy array of float32
                    signal_data_decoded = np.frombuffer(signal_data_decoded, dtype=np.float32) 
                    
                    # Ensure the size matches the expected size
                    if len(signal_data_decoded) != signal_size:
                        raise ValueError(f"Decoded data size ({len(signal_data_decoded)}) does not match expected size ({signal_size}).")
                    
                    if signal_units == "https://github.com/UTEP-Dynamic-Materials-Lab/SHPB_Toolkit/tree/main/ontology#Volts": 
                        try:
                            gauge_properties = self.fetch_gauge_properties(signal_gauge)
                            gauge_cal_resistance = gauge_properties["SG_CalibrationResistance"]
                            gauge_cal_voltage = gauge_properties["SG_CalibrationVoltage"]
                            gauge_factor = gauge_properties["SG_GaugeFactor"]
                            gauge_resistance = gauge_properties["SG_Resistance"]
                        
                            signal_data_decoded = self.voltage_to_strain(
                                signal_data_decoded, 
                                gauge_resistance, 
                                gauge_factor, 
                                gauge_cal_voltage, 
                                gauge_cal_resistance
                            )
                        except KeyError as e:
                            print(f"Missing key in gauge properties: {e}. Ensure all required keys (SG_CalibrationResistance, SG_CalibrationVoltage, SG_GaugeFactor, SG_Resistance) are present.")
                        except Exception as e:
                            print(f"Error converting voltage signal for {sensor_name}: {e}. Please verify the data and property names.")
                   
                    # Add the signal to the DataFrame with the sensor name as the column header
                    signals_df[sensor_name] = signal_data_decoded
                
            except Exception as e:
                print(f"Error processing {sensor_name}: {e}")
    
        return signals_df  
        
    def fetch_sensor_signals(self, sensor_class):
        """
        Retrieves all instances for a given sensor class as a pandas DataFrame.
        
        Args:
            sensor_class (str): The class of sensors to fetch signals for.
        
        Returns:
            pd.DataFrame: A DataFrame where each column represents a signal with the column name as the sensor name.
        """
        # Initialize an empty DataFrame to store signals
        signals_df = pd.DataFrame()
    
        # Retrieve all sensor instances of the given class
        sensor_data_instances = self.experiment.get_instances_of_class(sensor_class)
    
        for sensor_name in sensor_data_instances:
            # Fetch relevant properties for the sensor
            signal_data = self.experiment.get_objects(sensor_name, "dynamat:hasEncodedData")[0]
            signal_encoding = self.experiment.get_objects(sensor_name, "dynamat:hasEncoding")[0]
            signal_size = int(self.experiment.get_objects(sensor_name, "dynamat:hasSize")[0])
            signal_units = self.experiment.get_objects(sensor_name, "dynamat:hasUnits")[0]
                
            try:
                if signal_encoding == "base64Binary":
                    # Decode the base64 string into bytes
                    signal_data_decoded = base64.b64decode(signal_data)
                    
                    # Convert the bytes to a NumPy array of float32
                    signal_data_decoded = np.frombuffer(signal_data_decoded, dtype=np.float32) 
                    
                    # Ensure the size matches the expected size
                    if len(signal_data_decoded) != signal_size:
                        raise ValueError(f"Decoded data size ({len(signal_data_decoded)}) does not match expected size ({signal_size}).")
                    
                    # Check for valid units
                    valid_units = {
                        "https://github.com/UTEP-Dynamic-Materials-Lab/SHPB_Toolkit/tree/main/ontology#Millisecond",
                        "https://github.com/UTEP-Dynamic-Materials-Lab/SHPB_Toolkit/tree/main/ontology#DegreesCelsius"
                    }
                    
                    if signal_units not in valid_units:
                        raise ValueError(f"Incorrect unit specified for {sensor_name}: {signal_units}")
                        
                    # Add the signal to the DataFrame with the sensor name as the column header
                    signals_df[sensor_name] = signal_data_decoded
                
            except Exception as e:
                print(f"Error processing {sensor_name}: {e}")
    
        return signals_df

    def fetch_gauge_properties(self, gauge_uri):
        """
        Retrieves values from the gauge instance definition dynamically based on the graph content.
    
        Args:
            gauge_uri (str): The URI of the gauge instance.
    
        Returns:
            dict: A dictionary mapping property names (e.g., "CalibrationVoltage") to their values.
        """
        try:
            # SPARQL query to fetch all strain gauge properties
            query = f"""
            PREFIX : <https://github.com/UTEP-Dynamic-Materials-Lab/SHPB_Toolkit/tree/main/ontology#>
            SELECT ?property ?value WHERE {{
                <{gauge_uri}> :hasStrainGaugeProperty ?property .
                ?property :hasValue ?value .
            }}
            """
            results = self.experiment.query(query)
            
            # Organize properties into a dictionary
            gauge_properties = {}
            for row in results:
                property_uri = str(row.property)
                property_value = float(row.value)  # Assuming numerical values for properties
                # Extract the property name from the URI (e.g., "CalibrationVoltage" from "dynamat:CalibrationVoltage")
                property_name = property_uri.split("#")[-1]
                gauge_properties[property_name] = property_value
    
            return gauge_properties
    
        except Exception as e:
            print(f"Error fetching gauge properties for {gauge_uri}: {e}")
            return {}

    def voltage_to_strain(self, voltage_array, gauge_res, gauge_factor, cal_voltage, cal_resistance):
        """
        Converts a measured voltage from a strain gauge into strain using the provided parameters.
            
        Parameters:
        ----------
        voltage : float
            The measured voltage from the strain gauge (in volts).
        gauge_res : float
            The resistance of the strain gauge (in ohms).
        gauge_factor : float
            The gauge factor or sensitivity coefficient of the strain gauge (unitless).
        cal_voltage : float
            The calibration voltage applied to the strain gauge circuit (in volts).
        cal_resistance : float
            The resistance of the calibration resistor in the strain gauge circuit (in ohms).
                
        Returns:
        -------
        float
            The calculated strain value (unitless, as strain is dimensionless).
            
        """    
        conversion_factor = gauge_res / (cal_voltage * gauge_factor * (gauge_res + cal_resistance))
        
        strain =  voltage_array * conversion_factor
        return strain 

    def fetch_extracted_signals(self, extracted_signal_class):
        """
        Retrieves all instances for a given class as a pandas DataFrame.
        
        Args:
            extracted_signal_class (str): The class of gauge sensors to fetch signals for.
        
        Returns:
            pd.DataFrame: A DataFrame where each column represents a signal with the column name as the gauge sensor name.
        """
        
        # Initialize an empty DataFrame to store signals
        signals_df = pd.DataFrame()
    
        # Retrieve all sensor instances of the given class
        sensor_data_instances = self.experiment.get_instances_of_class(extracted_signal_class)
    
        for sensor_name in sensor_data_instances:
            # Fetch relevant properties for the sensor
            signal_data = self.experiment.get_objects(sensor_name, "dynamat:hasEncodedData")[0]
            signal_encoding = self.experiment.get_objects(sensor_name, "dynamat:hasEncoding")[0]
            signal_size = int(self.experiment.get_objects(sensor_name, "dynamat:hasSize")[0])
            signal_units = self.experiment.get_objects(sensor_name, "dynamat:hasUnits")[0]
    
            try:
                if signal_encoding == "base64Binary":
                    # Decode the base64 string into bytes
                    signal_data_decoded = base64.b64decode(signal_data)
                    
                    # Convert the bytes to a NumPy array of float32
                    signal_data_decoded = np.frombuffer(signal_data_decoded, dtype=np.float32) 
                    
                    # Ensure the size matches the expected size
                    if len(signal_data_decoded) != signal_size:
                        raise ValueError(f"Decoded data size ({len(signal_data_decoded)}) does not match expected size ({signal_size}).")
                   
                    # Add the signal to the DataFrame with the sensor name as the column header
                    signals_df[sensor_name] = signal_data_decoded
                    print(f"Extracted signal for {sensor_name.split('#')[-1]} loaded...")
                
            except Exception as e:
                print(f"Error processing {sensor_name}: {e}")
    
        return signals_df