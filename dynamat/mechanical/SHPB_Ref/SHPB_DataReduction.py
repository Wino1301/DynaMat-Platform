import numpy as np
import pandas as pd
from scipy.optimize import fsolve
from scipy.interpolate import CubicSpline
import pywt

class PulseDataReduction:
    def __init__(self, incident_strain_signal, transmitted_strain_signal, time_sensor_signal, pulse_data_points, delta_t,
                 pulse_duration, bar_wave_speed, bar_radius, bar_poissons, incident_SG_distance, transmitted_SG_distance, test_type):

        print("\n Starting Data Reduction Process")
        print("-----"*10)
        # Needed Variables for Analysis
        self.incident_strain_signal = incident_strain_signal
        self.transmitted_strain_signal = transmitted_strain_signal
        self.time_sensor_signal = time_sensor_signal
        self.pulse_data_points = pulse_data_points
        self.pulse_duration = pulse_duration
        self.delta_t = delta_t
        self.test_type = test_type
        self.bar_wave_speed = bar_wave_speed
        self.bar_radius = bar_radius
        self.bar_poissons = bar_poissons
        self.incident_SG_distance = incident_SG_distance
        self.transmitted_SG_distance = transmitted_SG_distance

        ###########################################################################################
        #### Step 1: Find Approximate Windows
        ###########################################################################################

        wavelet = 'gaus1'
        scales = np.arange(1, 300, 2)  # Multi-scale analysis
        
        # Compute CWT
        print("\n Computing Wavelet Transform Coefficients ...")
        incident_coeffs, _ = pywt.cwt(self.incident_strain_signal, scales, wavelet)
        transmitted_coeffs, _ = pywt.cwt(self.transmitted_strain_signal, scales, wavelet)
        
        # Find strong edges by taking the absolute max of wavelet coefficients
        self.incident_edges = np.where(np.abs(incident_coeffs).max(axis=0) > np.percentile(np.abs(incident_coeffs), 98.5))[0]
        self.transmitted_edges = np.where(np.abs(transmitted_coeffs).max(axis=0) > np.percentile(np.abs(transmitted_coeffs), 98.5))[0]

        ###########################################################################################
        #### Step 2: Extract Pulse Windows From Approximation
        ###########################################################################################
        print("\n Extracting Pulse Windows From Approximations ...")
        self.process_pulses(initial_pp_extra=0.15, max_pp_extra=2.0)

        # self.incident_start and self.transmitted_start are expected to be extracted to determine pulse wave speed. 

        ###########################################################################################
        #### Step 3: Apply Wave Dispersion Correction using Fourier Transform
        ###########################################################################################
        print("\n Correcting Wave Dispersion using Fourier Transform ...")
        omega0 = (2 * np.pi) / self.pulse_duration
        N = (self.subset_points // 1024) * 1024
        
        incident_corrected, time_corrected = self.wave_dispersion_correction(self.time_extracted, self.incident_extracted,
                                                                             self.bar_wave_speed, self.bar_radius, self.bar_poissons,
                                                                             omega0, self.delta_t, self.pulse_duration, N,
                                                                             np.abs(self.incident_SG_distance))
        
        transmitted_corrected, _ = self.wave_dispersion_correction(self.time_extracted, self.transmitted_extracted, self.bar_wave_speed,
                                                                   self.bar_radius, self.bar_poissons, omega0, self.delta_t,
                                                                   self.pulse_duration, N, -np.abs(self.transmitted_SG_distance))
        
        if test_type == "SpecimenTest":
            reflected_corrected, _ = self.wave_dispersion_correction(self.time_extracted, self.reflected_extracted, self.bar_wave_speed,
                                                                     self.bar_radius, self.bar_poissons, omega0, self.delta_t,
                                                                     self.pulse_duration, N, np.abs(self.incident_SG_distance))

        ###########################################################################################
        #### Step 4: Apply Wave Dispersion Correction using Fourier Transform
        ###########################################################################################
        print("\n Fitting Pulse Windows ...")
        
        if test_type == "SpecimenTest":
            fitted_pulses = self.fit_pulse_windows([incident_corrected, reflected_corrected, transmitted_corrected], 5e-4, [True,False,True])
            self.incident_corrected = np.array(fitted_pulses[0]) # Expected to be extracted
            self.reflected_corrected = np.array(fitted_pulses[1]) # Expected to be extracted
            self.transmitted_corrected = np.array(fitted_pulses[2]) # Expected to be extracted
        else:
            fitted_pulses = self.fit_pulse_windows([incident_corrected, transmitted_corrected], 5e-4, [True,True])
            self.incident_corrected = np.array(fitted_pulses[0]) # Expected to be extracted
            self.transmitted_corrected = np.array(fitted_pulses[1]) # Expected to be extracted
        
        self.time_corrected = time_corrected[len(time_corrected) - len(self.incident_corrected):] # Expected to be extracted

        print("\n Data Reduction Process Completed ...")
        
    def find_pulse_edges(self, edges, signal, pulse_window, pp_extra):
        """
        Identifies and classifies pulses using derivative-based edge detection and validates pulse windows.
    
        Parameters:
        edges (array-like): List of detected edge indices.
        signal (array-like): The reference signal (e.g., SHPB strain gauge data).
        pulse_window (float): Expected pulse duration (in index units).
    
        Returns:
        tuple: (List of valid pulse start indices, Dictionary of all pulse properties)
        """
        rising_edges_start_idx = []
        falling_edges_start_idx = [] 
        window_start_approx = []
        window_end_approx = []
        
        edge_results = {
            "start": [],
            "end": [],
            "n_points": [],
            "direction": []
        }
        
        if len(edges) == 0:
            return window_start_approx, edge_results  # Return empty result if no edges detected
    
        # Compute first derivative of the signal
        derivative = np.gradient(signal)
    
        # Sort edges to ensure order
        edges = np.sort(edges)
    
        # Group consecutive edges
        grouped_edges = []
        current_group = [edges[0]]
    
        for i in range(1, len(edges)):
            if edges[i] - edges[i - 1] <= 2:  # Allowing small gaps (adjustable)
                current_group.append(edges[i])
            else:
                grouped_edges.append(current_group)
                current_group = [edges[i]]
        
        grouped_edges.append(current_group)  # Add last group
    
        # Process grouped edges to extract pulse properties
        for group in grouped_edges:
            start_idx = group[0]
            end_idx = group[-1]
            n_points = len(group)
    
            # Compute average derivative over the pulse range
            avg_slope = np.mean(derivative[start_idx:end_idx])
    
            # Direction is determined by the sign of the average derivative
            if avg_slope > 0: 
                direction = 1
                rising_edges_start_idx.append(start_idx)
            else: 
                direction = -1
                falling_edges_start_idx.append(start_idx)
    
            # Store results
            edge_results["start"].append(start_idx)
            edge_results["end"].append(end_idx)
            edge_results["n_points"].append(n_points)
            edge_results["direction"].append(direction)
    
        # **Improved Logic for Pulse Window Matching**
        for rise_idx in rising_edges_start_idx:
            # Find the closest falling edge that meets pulse window constraints
            valid_falls = [
                fall_idx for fall_idx in falling_edges_start_idx
                if pulse_window * (1 - pp_extra) <= np.abs(rise_idx - fall_idx) <= pulse_window * (1 + pp_extra)
            ]
    
            if valid_falls:
                # Select the closest falling edge
                best_fall_idx = min(valid_falls, key=lambda x: abs(rise_idx - x))
                window_start_approx.append(min(rise_idx, best_fall_idx))  # Store the earlier index as the start
                window_end_approx.append(max(rise_idx, best_fall_idx))
    
        return window_start_approx, window_end_approx
        
    def extract_pulse_window(self, signal, signal_start_approx, signal_end_approx, pulse_points, pp_extra, negative=True, atol_values=[5e-5, 10e-5, 15e-5, 20e-5], attempt=0):
        """
        Recursively attempts to find the pulse window using different tolerance (atol) values
        for signal_end_zero if necessary.
    
        Parameters:
            signal (numpy array): The input signal.
            signal_start_approx (int): Approximate start index of the signal.
            signal_end_approx (int): Approximate end index of the signal.
            pulse_points (int): Expected number of points in the pulse.
            pp_extra (float): Additional margin for searching start and end points.
            negative (bool): Determines whether to look for min or max gradient.
            atol_values (list): List of atol values to try for detecting signal_end_zero.
            attempt (int): Index of the current atol attempt.
    
        Returns:
            extracted_signal (numpy array): The extracted pulse signal.
            time_start_idx (int): The corrected start index of the extracted pulse.
        """
        
        if attempt >= len(atol_values):
            raise ValueError("Failed to extract pulse window with given threshold values.")
    
        # Define search range
        search_range = np.arange(int(signal_start_approx - (pulse_points * pp_extra)),
                                 int(signal_start_approx + (pulse_points * (1 + pp_extra))), 1)
  
        # Extract subset of the signal and compute gradients
        signal_subset = np.array(signal[search_range])
        signal_gradient = np.gradient(signal_subset)
    
        # Find start slope (minimum or maximum gradient)
        signal_start_slope = np.argmin(signal_gradient) if negative else np.argmax(signal_gradient)
    
        # Attempt to find the end zero crossing using the current threshold
        atol = atol_values[attempt]
        signal_start_zero_candidates = np.where(np.isclose(signal_subset[:signal_start_slope], 0, atol=atol))[0]
        signal_end_zero_candidates = np.where(np.isclose(signal_subset[signal_start_slope:], 0, atol=atol))[0]

        # Default values in case no zero crossings are found
        signal_start_zero = None
        signal_end_zero = None
    
        if len(signal_start_zero_candidates) > 0:
            signal_start_zero = signal_start_zero_candidates[-1]
        if len(signal_end_zero_candidates) > 0:
            signal_end_zero = signal_end_zero_candidates[0]            
        
        if signal_start_zero is None or signal_end_zero is None:
            if attempt + 1 < len(atol_values):  # Ensure we don't exceed available atol values
                print(f"Retrying with higher atol={atol_values[attempt+1]}")
                return self.extract_pulse_window(signal, signal_start_approx, signal_end_approx, pulse_points, pp_extra,
                                                 negative, atol_values, attempt + 1)
            else:
                raise ValueError("Failed to extract pulse window: No valid zero crossing found.")
    
        # Define final pulse window range
        window_range = np.arange(int(signal_start_zero), int(signal_start_slope + signal_end_zero), 1)
        extracted_signal = signal_subset[window_range]
    
        # Calculate the corrected start index
        time_start_idx = int(signal_start_approx - (pulse_points * pp_extra) + signal_start_zero)
    
        return extracted_signal, time_start_idx

    def process_pulses(self, initial_pp_extra=0.1, max_pp_extra=2.0, attempt = 0):
        """
        Finds and extracts pulses while adapting pp_extra dynamically in case of failure.
        
        Parameters:
            initial_pp_extra (float): Starting value of pp_extra.
            max_pp_extra (float): Maximum allowed increase for pp_extra before failing.
    
        Returns:
            None (modifies self variables in-place).
        """
        
        pp_extra = initial_pp_extra
    
        while pp_extra <= max_pp_extra:
            try:
                print(f"\nAttempt {attempt + 1}: Finding Approximate Pulse Starts with pp_extra={pp_extra:.2f}")
    
                # Detect pulse edges
                self.incident_start_approx, self.incident_end_approx = self.find_pulse_edges(
                    self.incident_edges, self.incident_strain_signal, self.pulse_data_points, pp_extra
                )
                self.transmitted_start_approx, self.transmitted_end_approx = self.find_pulse_edges(
                    self.transmitted_edges, self.transmitted_strain_signal, self.pulse_data_points, pp_extra
                )
    
                print(f"\nAttempt {attempt + 1}: Extracting Pulses with pp_extra={pp_extra:.2f}")
    
                # Extract incident & transmitted pulses
                self.incident_extracted, self.incident_start = self.extract_pulse_window(
                    self.incident_strain_signal, self.incident_start_approx[0], self.incident_end_approx[0],
                    self.pulse_data_points, pp_extra
                )
                self.transmitted_extracted, self.transmitted_start = self.extract_pulse_window(
                    self.transmitted_strain_signal, self.transmitted_start_approx[0], self.transmitted_end_approx[0],
                    self.pulse_data_points, pp_extra
                )
    
                # If Specimen Test, extract reflected pulse
                if self.test_type == "SpecimenTest":
                    self.reflected_extracted, _ = self.extract_pulse_window(
                        self.incident_strain_signal, self.incident_start_approx[1], self.incident_end_approx[1],
                        self.pulse_data_points, pp_extra, negative=False
                    )
                    self.subset_points = min(
                        len(self.incident_extracted), len(self.reflected_extracted), len(self.transmitted_extracted)
                    )
                    self.reflected_extracted = self.reflected_extracted[:self.subset_points]
                else:
                    self.subset_points = min(len(self.incident_extracted), len(self.transmitted_extracted))
    
                # Ensure all extracted signals have the same length
                self.incident_extracted = self.incident_extracted[:self.subset_points]
                self.transmitted_extracted = self.transmitted_extracted[:self.subset_points]
                self.time_extracted = np.linspace(0, self.pulse_duration, self.subset_points)
    
                print(f"\nSuccess: Pulse extraction completed with pp_extra={pp_extra:.2f}")
                return  # Exit function if everything worked
    
            except (IndexError, ValueError) as e:
                print(f"\nAttempt {attempt + 1} failed: {str(e)}. Increasing pp_extra and retrying...")
    
                # Increase pp_extra and retry
                pp_extra += 0.15  
                attempt += 1
                self.process_pulses(initial_pp_extra=pp_extra, max_pp_extra=2.0, attempt = attempt)
    
        raise ValueError(f"Pulse extraction failed after {attempt} attempts. Max pp_extra={max_pp_extra:.2f} reached.")

    def compute_fourier_coeffs(self, f_data, deltaT, omega0, T):
        """
        Compute the Fourier coefficients A0, A_k, and B_k from discrete data.
        
        Assumptions:
          - The time-domain signal f_data is sampled uniformly at 2N points.
          - T is the total period (pulse_duration).
          - The Fourier series representation is defined for n = 1,...,2N.
          
        Returns:
          A0 : float           Zeroth (DC) coefficient.
          A  : numpy array     Cosine coefficients for k = 1,...,N.
          B  : numpy array     Sine coefficients for k = 1,...,N.
        """
        f_data = np.array(f_data)
        M = f_data.shape[0]  # M should be even (M = 2N)
        if M % 2 != 0:
            raise ValueError("f_data must contain an even number of samples (2N samples).")
        N = M // 2  # Number of harmonics to use
        
        # Use all 2N sample indices: n = 1,2,...,2N
        n_vals = np.arange(1, M + 1)
        
        A0 = (2 / T) * np.sum(f_data * deltaT)
        A = np.zeros(N)
        B = np.zeros(N)
        for k in range(1, N + 1):
            cos_term = np.cos(k * omega0 * n_vals * deltaT)
            sin_term = np.sin(k * omega0 * n_vals * deltaT)
            A[k - 1] = (2 / T) * np.sum(f_data * cos_term * deltaT)
            B[k - 1] = (2 / T) * np.sum(f_data * sin_term * deltaT)
        return A0, A, B
    
    def dispersion_eq(self, X, k, c0, omega0, r, A_param, B_param, C_param, D_param, E_param, F_param):
        """
        Implicit equation for X = c_k/c0 for the k-th harmonic.
        """
        y = (r * k * omega0) / (2 * np.pi * c0 * X)
        denom = C_param * y**4 + D_param * y**3 + E_param * y**2 + F_param * y**1.5 + 1
        return X - (A_param + B_param / denom)
        
    def compute_dispersion_parameters(self, omega0, c0, r,
                                      A_param, B_param, C_param, D_param, E_param, F_param,
                                      num_harmonics):
        """
        Solve for the dispersion-corrected phase velocities c_k for k = 1,...,num_harmonics.
        Returns arrays of c_k and Λ_k.
        """
        c_k_arr = np.zeros(num_harmonics)
        Lambda_arr = np.zeros(num_harmonics)
        for k in range(1, num_harmonics + 1):
            X0 = 0.6  # initial guess for X = c_k/c0; adjust as needed
            X_sol, = fsolve(self.dispersion_eq, X0, args=(k, c0, omega0, r,
                                                      A_param, B_param, C_param,
                                                      D_param, E_param, F_param))
            c_k = X_sol * c0
            Lambda_k = (2 * np.pi * c0 * X_sol) / (k * omega0)
            c_k_arr[k - 1] = c_k
            Lambda_arr[k - 1] = Lambda_k
        return c_k_arr, Lambda_arr

    def fourier_series_dispersion(self, n, deltaT, A0, A, B, omega0, c0, c_k_arr, delta_x):
        """
        Evaluate the dispersion-corrected Fourier series at times t = n * deltaT.
        The corrected series is:
          F(nΔT) = A0/2 + Σₖ₌₁ᴺ [ Aₖ cos(kω0 nΔT - φₖ) + Bₖ sin(kω0 nΔT - φₖ) ],
        with phase correction:
          φₖ = kω0 (Δx/c_k - Δx/c0).
        """
        n = np.array(n, ndmin=1)
        t = n * deltaT
        f_val = (A0 / 2.0) * np.ones_like(t)
        num_harmonics = len(A)  # This is N (number of Fourier components)
        for k in range(1, num_harmonics + 1):
            phi = k * omega0 * (delta_x / c_k_arr[k - 1] - delta_x / c0)
            f_val += A[k - 1] * np.cos(k * omega0 * t - phi) + \
                     B[k - 1] * np.sin(k * omega0 * t - phi)
        return f_val if f_val.size > 1 else f_val.item()
        
    def fourier_series(self, n, deltaT, A0, A, B, omega0):
        """
        Evaluate the original (uncorrected) Fourier series at t = n * deltaT.
        """
        n = np.array(n, ndmin=1)
        t = n * deltaT
        f_val = (A0 / 2.0) * np.ones_like(t)
        num_harmonics = len(A)
        for k in range(1, num_harmonics + 1):
            f_val += A[k - 1] * np.cos(k * omega0 * t) + B[k - 1] * np.sin(k * omega0 * t)
        return f_val if f_val.size > 1 else f_val.item()
    
    def dispersion_parameters(self, poissons):
        dispersion_data = pd.read_csv("config/bancroft_dispersion_parameters.csv")
        
        dispersion_data.where(dispersion_data["v"] == poissons, inplace=True)
        dispersion_data.dropna(inplace=True)
        return dispersion_data
    
    def wave_dispersion_correction(self, time, signal, c0, r, poissons, omega0, delta_t, pulse_duration, total_points, delta_x):
        """
        Applies dispersion correction to a pulse.
        
        Parameters:
          time          : 1D array of the original time values.
          signal        : 1D array of the corresponding signal values.
          c0            : Base (nondispersive) wave speed (mm/ms).
          r             : Bar radius (mm).
          omega0        : Fundamental angular frequency (2π/T).
          delta_t       : Sampling interval (ms).
          pulse_duration: Total pulse duration (ms), i.e., T.
          total_points  : Total number of time samples to represent the pulse (should be even, e.g., 1024).
          delta_x       : Propagation distance (mm) for phase correction.
        
        Returns:
          f_dispersion  : The dispersion-corrected reconstructed pulse.
          t             : The uniform time grid.
        """
        if total_points % 2 != 0:
            raise ValueError("total_points must be even (i.e. 2N samples).")
        
        # Create a uniform time grid for the pulse from 0 to pulse_duration.
        t = np.linspace(0, pulse_duration, total_points, endpoint=True)
        
        # Interpolate the original signal onto this uniform grid.
        spline = CubicSpline(time, signal)
        f_data = spline(t)  # f_data now has shape (total_points,)
           
        # Compute Fourier coefficients from the 2N time samples.
        # Here pulse_duration = T.
        A0, A, B = self.compute_fourier_coeffs(f_data, delta_t, omega0, pulse_duration)
                    
        # The number of Fourier components (harmonics) is half the total number of samples.
        num_harmonics = total_points // 2
        
        # Step 1 & 2: Compute dispersion parameters (c_k and Λ_k) for each harmonic.
        # The dispersion relation parameters (A_param to F_param) should come from your interpolation
        # based on Poisson's ratio and Bancroft's table. Here we use fixed example values.
        paramaters = self.dispersion_parameters(poissons)
    
        # Calculate phase velocities c_k and corresponding Λ_k for each harmonic (k=1,...,num_harmonics).
        c_k_arr, Lambda_arr = self.compute_dispersion_parameters(omega0, c0, r,
                                                            paramaters["A"], paramaters["B"],
                                                            paramaters["C"], paramaters["D"],
                                                            paramaters["E"], paramaters["F"],
                                                            num_harmonics)
        
        # Build a DataFrame with the ratios for diagnostic purposes.
        # (Make sure that the arrays A and B have length num_harmonics.)
        harmonic_ratios = pd.DataFrame()
        harmonic_ratios["r/Lambda"] = r / Lambda_arr
        harmonic_ratios["A_k / A_0"] = A / A0
        harmonic_ratios["B_k / A_0"] = B / A0
        # Here we compute D_k as the amplitude of the k-th harmonic and then normalize by A0.
        harmonic_ratios["D_k / A_0"] = np.sqrt(A**2 + B**2) / A0  
        #print("All harmonic ratios:")
        #print(harmonic_ratios.head(20))
        
        # Filter: Only retain those harmonics where r/Lambda < 0.1.
        valid_indices = np.where((r / Lambda_arr) <= 0.1)[0]
        #print("Valid harmonic indices (r/Lambda <= 0.10):", valid_indices)
        
        # Update the Fourier coefficients and dispersion parameters to include only valid harmonics.
        A = A[valid_indices]
        B = B[valid_indices]
        c_k_arr = c_k_arr[valid_indices]
        
        # For reconstruction, we now use the truncated number of harmonics.
        num_valid_harmonics = len(valid_indices)
        
        # Create sample indices corresponding to each time point.
        n_vals = np.arange(1, total_points + 1)
        
        # Evaluate the dispersion-corrected Fourier series using the truncated coefficients.
        f_dispersion = self.fourier_series_dispersion(n_vals, delta_t, A0, A, B,
                                                 omega0, c0, c_k_arr, delta_x)   
   
        return f_dispersion, t
    
    @staticmethod
    def fit_pulse_windows(pulses, threshold, negatives):
        """
        Trim a list of pulses based on a threshold so that each pulse starts at
        its own threshold crossing and is then trimmed to a common length.
        
        Parameters:
          pulses    : list or array of 1D arrays
                      Each element is a pulse (time-series data).
          threshold : float
                      The threshold value used for determining the pulse start.
          negative  : bool, default True
                      If True, the pulse start is defined as the first index 
                      where the pulse value is less than the threshold.
                      If False, the pulse start is defined as the first index 
                      where the pulse value is greater than the threshold.
        
        Returns:
          trimmed_pulses : list of 1D NumPy arrays
                           Each pulse is trimmed starting at its own threshold
                           crossing and continuing for a common length (the
                           minimum available length across pulses).
        """
        start_indices = []
        for idx, pulse in enumerate(pulses):
            # Ensure pulse is a NumPy array.
            pulse = np.array(pulse)
            
            if negatives[idx]:
                # Find indices where the pulse is below the threshold.
                indices = np.where(pulse < -threshold)[0]
            else:
                indices = np.where(pulse > threshold)[0]
            
            # If no index meets the criterion, we default to index 0.
            idx = indices[0] if len(indices) > 0 else 0
            start_indices.append(idx)
        
        # For each pulse, compute the number of points available after its start index.
        lengths_after = [len(pulse) - idx for pulse, idx in zip(pulses, start_indices)]
        common_length = min(lengths_after)
        
        # Now trim every pulse from its own start index to start index + common_length.
        trimmed_pulses = [np.array(pulse)[idx: idx + common_length]
                          for pulse, idx in zip(pulses, start_indices)]
        
        return trimmed_pulses
