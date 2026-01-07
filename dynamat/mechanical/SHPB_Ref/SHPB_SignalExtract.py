import numpy as np
import pandas as pd
import os, io
from scripts.rdf_wrapper import RDFWrapper
from scripts.SHPB_RDFSignalFetch import RawExperimentDataHandler
from scripts.SHPB_DataReduction import PulseDataReduction
from rdflib import Graph, Namespace, URIRef, Literal
import base64

class SignalExtractor:
    """
    A class to perform pulse signal extraction from the experiment graph
    """   
  
    def __init__(self, ontology_path, experiment_graph_path):
        """
        Initialize the SignalExractor with the RDF graph.

        Args:
            ontology_path (str): Path to the RDF file.
        """
        print("Starting Signal Extraction Process")
        self.ontology_path = ontology_path
        self.file_path = experiment_graph_path
        self.experiment = RDFWrapper(self.file_path) 
        self.handler = RawExperimentDataHandler(self.experiment)
        self.calibration_csv = os.path.join(os.getcwd(),"config/Bar_Wave_Speed.csv") # Wave Speed Calibration CSV File.

        self.testing_conditions_uri = self.experiment.get_instances_of_class("dynamat:TestingConditions")[0]
        self.test_type = self.experiment.get_objects(self.testing_conditions_uri, "dynamat:hasTestType")[0].split("#")[-1]
        self.test_mode = self.experiment.get_objects(self.testing_conditions_uri, "dynamat:hasTestMode")[0].split("#")[-1]
        
        ##################################################################################
        #### Step 1: Fetch Sensor Signals, and variables to perfrom preliminary analysis
        #### This analysis part is common to all valid test conditions entries.
        ##################################################################################
        
        self.incident_sensor_signals = self.handler.fetch_gauge_signals("dynamat:IncidentSensorSignal") # unitless 
        self.transmitted_sensor_signals = self.handler.fetch_gauge_signals("dynamat:TransmittedSensorSignal") # unitless
        self.time_sensor_signals = self.handler.fetch_sensor_signals("dynamat:TimeSensorSignal") # ms 
        
        print("\n Loaded Sensor Signals")
        print("-----"*10)
        print(f"Incident Sensor Signals Loaded: {self.incident_sensor_signals.shape[1]}")
        print(f"Transmitted Sensor Signals Loaded: {self.transmitted_sensor_signals.shape[1]}")
        print(f"Time Sensor Signals Loaded: {self.time_sensor_signals.shape[1]}")

        if len(self.experiment.get_instances_of_class("dynamat:TemperatureSensorSignal")) > 0 :
            self.temperature_sensor_signals = handler.fetch_sensor_signals("dynamat:TemperatureSensorSignal") # Degrees C
            print(f"Temperature Sensor Signals Loaded: {self.temperature_sensor_signals.shape[1]}") 
       
        ###########################################################################################
        #### Step 2: Determine Loading Duration, Stress and Strain Amplitude and Stress Wave Length
        ###########################################################################################
        
        # Retrive striker bar lenght 
        self.striker_bar_uri = self.experiment.get_instances_of_class("dynamat:StrikerBar")[0]        
        self.striker_bar_material = self.experiment.get_objects(self.striker_bar_uri, "dynamat:hasMaterial")[0].split("#")[-1]
        self.striker_bar_dimensions = self.experiment.get_objects(self.striker_bar_uri, "dynamat:hasDimension")
        self.striker_bar_properties = self.experiment.get_objects(self.striker_bar_uri, "dynamat:hasMechanicalProperty")
        
        for prop in self.striker_bar_dimensions:
            if "OriginalLength" in prop:
                self.striker_length = float(self.experiment.get_objects(prop, "dynamat:hasValue")[0]) # mm
            elif "Velocity" in prop:
                self.striker_velocity = float(self.experiment.get_objects(prop, "dynamat:hasValue")[0]) # m/s
            elif "Pressure" in prop:
                self.striker_pressure = float(self.experiment.get_objects(prop, "dynamat:hasValue")[0]) # MPa
            elif "OriginalCrossSectionalArea" in prop:
                self.bar_cross_section = float(self.experiment.get_objects(prop, "dynamat:hasValue")[0]) # mm^2
                self.bar_radius = np.sqrt(self.bar_cross_section / np.pi)
                
        for prop in self.striker_bar_properties:
            if "Density" in prop:
                self.bar_density = float(self.experiment.get_objects(prop, "dynamat:hasValue")[0]) # kg/mm3
            elif "Poissons" in prop:
                self.bar_poissons = float(self.experiment.get_objects(prop, "dynamat:hasValue")[0]) # unitless
            elif "ElasticModulus" in prop:
                self.bar_elastic_modulus = float(self.experiment.get_objects(prop, "dynamat:hasValue")[0]) # MPa
            elif "WaveSpeed" in prop:
                self.bar_wave_speed = float(self.experiment.get_objects(prop, "dynamat:hasValue")[0]) # MPa

        print("\n Loaded Striker Bar Conditions")
        print("-----"*10)
        print(f"Striker Material: {self.striker_bar_material}")
        print(f"Striekr Bar Length: {self.striker_length:.3f} mm")
        print(f"Striker Bar Initial Velocity: {self.striker_velocity:.3f} m/s or mm/ms")
        print(f"Striker Bar Initial Pressure: {self.striker_pressure:.3f} MPa")

        print("\n Loaded Bar Properties")
        print("-----"*10)
        print(f"Bar Cross Section: {self.bar_cross_section:.3f} mm^2")
        print(f"Bar Radius: {self.bar_radius:.3f} mm")
        print(f"Bar Density: {self.bar_density:.3e} kg/mm^3")
        print(f"Bar Poisson's Ratio: {self.bar_poissons:.3f}")
        print(f"Bar Elastic Modulus: {self.bar_elastic_modulus:.3f} MPa")
        print(f"Calibrated Bar Wave Speed: {self.bar_wave_speed:.3f} m/s or mm/ms")

        self.incident_bar_uri = self.experiment.get_instances_of_class("dynamat:IncidentBar")[0]
        self.transmitted_bar_uri = self.experiment.get_instances_of_class("dynamat:IncidentBar")[0]
        
        self.incident_SG_distance = self.fetch_bar_gauge_distance(self.incident_bar_uri)
        self.transmitted_SG_distance = self.fetch_bar_gauge_distance(self.transmitted_bar_uri)

        print("\n Strain Gauge Distances")
        print("-----"*10)
        print(f"Incident Strain Gauge Distance: {self.incident_SG_distance:.3f} mm")
        print(f"Transmitted Strain Gauge Distance: {self.transmitted_SG_distance:.3f} mm")

        ###########################################################################################
        #### Step 2: Determine Loading Duration, Delta_t and Pulse Data Points
        ###########################################################################################

        self.delta_t = np.mean(np.diff(self.time_sensor_signals.iloc[:,0]))   
        self.pulse_duration = (2*self.striker_length) / self.bar_wave_speed        
        self.pulse_data_points = int(self.pulse_duration / self.delta_t) 
        self.pulse_length = 2 * self.striker_length
        self.pulse_stress = (1/2) * self.bar_density * self.bar_wave_speed * self.striker_velocity * 1000
        self.pulse_strain = (1/2) * (self.striker_velocity / self.bar_wave_speed) 

        print("\n Pulse Properties")
        print("-----"*10)             
        print(f"Pulse Duration from Calibrated Bar Wave Speed: {self.pulse_duration:.3f} ms")        
        print(f"Pulse Data Points from Calibrated Bar Wave Speed: {self.pulse_data_points} points")
        print(f"Average Delta T: {self.delta_t:.3e} ms")   

        print(f"Pulse Length: {self.pulse_length:.3f} mm")
        print(f"Pulse Stress: {self.pulse_stress:.3f} MPa")
        print(f"Pulse Strain: {self.pulse_strain:.3e} mm/mm")
        
        ###########################################################################################
        #### Step 4: Extract Pulse Signals from Sensor Signal
        ###########################################################################################

        if (
            self.incident_sensor_signals.shape[1] == 1
            and self.transmitted_sensor_signals.shape[1] == 1
            and self.time_sensor_signals.shape[1] == 1
        ):
            
            data_reduction = PulseDataReduction(self.incident_sensor_signals.iloc[:,0], self.transmitted_sensor_signals.iloc[:,0],
                                                       self.time_sensor_signals.iloc[:,0], self.pulse_data_points, self.delta_t,
                                                       self.pulse_duration, self.bar_wave_speed, self.bar_radius, self.bar_poissons, 
                                                       self.incident_SG_distance, self.transmitted_SG_distance, self.test_type)

            self.incident_corrected = data_reduction.incident_corrected
            self.transmitted_corrected = data_reduction.transmitted_corrected
            self.time_corrected = data_reduction.time_corrected
            print("\n Extracted Pulses")
            print("--------"*10)
            print(f"Extracted Time Pulse with {len(self.time_corrected)} points.")
            print(f"Extracted Incident Pulse with {len(self.incident_corrected)} points.")
            print(f"Extracted Transmitted Pulse with {len(self.transmitted_corrected)} points.")

            if self.test_type == "SpecimenTest":
                self.reflected_corrected = data_reduction.reflected_corrected
                print(f"Extracted Reflected Pulse with {len(self.reflected_corrected)} points.")
                
        else:
            raise ValueError("Current pulse extraction logic only works for 1 Sensor Signal of Each Type, please check code, or add new logic.")

        ###########################################################################################
        #### Step 5: Determine Pulse Speed
        ###########################################################################################

        print("\n Pulse Speed")
        print("--------"*10)

        if (
            self.incident_sensor_signals.shape[1] == 1
            and self.transmitted_sensor_signals.shape[1] == 1
            and self.time_sensor_signals.shape[1] == 1
        ):

            # Extract Pulse Starting Points
            incident_start = data_reduction.incident_start
            transmitted_start = data_reduction.transmitted_start
    
            if self.test_type == "SpecimenTest":
                specimen_data_uri = self.experiment.get_instances_of_class("dynamat:SHPBSpecimen")[0]
                specimen_dimensions = self.experiment.get_objects(specimen_data_uri, "dynamat:hasDimension")
                for prop in specimen_dimensions:
                    if "OriginalLength" in prop:
                        self.specimen_length = float(self.experiment.get_objects(prop, "dynamat:hasValue")[0]) # mm

                self.pulse_speed = (self.incident_SG_distance + self.transmitted_SG_distance + self.specimen_length) / ((transmitted_start - incident_start ) * self.delta_t) 
                print(f"Calculated Pulse Speed: {self.pulse_speed:.3f} mm/ms or m/s")
                
            elif self.test_type == "PulseTest":
                self.pulse_speed = (self.incident_SG_distance + self.transmitted_SG_distance) / ((transmitted_start - incident_start ) * self.delta_t)
                self.add_calibration_wave_speed()
                print(f"Calculated Pulse Speed: {self.pulse_speed:.3f} mm/ms or m/s")
                print(f"Wave Speed Difference from Bar Reference: {((self.bar_wave_speed - self.pulse_speed) / self.pulse_speed)* 100 :.3f} % ")    
                
        else:
            raise ValueError("Current Experiment Pulse Speed logic only works for 1 Sensor Signal of Each Type, please check code, or add new logic.")        

        ###########################################################################################
        #### Step 6: Save Secondary Data to RDF
        ###########################################################################################
        self.secondary_data_uri = str(self.experiment.DYNAMAT["Experiment_Secondary_Data"])

        # Add Pulse Duration, Length, Speed, and Stress / Strain Amplitudes
        pulse_duration_uri = str(self.experiment.DYNAMAT["Pulse_Duration"])
        self.experiment.set((URIRef(pulse_duration_uri), self.experiment.RDF.type, self.experiment.DYNAMAT.PulseProperties))
        self.experiment.set((URIRef(pulse_duration_uri), self.experiment.RDF.type, self.experiment.DYNAMAT.PulseDuration))
        self.experiment.set((URIRef(pulse_duration_uri), self.experiment.DYNAMAT.hasUnits, self.experiment.DYNAMAT.Millisecond))
        self.experiment.set((URIRef(pulse_duration_uri), self.experiment.DYNAMAT.hasValue,
                             Literal(self.pulse_duration, datatype = self.experiment.XSD.float )))
        self.experiment.set((URIRef(pulse_duration_uri), self.experiment.DYNAMAT.hasDescription, 
                             Literal("Test wave pulse duration", datatype = self.experiment.XSD.string )))
        self.experiment.add((URIRef(self.secondary_data_uri), self.experiment.DYNAMAT.hasPulseProperty, URIRef(pulse_duration_uri)))

        pulse_length_uri = str(self.experiment.DYNAMAT["Pulse_Length"])
        self.experiment.set((URIRef(pulse_length_uri), self.experiment.RDF.type, self.experiment.DYNAMAT.PulseProperties))
        self.experiment.set((URIRef(pulse_length_uri), self.experiment.RDF.type, self.experiment.DYNAMAT.PulseLength))
        self.experiment.set((URIRef(pulse_length_uri), self.experiment.DYNAMAT.hasUnits, self.experiment.DYNAMAT.Millimeter))
        self.experiment.set((URIRef(pulse_length_uri), self.experiment.DYNAMAT.hasValue,
                             Literal(self.pulse_length, datatype = self.experiment.XSD.float )))
        self.experiment.set((URIRef(pulse_length_uri), self.experiment.DYNAMAT.hasDescription, 
                             Literal("Test wave pulse length", datatype = self.experiment.XSD.string )))
        self.experiment.add((URIRef(self.secondary_data_uri), self.experiment.DYNAMAT.hasPulseProperty, URIRef(pulse_length_uri)))

        pulse_speed_uri = str(self.experiment.DYNAMAT["Pulse_Speed"])
        self.experiment.set((URIRef(pulse_speed_uri), self.experiment.RDF.type, self.experiment.DYNAMAT.PulseProperties))
        self.experiment.set((URIRef(pulse_speed_uri), self.experiment.RDF.type, self.experiment.DYNAMAT.PulseSpeed))
        self.experiment.set((URIRef(pulse_speed_uri), self.experiment.DYNAMAT.hasUnits, self.experiment.DYNAMAT.MeterPerSecond))
        self.experiment.set((URIRef(pulse_speed_uri), self.experiment.DYNAMAT.hasValue,
                             Literal(self.pulse_speed, datatype = self.experiment.XSD.float )))
        self.experiment.set((URIRef(pulse_speed_uri), self.experiment.DYNAMAT.hasDescription, 
                             Literal("Test wave pulse speed", datatype = self.experiment.XSD.string )))
        self.experiment.add((URIRef(self.secondary_data_uri), self.experiment.DYNAMAT.hasPulseProperty, URIRef(pulse_speed_uri)))

        stress_pulse_uri = str(self.experiment.DYNAMAT["Pulse_Stress_Amplitude"])
        self.experiment.set((URIRef(stress_pulse_uri), self.experiment.RDF.type, self.experiment.DYNAMAT.PulseProperties))
        self.experiment.set((URIRef(stress_pulse_uri), self.experiment.RDF.type, self.experiment.DYNAMAT.PulseStressAmplitude))
        self.experiment.set((URIRef(stress_pulse_uri), self.experiment.DYNAMAT.hasUnits, self.experiment.DYNAMAT.Megapascal))
        self.experiment.set((URIRef(stress_pulse_uri), self.experiment.DYNAMAT.hasValue,
                             Literal(self.pulse_stress, datatype = self.experiment.XSD.float )))
        self.experiment.set((URIRef(stress_pulse_uri), self.experiment.DYNAMAT.hasDescription, 
                             Literal("Test pulse stress amplitude", datatype = self.experiment.XSD.string )))
        self.experiment.add((URIRef(self.secondary_data_uri), self.experiment.DYNAMAT.hasPulseProperty, 
                             URIRef(stress_pulse_uri)))

        strain_pulse_uri = str(self.experiment.DYNAMAT["Pulse_Strain_Amplitude"])
        self.experiment.set((URIRef(strain_pulse_uri), self.experiment.RDF.type, self.experiment.DYNAMAT.PulseProperties))
        self.experiment.set((URIRef(strain_pulse_uri), self.experiment.RDF.type, self.experiment.DYNAMAT.PulseStrainAmplitude))
        self.experiment.set((URIRef(strain_pulse_uri), self.experiment.DYNAMAT.hasUnits, self.experiment.DYNAMAT.Unitless))
        self.experiment.set((URIRef(strain_pulse_uri), self.experiment.DYNAMAT.hasValue,
                             Literal(self.pulse_strain, datatype = self.experiment.XSD.float )))
        self.experiment.set((URIRef(strain_pulse_uri), self.experiment.DYNAMAT.hasDescription, 
                             Literal("Test pulse strain amplitude", datatype = self.experiment.XSD.string )))
        self.experiment.add((URIRef(self.secondary_data_uri), self.experiment.DYNAMAT.hasPulseProperty, 
                             URIRef(strain_pulse_uri)))

        # Save Incident and Reflected Extracted Signals         
        self.incident_sensor_signals_names = self.experiment.get_instances_of_class("dynamat:IncidentSensorSignal")
        if self.incident_sensor_signals.shape[1] == 1:
            for idx, name in enumerate(self.incident_sensor_signals_names): 
                incident_name_uri = name.replace("Sensor", "Extracted") # Extracted Sensor URI
                reflected_name_uri = incident_name_uri.replace("Incident", "Reflected") # Extracted Sensor URI
                extracted_signal_class = self.experiment.DYNAMAT.ExtractedSignal
                incident_signal_class = self.experiment.DYNAMAT.IncidentExtractedSignal
                reflected_signal_class = self.experiment.DYNAMAT.ReflectedExtractedSignal   
    
                incident_data = np.array(self.incident_corrected).astype(np.float32)
                data_size = len(incident_data) 
                encoding = "base64Binary"  
    
                if encoding == "base64Binary":
                    incident_encoded_data = base64.b64encode(incident_data.tobytes()).decode("utf-8")
                else:
                    raise ValueError("Unsupported encoding type. Currently only 'base64' is supported.")
                
                # Add Incident Extracted Signal
                self.experiment.set((URIRef(incident_name_uri), self.experiment.RDF.type, extracted_signal_class))
                self.experiment.set((URIRef(incident_name_uri), self.experiment.RDF.type, incident_signal_class))
                self.experiment.set((URIRef(incident_name_uri), self.experiment.DYNAMAT.hasUnits, self.experiment.DYNAMAT.Unitless))
                self.experiment.set((URIRef(incident_name_uri), self.experiment.DYNAMAT.hasEncodedData,
                                     Literal(incident_encoded_data, datatype = self.experiment.XSD.base64Binary)))
                self.experiment.set((URIRef(incident_name_uri), self.experiment.DYNAMAT.hasEncoding,
                                     Literal(encoding, datatype = self.experiment.XSD.string)))
                self.experiment.set((URIRef(incident_name_uri), self.experiment.DYNAMAT.hasSize,
                                     Literal(data_size, datatype = self.experiment.XSD.int)))
                self.experiment.set((URIRef(incident_name_uri), self.experiment.DYNAMAT.hasLegendName,
                                     Literal("Incident", datatype = self.experiment.XSD.string)))
                self.experiment.set((URIRef(incident_name_uri), self.experiment.DYNAMAT.hasDescription,
                                     Literal("Extracted Incident Signal from SG", datatype = self.experiment.XSD.string)))                
                self.experiment.add((URIRef(self.secondary_data_uri), self.experiment.DYNAMAT.hasExtractedSignal,
                                     URIRef(incident_name_uri)))
                                    
                # Add Reflected Extracted Signal
                if self.test_type == "SpecimenTest":
                    reflected_data = np.array(self.reflected_corrected).astype(np.float32)                
                    if encoding == "base64Binary":
                        reflected_encoded_data = base64.b64encode(reflected_data.tobytes()).decode("utf-8")
                    else:
                        raise ValueError("Unsupported encoding type. Currently only 'base64' is supported.")   
                        
                    self.experiment.set((URIRef(reflected_name_uri), self.experiment.RDF.type, extracted_signal_class))
                    self.experiment.set((URIRef(reflected_name_uri), self.experiment.RDF.type, reflected_signal_class))
                    self.experiment.set((URIRef(reflected_name_uri), self.experiment.DYNAMAT.hasUnits, self.experiment.DYNAMAT.Unitless))
                    self.experiment.set((URIRef(reflected_name_uri), self.experiment.DYNAMAT.hasEncodedData,
                                         Literal(reflected_encoded_data, datatype = self.experiment.XSD.base64Binary)))
                    self.experiment.set((URIRef(reflected_name_uri), self.experiment.DYNAMAT.hasEncoding,
                                         Literal(encoding, datatype = self.experiment.XSD.string)))
                    self.experiment.set((URIRef(reflected_name_uri), self.experiment.DYNAMAT.hasSize,
                                         Literal(data_size, datatype = self.experiment.XSD.int)))
                    self.experiment.set((URIRef(reflected_name_uri), self.experiment.DYNAMAT.hasLegendName,
                                         Literal("Reflected", datatype = self.experiment.XSD.string)))
                    self.experiment.set((URIRef(reflected_name_uri), self.experiment.DYNAMAT.hasDescription,
                                         Literal("Extracted Reflected Signal from SG", datatype = self.experiment.XSD.string)))
                    self.experiment.add((URIRef(self.secondary_data_uri), self.experiment.DYNAMAT.hasExtractedSignal,
                                         URIRef(reflected_name_uri)))
        else: 
            raise ValueError(f"Logic not defined for the amount of {self.incident_extracted_signals.shape[1]} Extracted Incident/Refelcted Sensor Signals")

        # Add Extracted Transmitted Data
        self.transmitted_sensor_signals_names = self.experiment.get_instances_of_class("dynamat:TransmittedSensorSignal")
        if self.transmitted_sensor_signals.shape[1] == 1:
            for idx, name in enumerate(self.transmitted_sensor_signals_names): 
                transmitted_name_uri = name.replace("Sensor", "Extracted") # Extracted Sensor URI
                extracted_signal_class = self.experiment.DYNAMAT.ExtractedSignal
                transmitted_signal_class = self.experiment.DYNAMAT.TransmittedExtractedSignal   
    
                transmitted_data = np.array(self.transmitted_corrected).astype(np.float32)
                data_size = len(transmitted_data) 
                encoding = "base64Binary"  
    
                if encoding == "base64Binary":
                    transmitted_encoded_data = base64.b64encode(transmitted_data.tobytes()).decode("utf-8")
                else:
                    raise ValueError("Unsupported encoding type. Currently only 'base64' is supported.")
                
                # Add transmitted Extracted Signal
                self.experiment.set((URIRef(transmitted_name_uri), self.experiment.RDF.type, extracted_signal_class))
                self.experiment.set((URIRef(transmitted_name_uri), self.experiment.RDF.type, transmitted_signal_class))
                self.experiment.set((URIRef(transmitted_name_uri), self.experiment.DYNAMAT.hasUnits, self.experiment.DYNAMAT.Unitless))
                self.experiment.set((URIRef(transmitted_name_uri), self.experiment.DYNAMAT.hasEncodedData,
                                     Literal(transmitted_encoded_data, datatype = self.experiment.XSD.base64Binary)))
                self.experiment.set((URIRef(transmitted_name_uri), self.experiment.DYNAMAT.hasEncoding,
                                     Literal(encoding, datatype =  self.experiment.XSD.string)))
                self.experiment.set((URIRef(transmitted_name_uri), self.experiment.DYNAMAT.hasSize,
                                     Literal(data_size, datatype = self.experiment.XSD.int)))
                self.experiment.set((URIRef(transmitted_name_uri), self.experiment.DYNAMAT.hasLegendName,
                                     Literal("Transmitted", datatype = self.experiment.XSD.string)))
                self.experiment.set((URIRef(transmitted_name_uri), self.experiment.DYNAMAT.hasDescription,
                                     Literal("Extracted Transmitted Signal from SG", datatype = self.experiment.XSD.string)))               
                self.experiment.add((URIRef(self.secondary_data_uri), self.experiment.DYNAMAT.hasExtractedSignal,
                                     URIRef(transmitted_name_uri)))
        else: 
            raise ValueError(f"Logic not defined for the amount of {self.transmitted_extracted_signals.shape[1]} Extracted Transmitted Sensor Signals")

        # Add Extracted Time Data
        self.time_sensor_signals_name = self.experiment.get_instances_of_class("dynamat:TimeSensorSignal")[0]        
        time_name_uri = self.time_sensor_signals_name.replace("Sensor", "Extracted") # Extracted Sensor URI
        extracted_signal_class = self.experiment.DYNAMAT.ExtractedSignal
        time_signal_class = self.experiment.DYNAMAT.TimeExtractedSignal   
    
        time_data = np.array(self.time_corrected).astype(np.float32)
        data_size = len(time_data) 
        encoding = "base64Binary"  
    
        if encoding == "base64Binary":
            time_encoded_data = base64.b64encode(time_data.tobytes()).decode("utf-8")
        else:
            raise ValueError("Unsupported encoding type. Currently only 'base64' is supported.")
                
        # Add time Extracted Signal
        self.experiment.set((URIRef(time_name_uri), self.experiment.RDF.type, extracted_signal_class))
        self.experiment.set((URIRef(time_name_uri), self.experiment.RDF.type, time_signal_class))
        self.experiment.set((URIRef(time_name_uri), self.experiment.DYNAMAT.hasUnits, self.experiment.DYNAMAT.Millisecond))
        self.experiment.set((URIRef(time_name_uri), self.experiment.DYNAMAT.hasEncodedData,
                                    Literal(time_encoded_data, datatype = self.experiment.XSD.base64Binary)))
        self.experiment.set((URIRef(time_name_uri), self.experiment.DYNAMAT.hasEncoding,
                                    Literal(encoding, datatype =  self.experiment.XSD.string)))
        self.experiment.set((URIRef(time_name_uri), self.experiment.DYNAMAT.hasSize,
                                    Literal(data_size, datatype = self.experiment.XSD.int)))
        self.experiment.set((URIRef(time_name_uri), self.experiment.DYNAMAT.hasLegendName,
                                    Literal("Time", datatype = self.experiment.XSD.string)))
        self.experiment.set((URIRef(time_name_uri), self.experiment.DYNAMAT.hasDescription,
                                    Literal("Extracted Time Signal from SG", datatype = self.experiment.XSD.string)))               
        self.experiment.add((URIRef(self.secondary_data_uri), self.experiment.DYNAMAT.hasExtractedSignal,
                                    URIRef(time_name_uri)))
  
        # Add Temperatyre Extracted Signal
        if len(self.experiment.get_instances_of_class("dynamat:TemperatureSensorSignal")) > 0 :
            print("No Temperature Extracted Signal Process Defined.") # Future Update Note!  
        
        print("Saving graph to file...")
        print(f"Graph contains: {self.experiment.len()} triples.")
        with open(self.file_path, "w") as f:
            f.write(self.experiment.serialize("turtle"))           

    def fetch_bar_gauge_distance(self, bar_instance_uri):
        try:    
            # Fetch dimensions for the bar
            bar_sg_uris = self.experiment.get_objects(bar_instance_uri, "dynamat:hasStrainGauge")
            if not bar_sg_uris:
                raise ValueError(f"No Strain Gauge Entries found for bar instance: {bar_instance_uri}.")

            if len(bar_sg_uris) > 1: # Add logic to multy signal here...
                print(f"Note, more than one SG for {bar_instance_uri} found. Current logic designed only for 1 SG - Sensor Signal")
                    
            sg_dimensions_uris = self.experiment.get_objects(bar_sg_uris[0], "dynamat:hasDimension")
            if not sg_dimensions_uris:
                raise ValueError(f"No Strain Gauge dimensions found for bar instance {bar_sg_uris}.")
            
            for dimension in sg_dimensions_uris:
                if "Distance" in dimension:
                    # Fetch and convert the value
                    sg_gauge_distance = self.experiment.get_objects(dimension, "dynamat:hasValue")
                    if not sg_gauge_distance:
                        raise ValueError(f"No value found for dimension {dimension}.")
                    sg_gauge_distance = float(sg_gauge_distance[0])
                    return sg_gauge_distance                    

        except ValueError as e:
            print(f"ValueError encountered: {e}")
        except KeyError as e:
            print(f"KeyError encountered: {e}")
        except IndexError as e:
            print(f"IndexError encountered: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")   

    def add_calibration_wave_speed(self):
        """
        Add Calibration Wave Speed Result from Pulse Tests to the current config table
        """
        # Define column headers
        headers = [
            "Test Name", "Striker Length", "Striker Velocity", "Striker Pressure", 
            "Wave Speed", "Striker Material", "Bar Density", "Bar Poisson's", 
            "Bar Elastic Modulus", "Bar Cross Section", "Bar Radius", 
            "Incident SG Distance", "Transmitted SG Distance", "Test Mode"
        ]
        
        # Check if the file exists, otherwise create a new DataFrame
        if os.path.exists(self.calibration_csv):
            df = pd.read_csv(self.calibration_csv)
        else:
            df = pd.DataFrame(columns=headers)

        metadata_uri = self.experiment.get_instances_of_class("dynamat:Metadata")[0]
        test_name = self.experiment.get_objects(metadata_uri, "dynamat:hasTestName")[0].split("#")[-1]        
        
        # Define new data as a dictionary (example values, modify as needed)
        new_data = {
            "Test Name": str(test_name),
            "Striker Length": self.striker_length,
            "Striker Velocity": self.striker_velocity,
            "Striker Pressure": self.striker_pressure,
            "Wave Speed": self.pulse_speed,
            "Striker Material": self.striker_bar_material,
            "Bar Density": self.bar_density,
            "Bar Poisson's": self.bar_poissons,
            "Bar Elastic Modulus": self.bar_elastic_modulus,
            "Bar Cross Section": self.bar_cross_section,
            "Bar Radius": self.bar_radius,
            "Incident SG Distance": self.incident_SG_distance,
            "Transmitted SG Distance": self.transmitted_SG_distance,
            "Test Mode": self.test_mode
        }
        
        # Append the new data
        df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
        
        # Save the updated DataFrame back to CSV
        df.to_csv(self.calibration_csv, index=False)   
        print(f"Adding Calibration Data from test: {test_name}")
        print(f"Calibration Data successfully saved to {self.calibration_csv}")

        return        
            
    def add_instance_data(self, instance):
        """
        Recursively fetch and add all data properties for a given instance in the ontology.
    
        Parameters:
        - instance (str): The URI of the instance to fetch properties for.
        """
        try:
            # Load the ontology
            ontology = Graph()
            ontology.parse(self.ontology_path, format="turtle")
            namespace = Namespace("https://github.com/UTEP-Dynamic-Materials-Lab/SHPB_Toolkit/tree/main/ontology#")
            
            # Define the query
            query = f"""
               PREFIX : <https://github.com/UTEP-Dynamic-Materials-Lab/SHPB_Toolkit/tree/main/ontology#>
               PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
               SELECT ?property ?value ?className WHERE {{
                   <{instance}> ?property ?value .
                   OPTIONAL {{ <{instance}> rdf:type ?className . }}
               }}
            """
            
            # Execute the query
            results = ontology.query(query)
            
            # Add the results to the graph
            if results:
                for row in results:
                    property_uri = URIRef(row.property)
                    value = str(row.value)
                    if row.className:
                        class_uri = URIRef(row.className)
                        self.experiment.add((URIRef(instance), self.experiment.RDF.type, class_uri))
                        
                    self.experiment.add((URIRef(instance), URIRef(property_uri), Literal(value, datatype=self.experiment.XSD.string)))
            else:
                print(f"No properties found for instance: {instance}")
    
        except Exception as e:
            print(f"Error executing query: {e}")