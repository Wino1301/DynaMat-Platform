import numpy as np
import pandas as pd
import os, io
from scripts.rdf_wrapper import RDFWrapper
from scripts.SHPB_RDFSignalFetch import RawExperimentDataHandler
from rdflib import Graph, Namespace, URIRef, Literal
from scipy.integrate import cumulative_trapezoid
import base64

class SeriesData:
    """
    A class to determine series data for Experiment Tests
    """   
  
    def __init__(self, ontology_path, experiment_graph_path):
        """
        Initialize the SignalExractor with the RDF graph.

        Args:
            ontology_path (str): Path to the RDF file.
        """
        self.ontology_path = ontology_path
        self.file_path = experiment_graph_path
        self.experiment = RDFWrapper(self.file_path)         
        self.handler = RawExperimentDataHandler(self.experiment)
        self.encoding = "base64Binary" 
        
        ##################################################################################
        #### Step 1: Unpack Variables
        ##################################################################################
        self.secondary_data_uri = self.experiment.get_instances_of_class("dynamat:SecondaryData")[0]
        self.series_data_class = self.experiment.DYNAMAT.SeriesData
        
        print("\n Fetching Extracted Signals from RDF")
        print("-----"*10)
        self.incident_extracted_pulse = self.handler.fetch_extracted_signals("dynamat:IncidentExtractedSignal")
        self.transmitted_extracted_pulse = self.handler.fetch_extracted_signals("dynamat:TransmittedExtractedSignal")
        self.reflected_extracted_pulse = self.handler.fetch_extracted_signals("dynamat:ReflectedExtractedSignal")
        self.time_extracted_pulse = self.handler.fetch_extracted_signals("dynamat:TimeExtractedSignal")

        #### PLace holder for temp signal handler
        if len(self.experiment.get_instances_of_class("dynamat:TemperatureSensorSignal")) > 0 :
            print("No process defined to handle temperature signals yet!.")            
        print("Extracted signals loaded!")

        # Extract Pulse Duration
        self.pulse_properties = self.experiment.get_objects(self.secondary_data_uri, "dynamat:hasPulseProperty")
        for prop in self.pulse_properties:
            if "Pulse_Duration" in prop:
                self.pulse_duration = float(self.experiment.get_objects(prop, "dynamat:hasValue")[0]) # ms
        
        # Extract Specimen Original Length and Cross Section
        self.specimen_data_uri = self.experiment.get_instances_of_class("dynamat:SHPBSpecimen")[0]
        self.specimen_dimensions = self.experiment.get_objects(self.specimen_data_uri, "dynamat:hasDimension")
        for prop in self.specimen_dimensions:
            if "OriginalLength" in prop:
                self.specimen_length = float(self.experiment.get_objects(prop, "dynamat:hasValue")[0]) # mm
            elif "OriginalCrossSectionalArea" in prop:
                self.specimen_cross = float(self.experiment.get_objects(prop, "dynamat:hasValue")[0]) # mm^2

        # Extract Bar Dimensions and Properties
        self.bar_data_uri = self.experiment.get_instances_of_class("dynamat:Bar")[0] # Incident Bar
        self.bar_dimensions = self.experiment.get_objects(self.bar_data_uri, "dynamat:hasDimension")
        self.bar_properties = self.experiment.get_objects(self.bar_data_uri, "dynamat:hasMechanicalProperty")
        
        for prop in self.bar_dimensions:
            if "OriginalCrossSectionalArea" in prop:
                self.bar_cross = float(self.experiment.get_objects(prop, "dynamat:hasValue")[0]) # mm^2
        for prop in self.bar_properties:
            if "Density" in prop:
                self.bar_density = float(self.experiment.get_objects(prop, "dynamat:hasValue")[0]) # kg/mm^3
            elif "ElasticModulus" in prop:
                self.bar_elastic_modulus = float(self.experiment.get_objects(prop, "dynamat:hasValue")[0]) # MPa
            elif "WaveSpeed" in prop:
                self.bar_wave_speed = float(self.experiment.get_objects(prop, "dynamat:hasValue")[0]) # ms


        ##################################################################################
        #### Step 2: Calculate Particle Velocity at Bar - Specimen Interfaces
        ##################################################################################
        
        self.particle_velocity_1 = self.bar_wave_speed * (self.incident_extracted_pulse.iloc[:,0] + 
                                                          self.reflected_extracted_pulse.iloc[:,0])   

        self.particle_velocity_2 = self.bar_wave_speed * (self.transmitted_extracted_pulse.iloc[:,0]) 

        print("\n Data Series 1: Bar / Specimen Particle Velocities")
        print("-----"*10)
        print(f"Incident - Specimen Particle Velocity was determined with a max value of {np.min(self.particle_velocity_1):.3f} mm/ms at {self.time_extracted_pulse.iloc[np.argmin(self.particle_velocity_1), 0]:.3f} ms")
        print(f"Transmitted - Specimen Particle Velocity was determined with a max value of {np.min(self.particle_velocity_2):.3f} mm/ms at {self.time_extracted_pulse.iloc[np.argmin(self.particle_velocity_2), 0]:.3f} ms")

        # Add Front Particle Velocity to RDF
        series_name_uri = self.experiment.DYNAMAT["ParticleVelocity_1_Front"]
        series_class_uri = self.experiment.DYNAMAT.ParticleVelocity    
        series_data = np.array(self.particle_velocity_1).astype(np.float32)

        self.add_series_data(series_name_uri, series_class_uri, series_data,
                             units=self.experiment.DYNAMAT.MeterPerSecond, legend_name="Front Surface",
                             description="Incident - Specimen Particle Velocity determined from pulse strains")

        # Add Back Particle Velocity to RDF
        series_name_uri = self.experiment.DYNAMAT["ParticleVelocity_2_Back"]
        series_class_uri = self.experiment.DYNAMAT.ParticleVelocity    
        series_data = np.array(self.particle_velocity_2).astype(np.float32)

        self.add_series_data(series_name_uri, series_class_uri, series_data,
                             units=self.experiment.DYNAMAT.MeterPerSecond, legend_name="Back Surface",
                             description="Transmitted - Specimen Particle Velocity determined from pulse strains")
            
        ##################################################################################
        #### Step 3: Calculate Average Engineering Strain Rate
        ##################################################################################        
        
        self.strain_rate_3W = (self.bar_wave_speed / self.specimen_length) * (self.incident_extracted_pulse.iloc[:,0] -self.reflected_extracted_pulse.iloc[:,0] - self.transmitted_extracted_pulse.iloc[:,0]) * 1000 # Converts from 1/ms to 1/s

        self.strain_rate_1W = ((2*self.bar_wave_speed*self.reflected_extracted_pulse.iloc[:,0]) / self.specimen_length) *1000

        print("\n Data Series 2: Engineering Strain Rate")
        print("-----"*10)
        print(f"Using the 1 Wave Analysis")
        print(f"Strain rate was determined with a max value of {np.max(self.strain_rate_1W):.3f} 1/ms at {self.time_extracted_pulse.iloc[np.argmax(self.strain_rate_1W),0]:.3f} ms")
        
        print(f"\n Using the 3 Wave Analysis")
        print(f"Strain rate was determined with a max value of {np.min(self.strain_rate_3W):.3f} 1/ms at {self.time_extracted_pulse.iloc[np.argmin(self.strain_rate_3W),0]:.3f} ms")

        # Add 1-Wave Strain Rate to RDF        
        series_name_uri = self.experiment.DYNAMAT["EngineeringStrainRate_1Wave"]
        series_class_uri = self.experiment.DYNAMAT.EngineeringStrainRate      
        series_data = np.array(self.strain_rate_1W).astype(np.float32)
        
        self.add_series_data(series_name_uri, series_class_uri, series_data,
                             units=self.experiment.DYNAMAT.Hertz, legend_name="Strain Rate 1W",
                             description="Engineering Strain Rate determined from 1-wave analysis" )

        # Add 3-Wave Strain Rate to RDF        
        series_name_uri = self.experiment.DYNAMAT["EngineeringStrainRate_3Wave"]
        series_class_uri = self.experiment.DYNAMAT.EngineeringStrainRate      
        series_data = np.array(self.strain_rate_3W).astype(np.float32)
        
        self.add_series_data(series_name_uri, series_class_uri, series_data,
                             units=self.experiment.DYNAMAT.Hertz, legend_name="Strain Rate 3W",
                             description="Engineering Strain Rate determined from 3-wave analysis" )
         
        ##################################################################################
        #### Step 4: Calculate Average Engineering Strain  
        ##################################################################################
        
        self.eng_strain_1w = ((2*self.bar_wave_speed) / self.specimen_length) * cumulative_trapezoid(self.reflected_extracted_pulse.iloc[:,0], self.time_extracted_pulse.iloc[:,0], initial= 0)
        
        self.eng_strain_3w = (self.bar_wave_speed / self.specimen_length) * cumulative_trapezoid((self.incident_extracted_pulse.iloc[:,0] - self.reflected_extracted_pulse.iloc[:,0] - self.transmitted_extracted_pulse.iloc[:,0]), self.time_extracted_pulse.iloc[:,0], initial= 0)
        
        print("\n Data Series 3: Engineering Strain")
        print("-----"*10)
        print(f"Using the 1 Wave Analysis")
        print(f"Engineering Strain was determined with a max value of {np.max(self.eng_strain_1w):.3f} mm/mm at {self.time_extracted_pulse.iloc[np.argmax(self.eng_strain_1w),0]:.3f} ms")
        print(f"\n Using the 3 Wave Analysis")
        print(f"Engineering Strain was determined with a max value of {np.min(self.eng_strain_3w):.3f} mm/mm at {self.time_extracted_pulse.iloc[np.argmin(self.eng_strain_3w),0]:.3f} ms")

        # Add Engineering Strain 1W
        series_name_uri = self.experiment.DYNAMAT["EngineeringStrain_1Wave"] #
        series_class_uri = self.experiment.DYNAMAT.EngineeringStrain   #
        series_data = np.array(self.eng_strain_1w).astype(np.float32) 

        self.add_series_data(series_name_uri, series_class_uri, series_data,
                             units=self.experiment.DYNAMAT.Unitless, legend_name="Eng Strain 1W",
                             description="Engineering Strain determined from 1-wave analysis" )

         # Add Engineering Strain 3W 
        series_name_uri = self.experiment.DYNAMAT["EngineeringStrain_3Wave"] #
        series_class_uri = self.experiment.DYNAMAT.EngineeringStrain   #
        series_data = np.array(self.eng_strain_3w).astype(np.float32) 

        self.add_series_data(series_name_uri, series_class_uri, series_data,
                             units=self.experiment.DYNAMAT.Unitless, legend_name="Eng Strain 3W",
                             description="Engineering Strain determined from 3-wave analysis" ) 
        
        ##################################################################################
        #### Step 5: Calculate True Strain
        ##################################################################################
        
        self.true_strain_1w = np.log(1 + self.eng_strain_1w)
        self.true_strain_3w = np.log(1 + self.eng_strain_3w)

        print("\n Data Series 4: True Strain")
        print("-----"*10)
        print(f"Using the 1 Wave Analysis")
        print(f"True Strain was determined with a max value of {np.max(self.true_strain_1w):.3f} mm/mm at {self.time_extracted_pulse.iloc[np.argmax(self.true_strain_1w),0]:.3f} ms")
        print(f"\n Using the 3 Wave Analysis")
        print(f"True Strain was determined with a max value of {np.min(self.true_strain_3w):.3f} mm/mm at {self.time_extracted_pulse.iloc[np.argmin(self.true_strain_3w),0]:.3f} ms")

        # Add True Strain 1W 
        series_name_uri = self.experiment.DYNAMAT["TrueStrain_1W"] 
        series_class_uri = self.experiment.DYNAMAT.TrueStrain   
        series_data = np.array(self.true_strain_1w).astype(np.float32) 

        self.add_series_data(series_name_uri, series_class_uri, series_data,
                             units=self.experiment.DYNAMAT.Unitless, legend_name="True Strain 1W",
                             description="True Strain determined from 1-wave analysis" ) 
        
        # Add True Strain 3W 
        series_name_uri = self.experiment.DYNAMAT["TrueStrain_3W"] 
        series_class_uri = self.experiment.DYNAMAT.TrueStrain   
        series_data = np.array(self.true_strain_3w).astype(np.float32) 

        self.add_series_data(series_name_uri, series_class_uri, series_data,
                             units=self.experiment.DYNAMAT.Unitless, legend_name="True Strain 3W",
                             description="True Strain determined from 3-wave analysis" )
        
        ##################################################################################
        #### Step 6: Calculate Interface Forces  
        ##################################################################################
        
        self.force_1w = self.bar_cross * (self.bar_elastic_modulus/1000) * (self.transmitted_extracted_pulse.iloc[:,0])
        self.force_2w = self.bar_cross * (self.bar_elastic_modulus/1000) * (self.incident_extracted_pulse.iloc[:,0] + self.reflected_extracted_pulse.iloc[:,0])        

        print("\n Data Series 5: Interface Forces")
        print("-----"*10)
        print(f"Using the 1 Wave Analysis")
        print(f"Incident - Specimen force was determined with a max value of {np.min(self.force_1w):.3f} mm/mm at {self.time_extracted_pulse.iloc[np.argmin(self.force_1w),0]:.3f} ms")
        print(f"\n Using the 2 Wave Analysis")
        print(f"Transmitted - Specimen force was determined with a max value of {np.min(self.force_2w):.3f} mm/mm at {self.time_extracted_pulse.iloc[np.argmin(self.force_2w),0]:.3f} ms")

        # Add 1-Wave Force to RDF        
        series_name_uri = self.experiment.DYNAMAT["Force_1Wave"]
        series_class_uri = self.experiment.DYNAMAT.SurfaceForce    
        series_data = np.array(self.force_1w).astype(np.float32)
        
        self.add_series_data(series_name_uri, series_class_uri, series_data,
                             units=self.experiment.DYNAMAT.KiloNewton, legend_name="Back Surface",
                             description="Back Surface Force determined from 1-wave analysis" )

        # Add 2-Wave Force to RDF        
        series_name_uri = self.experiment.DYNAMAT["Force_2Wave"]
        series_class_uri = self.experiment.DYNAMAT.SurfaceForce    
        series_data = np.array(self.force_2w).astype(np.float32)
        
        self.add_series_data(series_name_uri, series_class_uri, series_data,
                             units=self.experiment.DYNAMAT.KiloNewton, legend_name="Front Surface",
                             description="Front Surface Force determined from 2-wave analysis" )
           
        ##################################################################################
        #### Step 7: Calculate Engineering Stress at both Specimen Ends
        ##################################################################################
        
        self.eng_stress_1w = (self.bar_elastic_modulus / 1000) * (self.bar_cross  / self.specimen_cross) * (self.transmitted_extracted_pulse.iloc[:,0]) * 1000 # Converts all to MPa
        
        self.eng_stress_2w = (self.bar_elastic_modulus / 1000) * (self.bar_cross  / self.specimen_cross) * (self.incident_extracted_pulse.iloc[:,0] + self.reflected_extracted_pulse.iloc[:,0] ) * 1000 # Converts all to MPa
        
        print("\n Data Series 6: Engineering Stress")
        print("-----"*10)
        print(f"Using the 1 Wave Analysis")
        print(f"Engineering Stress at the Transmitted / Specimen interphase was determined with a max value of {np.min(self.eng_stress_1w):.3f} MPa at {self.time_extracted_pulse.iloc[np.argmin(self.eng_stress_1w),0]:.3f} ms")
        print(f"\n Using the 2 Wave Analysis")
        print(f"Engineering Stress at the Incident / Specimen interphase was determined with a max value of {np.min(self.eng_stress_2w):.3f} MPa at {self.time_extracted_pulse.iloc[np.argmin(self.eng_stress_2w),0]:.3f} ms")

        # Add Engineering Stress 1w
        series_name_uri = self.experiment.DYNAMAT["EngineeringStress_1w"] 
        series_class_uri = self.experiment.DYNAMAT.EngineeringStress   
        series_data = np.array(self.eng_stress_1w).astype(np.float32) 
        
        self.add_series_data(series_name_uri, series_class_uri, series_data,
                             units=self.experiment.DYNAMAT.Megapascal, legend_name="Back Surface",
                             description="Back Surface Engineering Stress determined from 1-wave analysis" )
        
        # Add Engineering Stress 2w
        series_name_uri = self.experiment.DYNAMAT["EngineeringStress_2w"] 
        series_class_uri = self.experiment.DYNAMAT.EngineeringStress   
        series_data = np.array(self.eng_stress_2w).astype(np.float32) 
        
        self.add_series_data(series_name_uri, series_class_uri, series_data,
                             units=self.experiment.DYNAMAT.Megapascal, legend_name="Front Surface",
                             description="Front Surface Engineering Stress determined from 2-wave analysis" )
        
        ##################################################################################
        #### Step 6: Calculate True Stress at both Specimen Ends
        ##################################################################################
        
        self.true_stress_1w = self.eng_stress_1w * (1 + self.eng_strain_1w)
        self.true_stress_2w = self.eng_stress_2w * (1 + self.eng_strain_3w)
        
        print("\n Data Series 7: True Stress")
        print("-----"*10)
        print(f"Using the 1 Wave Analysis")
        print(f"True Stress at the Transmitted / Specimen interphase was determined with a max value of {np.min(self.true_stress_1w):.3f} MPa at {self.time_extracted_pulse.iloc[np.argmin(self.true_stress_1w),0]:.3f} ms")
        print(f"Using the 2 Wave Analysis")
        print(f"True Stress at the Incident / Specimen interphase was determined with a max value of {np.min(self.true_stress_2w):.3f} MPa at {self.time_extracted_pulse.iloc[np.argmin(self.true_stress_2w),0]:.3f} ms")

        # Add Engineering Stress
        series_name_uri = self.experiment.DYNAMAT["TrueStress_1w"] #
        series_class_uri = self.experiment.DYNAMAT.TrueStress   #
        series_data = np.array(self.true_stress_1w).astype(np.float32) #
        
        self.add_series_data(series_name_uri, series_class_uri, series_data,
                             units=self.experiment.DYNAMAT.Megapascal, legend_name="Back Surface",
                             description="Back Surface True Stress determined from 1-wave analysis" )

         # Add Engineering Stress 2W
        series_name_uri = self.experiment.DYNAMAT["TrueStress_2w"] #
        series_class_uri = self.experiment.DYNAMAT.TrueStress   #
        series_data = np.array(self.true_stress_2w).astype(np.float32) #
        
        self.add_series_data(series_name_uri, series_class_uri, series_data,
                             units=self.experiment.DYNAMAT.Megapascal, legend_name="Front Surface",
                             description="Front Surface True Stress determined from 2-wave analysis" )        
        
        ##################################################################################
        #### Step 8: Calculate Pulse's True Strains
        ##################################################################################

        self.incident_true_strain = np.log(1 + self.incident_extracted_pulse.iloc[:,0])
        #print(f"True Incident Strain was determined with a max value of {np.min(self.incident_true_strain):.3f} mm/mm at {self.time_extracted_pulse.iloc[np.argmin(self.incident_true_strain),0]:.3f} ms")

        self.reflected_true_strain = np.log(1 + self.reflected_extracted_pulse.iloc[:,0])
        #print(f"True Reflected Strain was determined with a max value of {np.max(self.reflected_true_strain):.3f} mm/mm at {self.time_extracted_pulse.iloc[np.argmax(self.reflected_true_strain),0]:.3f} ms")

        self.transmitted_true_strain = np.log(1 + self.transmitted_extracted_pulse.iloc[:,0])
        #print(f"True Transmitted Strain was determined with a max value of {np.min(self.transmitted_true_strain):.3f} mm/mm at {self.time_extracted_pulse.iloc[np.argmin(self.transmitted_true_strain),0]:.3f} ms")
        
        ##################################################################################
        #### Step 9: Calculate Pulse's Strain Energies
        ##################################################################################
        
        self.incident_strain_energy = 0.5 * self.bar_cross * self.bar_wave_speed * self.bar_elastic_modulus * self.pulse_duration * (self.incident_true_strain**2)
        self.reflected_strain_energy = 0.5 * self.bar_cross * self.bar_wave_speed * self.bar_elastic_modulus * self.pulse_duration * (self.reflected_true_strain**2)
        self.transmitted_strain_energy = 0.5 * self.bar_cross * self.bar_wave_speed * self.bar_elastic_modulus * self.pulse_duration * (self.transmitted_true_strain**2)
        
        print("\n Data Series 8: Pulse Strain Energies")
        print("-----"*10)
        print(f"Incident Strain Energy was determined with a max value of {np.max(self.incident_strain_energy):.3f} mJ at {self.time_extracted_pulse.iloc[np.argmax(self.incident_strain_energy),0]:.3f} ms")
        print(f"Reflected Strain Energy was determined with a max value of {np.max(self.reflected_strain_energy):.3f} mJ at {self.time_extracted_pulse.iloc[np.argmax(self.reflected_strain_energy),0]:.3f} ms")
        print(f"Transmitted Strain Energy was determined with a max value of {np.max(self.transmitted_strain_energy):.3f} mJ at {self.time_extracted_pulse.iloc[np.argmax(self.transmitted_strain_energy),0]:.3f} ms")

        # Add Incident Strain Energy
        series_name_uri = self.experiment.DYNAMAT["Incident_StrainEnergy"] 
        series_class_uri = self.experiment.DYNAMAT.StrainEnergy   
        series_data = np.array(self.incident_strain_energy).astype(np.float32) 

        self.add_series_data(series_name_uri, series_class_uri, series_data,
                             units=self.experiment.DYNAMAT.Millijoule, legend_name="Incident",
                             description="Incident Pulse Strain Energy determined from true pulse strain" )
    
        # Add Transmitted Strain Energy
        series_name_uri = self.experiment.DYNAMAT["Transmitted_StrainEnergy"] 
        series_class_uri = self.experiment.DYNAMAT.StrainEnergy   
        series_data = np.array(self.transmitted_strain_energy).astype(np.float32) 

        self.add_series_data(series_name_uri, series_class_uri, series_data,
                             units=self.experiment.DYNAMAT.Millijoule, legend_name="Transmitted",
                             description="Transmitted Pulse Strain Energy determined from true pulse strain" )

        # Add Incident Strain Energy
        series_name_uri = self.experiment.DYNAMAT["Reflected_StrainEnergy"] 
        series_class_uri = self.experiment.DYNAMAT.StrainEnergy   
        series_data = np.array(self.reflected_strain_energy).astype(np.float32) 

        self.add_series_data(series_name_uri, series_class_uri, series_data,
                             units=self.experiment.DYNAMAT.Millijoule, legend_name="Reflected",
                             description="Reflected Pulse Strain Energy determined from true pulse strain" )
                        
        ##################################################################################
        #### Step 5: Calculate Absorbed Energy
        ##################################################################################
        
        self.delta_e_energy = 0.5 * self.bar_cross * self.bar_wave_speed * self.bar_elastic_modulus * self.pulse_duration * (self.incident_extracted_pulse.iloc[:,0] **2 - self.reflected_extracted_pulse.iloc[:,0]**2 - self.transmitted_extracted_pulse.iloc[:,0]**2) 

        self.delta_k_energy = 0.5 * 1000 * self.bar_cross * (self.bar_wave_speed**3) * self.bar_density * self.pulse_duration * (self.incident_extracted_pulse.iloc[:,0]**2 - self.reflected_extracted_pulse.iloc[:,0]**2 - self.transmitted_extracted_pulse.iloc[:,0]**2) 

        self.total_energy = self.delta_e_energy + self.delta_k_energy

        print("\n Data Series 9: Pulse Absorbed Energies")
        print("-----"*10)
        print(f"Spcimen Absorbed Elastic Strain Energy was determined with a max value of {np.max(self.delta_e_energy):.3f} mJ at {self.time_extracted_pulse.iloc[np.argmax(self.delta_e_energy),0]:.3f} ms")
        print(f"Spcimen Absorbed Kinetic Strain Energy was determined with a max value of {np.max(self.delta_k_energy):.3f} mJ at {self.time_extracted_pulse.iloc[np.argmax(self.delta_k_energy),0]:.3f} ms")        
        print(f"Total Spcimen Absorbed Strain Energy was determined with a max value of {np.max(self.total_energy):.3f} mJ at {self.time_extracted_pulse.iloc[np.argmax(self.total_energy),0]:.3f} ms")

        # Add Delta E absorbed energy
        series_name_uri = self.experiment.DYNAMAT["Delta_E"] #
        series_class_uri = self.experiment.DYNAMAT.AbsorbedEnergy   #
        series_data = np.array(self.delta_e_energy).astype(np.float32) 
        
        self.add_series_data(series_name_uri, series_class_uri, series_data,
                             units=self.experiment.DYNAMAT.Millijoule, legend_name="Elastic Energy",
                             description="Absorbed Elastic Energy determined from pulse strains" ) 
        
        # Add Delta K absorbed Energy
        series_name_uri = self.experiment.DYNAMAT["Delta_K"] 
        series_class_uri = self.experiment.DYNAMAT.AbsorbedEnergy   
        series_data = np.array(self.delta_k_energy).astype(np.float32) 
        
        self.add_series_data(series_name_uri, series_class_uri, series_data,
                             units=self.experiment.DYNAMAT.Millijoule, legend_name="Kinetic Energy",
                             description="Absorbed Kinetic Energy determined from pulse strains" )    
        
        # Add Total absorbed Energy
        series_name_uri = self.experiment.DYNAMAT["Total_Energy"]
        series_class_uri = self.experiment.DYNAMAT.AbsorbedEnergy   
        series_data = np.array(self.total_energy).astype(np.float32) 
        
        self.add_series_data(series_name_uri, series_class_uri, series_data,
                             units=self.experiment.DYNAMAT.Millijoule, legend_name="Total Energy",
                             description="Total Absorbed Energy determined from pulse strains" )
            
        print("Saving graph to file...")
        print(f"Graph contains: {self.experiment.len()} triples.")
        with open(self.file_path, "w") as f:
            f.write(self.experiment.serialize("turtle"))  

    ##################################################################################
    #### Class Helper Functions
    ##################################################################################            

    def add_series_data(self, series_name, series_class, data_array, units=None, legend_name=None, description=None):
        """
        Adds a time-series dataset to the RDF graph using base64 encoding.
    
        Parameters:
        - series_name: The URIRef string representing the series name.
        - series_class: The RDF class URIRef for the data series.
        - data_array: The NumPy array containing numerical data.
        - units: The unit URIRef (e.g., experiment.DYNAMAT.MeterPerSecond).
        - legend_name: A string describing the legend name.
        - description: A string describing the series data.
        """
        
        # Convert data to float32 and encode in base64
        series_data = np.array(data_array).astype(np.float32)
        data_size = len(series_data)
        
        if self.encoding == "base64Binary":
            series_encoded_data = base64.b64encode(series_data.tobytes()).decode("utf-8")
        else:
            raise ValueError("Unsupported encoding type. Currently only 'base64Binary' is supported.")
            
        # Add RDF triples
        self.experiment.set((URIRef(series_name), self.experiment.RDF.type, series_class))
        self.experiment.add((URIRef(series_name), self.experiment.RDF.type, self.experiment.DYNAMAT.SeriesData))
        
        if units:
            self.experiment.set((URIRef(series_name), self.experiment.DYNAMAT.hasUnits, units))
    
        self.experiment.set((URIRef(series_name), self.experiment.DYNAMAT.hasEncodedData,
                        Literal(series_encoded_data, datatype=self.experiment.XSD.base64Binary)))
        self.experiment.set((URIRef(series_name), self.experiment.DYNAMAT.hasEncoding,
                        Literal(self.encoding, datatype=self.experiment.XSD.string)))
        self.experiment.set((URIRef(series_name), self.experiment.DYNAMAT.hasSize,
                        Literal(data_size, datatype=self.experiment.XSD.int)))
        
        if legend_name:
            self.experiment.set((URIRef(series_name), self.experiment.DYNAMAT.hasLegendName,
                            Literal(legend_name, datatype=self.experiment.XSD.string)))
        
        if description:
            self.experiment.set((URIRef(series_name), self.experiment.DYNAMAT.hasDescription,
                            Literal(description, datatype=self.experiment.XSD.string)))
    
        # Link the series to the secondary data URI
        self.experiment.add((URIRef(self.secondary_data_uri), self.experiment.DYNAMAT.hasSeriesData, URIRef(series_name)))
    
        # Ensure the unit instance is added to the ontology
        if units:
            self.add_instance_data(units)
            
        print(f"Added series: {series_name.split('#')[-1]} with {data_size} data points.")

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
