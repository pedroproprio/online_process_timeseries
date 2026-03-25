import clr
import os
import sys
import logging
import time
from typing import List, Tuple, Optional

# Load basic .NET Libraries
from System.Collections.Generic import List
from System.Threading import CancellationTokenSource

# Configure the logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PyCCT:
    """
    A class to interact with the Thorlabs Compact Spectrograph SDK.
    
    This class allows to discover available spectrograph devices and connect to a specific device.
    """
    
    def __init__(self, dll_path: str = './net48'):
        """
        Initialize the PyCCT class and load required DLLs.
        
        Parameters:
        dll_path (str): The path to the directory containing the required DLLs.
        """
        # Set the DLL path and load required DLLs
        self.load_dlls(dll_path)
        
        # Use .NET Logger, because it can be shared with SDK of the Compact Spectrometers
        self.dot_net_logger = self.initialize_logger(LogLevel.Information, "CCT.SDK")

        # Constructing the startup helper that manages required device interactions
        self.startupHelperCct = StartupHelperCompactSpectrometer(self.dot_net_logger)

    @staticmethod
    def load_dlls(dll_path: str) -> None:
        """
        Load the required DLLs from the specified path.
        
        Parameters:
        dll_path (str): The path to the directory containing the required DLLs.
        
        Raises:
        RuntimeError: If any of the DLLs fail to load.
        """
        # Define the DLL path relative to this file
        dll_path = os.path.abspath(os.path.join(os.path.dirname(__file__), dll_path))
        if dll_path not in sys.path:
            sys.path.append(dll_path)
        os.environ['PATH'] = dll_path + os.pathsep + os.environ['PATH']

        try:
            # Load the required DLLs
            dlls = [
                'Thorlabs.ManagedDevice.CompactSpectrographDriver.dll',
                'Microsoft.Extensions.Logging.dll',
                'Microsoft.Extensions.Logging.Console.dll',
                'Microsoft.Extensions.Options.dll'
            ]

            for dll in dlls:
                clr.AddReference(os.path.join(dll_path, dll))
        except Exception as e:
            logger.error(f"Failed to load DLLs from {dll_path}: {e}")
            raise RuntimeError(f"Failed to load DLLs from {dll_path}: {e}")

        # Perform imports after loading the DLLs
        global List, IConnectDevices, StartupHelper, CancellationTokenSource
        global StartupHelperCompactSpectrometer, ICompactSpectrographDriver, Dataset
        global LogLevel, LoggerFactory, ILoggerProvider, LoggerFilterOptions, ILogger
        global ConsoleLoggerProvider, ConsoleLoggerOptions
        global OptionsFactory, IConfigureNamedOptions, IPostConfigureOptions, OptionsMonitor, IOptionsChangeTokenSource, OptionsCache

        # Import the required types from loaded DLLs
        from System.Collections.Generic import List
        from System.Threading import CancellationTokenSource
        
        # Import necessary classes from the Compact Spectrometer SDK
        from Thorlabs.ManagedDevice.CompactSpectrographDriver.Workflow import StartupHelperCompactSpectrometer
        from Thorlabs.ManagedDevice.CompactSpectrographDriver import ICompactSpectrographDriver, Dataset
        
        # Enable use of .NET Logging
        from Microsoft.Extensions.Logging import LogLevel, LoggerFactory, ILoggerProvider, LoggerFilterOptions, ILogger
        from Microsoft.Extensions.Logging.Console import ConsoleLoggerProvider, ConsoleLoggerOptions
        from Microsoft.Extensions.Options import OptionsFactory, IConfigureNamedOptions, IPostConfigureOptions, OptionsMonitor, IOptionsChangeTokenSource, OptionsCache

    def discover_devices(self) -> List[str]:
        """
        Discover connected spectrograph devices.
        
        Returns:
        list: A list of discovered device IDs, or an empty list if no devices are found.
        """
        try:
            logger.info("Discovering devices...")

            # Running device discovery
            cancellation_token = CancellationTokenSource().Token

            # Getting the list of available devices
            connection_keys = list(self.startupHelperCct.GetKnownDevicesAsync(cancellation_token).Result)
            
            if not connection_keys:
                logger.info("No devices found.")
                return []
            else:
                report = "Found devices:"
                for key in connection_keys:
                    report = f"{report}\n- {key}"
                logger.info(report)
                return connection_keys
        except Exception as e:
            logger.error(f"An error occurred during device discovery: {e}")
            return []

    def connect_to_device(self, device_id: str) -> Optional['SpectrometerWrapper']:
        """
        Connect to a specific spectrograph device by its ID.
        
        Parameters:
        device_id (str): The ID of the device to connect to.
        
        Returns:
        SpectrometerWrapper: The connected spectrometer driver, or None if the connection fails.
        """
        try:
            spectrometer = self.startupHelperCct.GetCompactSpectrographById(device_id)
            logger.info("Connected to device. '{0}'".format(device_id))
            return SpectrometerWrapper(spectrometer)
        except Exception as e:
            logger.error(f"An error occurred while connecting to the device: {e}")
            return None
        
    def register_ethernet_ip_address(self, ip_address) -> bool:
        """
        Add IP address into list for Ethernet Discovery
        
        Parameters:
        ip_address (str): The IP Address to register
        
        Returns:
        Whether a new address was added into collection
        """
        try:
            return self.startupHelperCct.RegisterEthernetIpAddress(ip_address)
        except Exception as e:
            logger.error(f"An error occurred while registering an IP Address: {e}")
        return False

    def set_spectrometer_disconnected_by_id(self, device_id: str, connect_back: Optional[bool] = False) -> bool:
        """
        Set configuration flag to disconnect device and run procedure to bring it into Offline state

        Parameters:
        deviceId (str): Known Device ID

        connect_back (bool): When true, reverse operation is performed and disconnection configuration flag gets dropped and reconnection operation is proceeded

        Returns:
        Whether the procedure was successful
        """
        try:
            result = self.startupHelperCct.SetSpectrometerDisconnectedByIdAsync(device_id, connect_back).Result
            if result & connect_back:
                # Running device discovery to refresh connection
                cancellation_token = CancellationTokenSource().Token
                connection_keys = list(self.startupHelperCct.GetKnownDevicesAsync(cancellation_token).Result)
                spectrometer = self.startupHelperCct.GetCompactSpectrographById(device_id)
                if spectrometer:
                    return not spectrometer.IsOffline
                else:
                    return False
            else:
                return result

        except Exception as e:
            logger.error(f"An error occurred while managing disconnected state of device '{device_id}': {e}")
        return False
    
    def get_with_virtual(self):
        """
        Get whether to use a Virtual Device
        """
        return self.startupHelperCct.WithVirtual

    def set_with_virtual(self, state: bool):
        """
        Set whether to use a Virtual Device
        """
        self.startupHelperCct.WithVirtual = state
        
    @staticmethod
    def initialize_logger(log_verbosity, name):
        options_setups = List[IConfigureNamedOptions[ConsoleLoggerOptions]]()
        options_post = List[IPostConfigureOptions[ConsoleLoggerOptions]]()
        options_factory = OptionsFactory[ConsoleLoggerOptions](options_setups, options_post)
        options_sources = List[IOptionsChangeTokenSource[ConsoleLoggerOptions]]()
        options_cache = OptionsCache[ConsoleLoggerOptions]()
        options_monitor = OptionsMonitor[ConsoleLoggerOptions](options_factory, options_sources, options_cache)
        logger_provider = ConsoleLoggerProvider(options_monitor)
        logger_providers = List[ILoggerProvider]()
        logger_providers.Add(logger_provider)
        options = LoggerFilterOptions()
        options.MinLevel = log_verbosity
        logger_factory = LoggerFactory(logger_providers, options)
        return logger_factory.CreateLogger(name)
        
    def stop(self):
        """
        Disposes connected managed devices
        """
        self.startupHelperCct.Dispose()   
        
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
        pass

class SpectrometerWrapper:
    """
    Handle of the Compact Spectrometer SDK instance
    """
    
    def __init__(self, spectrometer: 'ICompactSpectrographDriver'):
        self.spectrometer = spectrometer

    def __enter__(self) -> 'SpectrometerWrapper':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    def get_device_id(self) -> str:
        """
        Get Spectrometer Device ID
        """
        return self.spectrometer.DeviceId

    def is_saturated(self) -> bool:
        """
        Get whether the last acquired spectrum is saturated
        """
        return self.spectrometer.IsSaturated

    def set_manual_exposure(self, exposure_time: float, cancellation_token: Optional[CancellationTokenSource] = None) -> bool:
        """
        Set exposure time for the next spectrum acquisition
        
        Parameters:
        exposure_time (float): Exposure time in milliseconds
        
        Returns:
        bool: Whether the exposure time was set successfully
        """
        if cancellation_token is None:
            cancellation_token = CancellationTokenSource().Token
        try:
            return self.spectrometer.SetManualExposureAsync(exposure_time, cancellation_token).Result
        except Exception as e:
            logger.error(f"An error occurred while setting manual exposure: {e}")
        return False

    def get_manual_exposure(self) -> float:
        """
        Get Exposure, ms
        """
        return round(self.spectrometer.ManualExposure, 2)

    def set_hardware_average(self, ave_frames: int, cancellation_token: Optional[CancellationTokenSource] = None) -> bool:
        """
        Set hardware averaging for the next spectrum acquisition
        
        Parameters:
        ave_frames (int): Amount of Frames to average
        
        Returns:
        bool: Whether the hardware averaging was set successfully
        """
        if cancellation_token is None:
            cancellation_token = CancellationTokenSource().Token
        try:
            return self.spectrometer.SetHwAverageAsync(ave_frames, cancellation_token).Result
        except Exception as e:
            logger.error(f"An error occurred while setting hardware averaging: {e}")
        return False

    def get_hardware_average(self) -> int:
        """
        Get Hardware Averaging, frames
        """
        return int(self.spectrometer.HwAverage)

    def acquire_single_spectrum(self, cancellation_token: Optional[CancellationTokenSource] = None) -> Tuple[Optional[List[float]], Optional[List[float]], Optional[float], Optional[int]]:
        """
        Acquire single Spectrum
        
        Returns:
        Spectrum data as Tuple of Wavelengths and Intensities arrays along with actual Exposure in ms and amount of hardware averaged frames
        """
        if cancellation_token is None:
            cancellation_token = CancellationTokenSource().Token
        try:
            spectrum = self.spectrometer.AcquireSingleSpectrumAsync(cancellation_token).Result
            return list(spectrum.Wavelength), list(spectrum.Intensity), round(spectrum.SensorExposureMs,2), spectrum.HardwareAverage
        except Exception as e:
            logger.error(f"An error occurred while acquiring the spectrum: {e}")
            return None, None, 0, 0

    def set_shutter(self, open_position: bool, cancellation_token: Optional[CancellationTokenSource] = None) -> bool:
        """
        Set position of the Shutter and wait 40 ms, because Mechanical Shutter requires some time to travel into changed position
        
        Parameters:
        open_position (bool): true for light measurements; false for dark measurements
        
        Returns:
        bool: Whether the Shutter position was set successfully
        """
        if cancellation_token is None:
            cancellation_token = CancellationTokenSource().Token
        try:
            result = self.spectrometer.SetShutterAsync(open_position, cancellation_token).Result
            # Mechanical Shutter requires some time to travel into changed position
            time.sleep(0.04)
            return result
        except Exception as e:
            logger.error(f"An error occurred while setting the shutter: {e}")
        return False

    def update_dark_spectrum(self, drop: bool, cancellation_token: Optional[CancellationTokenSource] = None) -> bool:
        """
        Update Dark Spectrum for further subtraction from measured spectra
        
        Parameters:
        drop (bool): true for dropping any existing record; false for actual acquisition
        
        Returns:
        bool: Whether the Shutter position was set successfully
        """
        if cancellation_token is None:
            cancellation_token = CancellationTokenSource().Token
        try:
            return self.spectrometer.UpdateDarkSpectrumAsync(drop, cancellation_token).Result
        except Exception as e:
            logger.error(f"An error occurred while updating the dark spectrum: {e}")
        return False

    def set_input_hw_trigger(self, enabled: bool, ave_no_wait: bool, slope_falling_edge: bool,
                             cancellation_token: Optional[CancellationTokenSource] = None) -> bool:
        """
        Set mode of listening from the Input Hardware Trigger

        Parameters:
        enabled (bool): False for free Running, True for triggered Mode
        ave_no_wait (bool): False for each spectrum frame to require own Trigger Event, True for immediate averaging on a single Trigger Event
        slope_falling_edge (bool): false for Rising Edge, True for Falling Edge

        Returns:
        bool: Whether the operation was successful
        """
        if cancellation_token is None:
            cancellation_token = CancellationTokenSource().Token
        try:
            return self.spectrometer.SetInputHwTriggerAsync(enabled, ave_no_wait, slope_falling_edge, cancellation_token).Result
        except Exception as e:
            logger.error(f"An error occurred while setting mode of the input hardware trigger: {e}")
        return False

    def get_input_hw_trigger_state(self) -> Tuple[Optional[bool], Optional[bool], Optional[bool]]:
        """
        Get current settings of the Input Hardware trigger
        """
        return self.spectrometer.HwTriggerIn, self.spectrometer.HwTriggerInAveNoWait, self.spectrometer.HwTriggerInSlope

    def set_output_hw_trigger_delay(self, delay_ms: float,
                            cancellation_token: Optional[CancellationTokenSource] = None) -> bool:
        """
        Set Delay in ms for Output Hardware Trigger.
        The output Hardware trigger is always issued on the acquisition start, except when its delay exceeds the acquisition time.
        In order to schedule acquisition start after issuing of the Output Hardware Trigger, this setting should be set to negative value.

        Parameters:
        exposure_time (float): Delay for Output Hardware Trigger in milliseconds

        Returns:
        bool: Whether the setting was set successfully
        """
        if cancellation_token is None:
            cancellation_token = CancellationTokenSource().Token
        try:
            return self.spectrometer.SetOutputHwTriggerDelayAsync(delay_ms, cancellation_token).Result
        except Exception as e:
            logger.error(f"An error occurred while setting output hardware trigger delay: {e}")
        return False

    def get_output_hw_trigger_delay(self) -> float:
        """
        Get Delay for Output Hardware Trigger, ms
        """
        return round(self.spectrometer.HwTriggerOutDelayMs, 2)
    
    def get_use_amplitude_correction(self) -> bool:
        """
        Get whether to use the Amplitude Correction
        """
        return self.spectrometer.UseAmplitudeCorrection

    def set_use_amplitude_correction(self, state: bool):
        """
        Set whether to use the Amplitude Correction
        """
        self.spectrometer.UseAmplitudeCorrection = state
