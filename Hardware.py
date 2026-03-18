# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Autor: Felipe Oliveira Barino
# Data: 03 de Junho de 2024
#
# Este script é fornecido "COMO ESTÁ", sem garantia de qualquer tipo, expressa ou
# implícita. O autor não se responsabiliza por quaisquer danos diretos ou indiretos
# resultantes do uso deste software. Use por sua conta e risco.
#
# Aviso de Reprodução:
# A reprodução ou distribuição não autorizada deste código, ou de qualquer parte
# dele, é estritamente proibida.
# -----------------------------------------------------------------------------

import numpy as np
import logging
import socket
import serial
import time
from scipy.signal import savgol_filter

logger = logging.getLogger(__name__)

class BraggMeter:
    """
    Represents a BraggMeter object used for controlling and retrieving data from a BraggMeter device.

    Args:
        host (str): The IP address of the BraggMeter device. Default is '10.0.0.150'.
        port (int): The port number of the BraggMeter device. Default is 3500.

    Attributes:
        commands (dict): A dictionary containing the commands used to communicate with the BraggMeter device.
        host (str): The IP address of the BraggMeter device.
        port (int): The port number of the BraggMeter device.
        timeout (int): The timeout value for the socket connection.
        sock (socket.socket): The socket connection object.

    Raises:
        RuntimeError: If the BraggMeter device is in the heating state.

    """

    def __init__(self, host='10.0.0.150', port:int=3500, legacy_cmds=False):
        """
        Initializes a new instance of the BraggMeter class.

        Args:
            host (str): The IP address of the BraggMeter device. Default is '10.0.0.150'.
            port (int): The port number of the BraggMeter device. Default is 3500.
            legacy_cmds (bool): If True, uses legacy commands (for old BraggMeter - FiberSensing). Default is False.

        Raises:
            RuntimeError: If the BraggMeter device is in the heating state.

        """
        self.legacy_cmds = legacy_cmds
        if self.legacy_cmds:
            self.commands = {'status': 	"\000\000\000\006:STAT?\r\n".encode('ascii'),
                            'start': 	"\000\000\000\n:ACQU:STAR\n".encode('ascii'),
                            'stop': 	"\000\000\000\n:ACQU:STOP\n".encode('ascii'),
                            'trace0': 	"\000\000\000\023:ACQU:OSAT:CHAN:0\n?".encode('ascii'),
                            'trace1': 	"\000\000\000\023:ACQU:OSAT:CHAN:1\n?".encode('ascii'),
                            'trace2': 	"\000\000\000\023:ACQU:OSAT:CHAN:2\n?".encode('ascii'),
                            'trace3': 	"\000\000\000\023:ACQU:OSAT:CHAN:3\n?".encode('ascii'),
                            }
        else:
            self.commands = {'status': ":STAT?\r\n".encode('ascii'),
                            'start':  ":ACQU:STAR\r\n".encode('ascii'),
                            'stop':   ":ACQU:STOP\r\n".encode('ascii'),
                            'trace0': ":ACQU:OSAT:CHAN:0?\r\n".encode('ascii'),
                            'trace1': ":ACQU:OSAT:CHAN:1?\r\n".encode('ascii'),
                            'trace2': ":ACQU:OSAT:CHAN:2?\r\n".encode('ascii'),
                            'trace3': ":ACQU:OSAT:CHAN:3?\r\n".encode('ascii'),
                            'bragg0': ":ACQU:WAVE:CHAN:0?\r\n".encode('ascii'),
                            'bragg1': ":ACQU:WAVE:CHAN:1?\r\n".encode('ascii'),
                            'bragg2': ":ACQU:WAVE:CHAN:2?\r\n".encode('ascii'),
                            'bragg3': ":ACQU:WAVE:CHAN:3?\r\n".encode('ascii'),
                            'power0': ":ACQU:POWE:CHAN:0?\r\n".encode('ascii'),
                            'power1': ":ACQU:POWE:CHAN:1?\r\n".encode('ascii'),
                            'power2': ":ACQU:POWE:CHAN:2?\r\n".encode('ascii'),
                            'power3': ":ACQU:POWE:CHAN:3?\r\n".encode('ascii'),
                            'gain0?': ":ACQU:CONF:GAIN:CHAN:0?\r\n".encode('ascii'),
                            'gain1?': ":ACQU:CONF:GAIN:CHAN:1?\r\n".encode('ascii'),
                            'gain2?': ":ACQU:CONF:GAIN:CHAN:2?\r\n".encode('ascii'),
                            'gain3?': ":ACQU:CONF:GAIN:CHAN:3?\r\n".encode('ascii'),
                            }
        self.host = host
        self.port = port
        self.timeout = 5
        self.sock = None

        self.start()

    def close(self):
        """
        Closes the socket connection to the BraggMeter device.
        """
        if self.sock is not None:
            try:
                self.sock.close()
                logger.info('Successfuly closed socket.')
            except Exception as e:
                logger.warning(f'Error closing socket: {e}')
            finally:
                self.sock = None

    def open(self):
        """
        Opens a socket connection to the BraggMeter device.
        """
        try:
            if self.sock is not None:
                logger.debug('Closing existing socket before reopening.')
                try:
                    self.sock.close()
                except (socket.error, AttributeError):
                    pass
                self.sock = None

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
            logger.info(f'Successfully opened socket to {self.host}:{self.port}')
        except Exception as e:
            self.sock = None
            logger.error(f'Failed to open socket to {self.host}:{self.port}: {e}')
            raise ConnectionError(f'Failed to open socket: {e}')

    def ask(self, key):
        """
        Sends a command to the BraggMeter device and returns the response.

        Args:
            key (str): The key corresponding to the command to be sent.

        Returns:
            str: The response from the BraggMeter device.

        """
        string = self.commands[key]
        resp = self.send(string)
        return resp

    def send(self, string, retries=0):
        """
        Assure a socket connection to the BraggMeter device, sends a command, and returns the response.

        Args:
            string (str): The command to be sent.
            retries (int): Number of retry attempts. Default is 0.

        Returns:
            str: The response from the BraggMeter device.

        """
        self.open()
        try:
            self.sock.sendall(string)
            resp = b''
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                resp += chunk
                if b'\n' in chunk:
                    break
            resp = resp.decode('latin-1')
        except (socket.error, socket.timeout) as e:
            logger.error(f'Socket error: {e}. Retrying...')
            if retries > 2:
                raise ConnectionError(f'Max retries exceeded: {e}')
            return self.send(string, retries=retries+1)
        self.close()
        return resp

    def start(self):
        """
        Starts the acquisition process on the BraggMeter device.

        """
        status = self.get_status()
        logger.info(f'BraggMETER status: {status}')
        if status == 1:
            self.ask('start')
        elif status == 3 or status == 4:
            self.ask('stop')
            self.ask('start')
        elif status == 5:
            err_msg = 'BraggMETER em aquecimento'
            logger.error(err_msg)
            raise RuntimeError(err_msg)

    def stop(self):
        """
        Stops the acquisition process on the BraggMeter device.

        Returns:
            str: The response from the BraggMeter device.

        """
        status = self.get_status()
        logger.debug(f'BraggMETER status before stopping: {status}')
        
        resp = self.ask('stop')
        status = self.get_status()
        logger.info(f'BraggMETER status: {status}')

        return resp

    def get_status(self):
        """
        Retrieves the status of the BraggMeter device.

        Returns:
            int: The status code of the BraggMeter device.

        """
        resp = self.ask('status')
        logger.debug(f'Resposta do status: {resp}')
        resp = resp.split(':')
        loc = 0
        for i in range(0, len(resp)):
            if resp[i] == 'ACK':
                loc = i + 1
        return int(resp[loc])

    def get_osa_trace(self, channel=0):
        """
        Retrieves the OSA trace data from the specified channel.

        Args:
            channel (int): The channel number.

        Returns:
            numpy.ndarray: An array containing the wavelength and trace data.

        """
        resp = self.ask(f'trace{channel}')
        resp = resp.split(':')
        
        if self.legacy_cmds:
            pot = resp[-1]
            trace = np.array([float(x) for x in pot.split(',')])
            wl = np.linspace(1500, 1600, len(trace))
        else:
            pot, wl = resp[-2], resp[-1]
            hex_values = [pot[i:i+3] for i in range(0, len(pot), 3)]
            trace = [int(hex_value, 16) for hex_value in hex_values]
            wl = np.array([float(x) for x in wl.split(',')])
        
        trace = 10*np.log10(np.abs(trace)+1e-12)
        trace = savgol_filter(trace, 101, 2)
        trace *= -1

        spec = np.stack((wl, trace), axis=1)
        spec = np.flipud(spec)
        return spec

    def get_peaks(self, channel):
        """
        Retrieves the peak intensity from the specified channel.

        Args:
            channel (int): The channel number.

        Returns:
            list: A list of peak intensities.

        """
        if self.legacy_cmds:
            logger.error('get_peaks not implemented for legacy commands')
            return -1
        try:
            lambdas = self.ask(f'power{channel}')
        except Exception as e:
            logger.error(f'Erro ao ler intensidade do Bragg: {e}')
            self.start()
            lambdas = self.ask(f'power{channel}')
        i = lambdas.find('ACK') + 4
        lambdas = lambdas[i:-2].split(',')
        if len(lambdas) == 0:
            return []
        if lambdas[0] == '':
            return []
        return [float(lamb) if lamb else 0 for lamb in lambdas]
    
    def get_bragg(self, channel):
        """
        Retrieves the peak wavelength from the specified channel.

        Args:
            channel (int): The channel number.

        Returns:
            list: A list of peak positions.

        """
        if self.legacy_cmds:
            logger.error('get_bragg not implemented for legacy commands')
            return -1
        try:
            lambdas = self.ask(f'bragg{channel}')
        except Exception as e:
            logger.error(f'Erro ao ler intensidade do Bragg: {e}')
            self.start()
            lambdas = self.ask(f'bragg{channel}')
        i = lambdas.find('ACK') + 4
        lambdas = lambdas[i:-2].split(',')
        if len(lambdas) == 0:
            return []
        if lambdas[0] == '':
            return []
        return [float(lamb) if lamb else 0 for lamb in lambdas]
    
    def set_gain(self, channel, gain):
        """
        Sets the gain for the specified channel.

        Args:
            channel (int): The channel number.
            gain (str): The gain value to be set from 0 to 255.

        Returns:
            str: The response from the BraggMeter device.

        """
        if self.legacy_cmds:
            logger.error('set_gain not implemented for legacy commands')
            return -1
        
        command = f":ACQU:CONF:GAIN:CHAN:{channel}:{gain}\r\n".encode('ascii')
        resp = self.send(command)
        return resp
    
    def set_threshold(self, channel, threshold):
        """
        Sets the threshold for the specified channel.

        Args:
            channel (int): The channel number.
            threshold (str): The threshold value to be set from 200 to 3200.

        Returns:
            str: The response from the BraggMeter device.

        """
        if self.legacy_cmds:
            logger.error('set_threshold not implemented for legacy commands')
            return -1
        command = f" :ACQU:CONF:THRE:CHAN:{channel}:{threshold}\r\n".encode('ascii')
        resp = self.send(command)
        return resp

    def get_gain(self, channel):
        """
        Retrieves the gain value for the specified channel.

        Args:
            channel (int): The channel number.

        Returns:
            str: The gain value.

        """
        if self.legacy_cmds:
            logger.error('get_gain not implemented for legacy commands')
            return -1
        resp = self.ask   

class Imon512:
    """
    Represents an Imon512 object used for controlling and retrieving data from an Imon512 device.

    Args:
        port (str): The port name of the Imon512 device. Default is 'COM5'.
        baudrate (int): The baud rate of the Imon512 device. Default is 921600.

    Attributes:
        port (str): The port name of the Imon512 device.
        baudrate (int): The baud rate of the Imon512 device.
        serial_port (serial.Serial): The serial port connection object.

    """

    def __init__(self, port='COM5', baudrate=921600):
        self.port = port
        self.baudrate = baudrate

        self.serial_port = None
        self.open()
        
        try:
            self.ask('*idn?')
            response = self.listen()
            logger.debug(response.decode())
        except Exception as e:
            logger.error(f'Communication error after opening port: {e}')
            raise e

        # A, B1, B2, ..., B5
        self.wl_param = self.update_coefficients()
        # alpha, alpha0, beta, beta0
        self.tem_param = self.update_temperature_coefficients()
        self.wl = np.arange(0, 510, dtype=float)
        self.temp = None

    def close(self):
        """
        Closes the serial port connection safely.
        """
        if self.serial_port is not None:
            try:
                # Tenta fechar sem verificar is_open para evitar acessar handle inválido
                self.serial_port.close()
                logger.info(f'Successfully closed port {self.port}')
            except OSError as e:
                # Ignora erros de handle inválido (porta já foi fechada ou desconectada)
                if hasattr(e, 'winerror') and e.winerror in [6, 9]:  # ERROR_INVALID_HANDLE ou outros
                    logger.debug(f'Port {self.port} handle already invalid, ignoring: {e}')
                else:
                    logger.warning(f'Error closing port {self.port}: {e}')
            except (AttributeError, TypeError) as e:
                # Handle já foi destruído ou está None
                logger.debug(f'Port {self.port} already destroyed: {e}')
            except Exception as e:
                logger.warning(f'Unexpected error closing port {self.port}: {e}')
            finally:
                self.serial_port = None

    def open(self):
        """
        Opens the serial port connection with retry logic.
        """
        try:
            # Fecha conexão existente antes de abrir uma nova
            if self.serial_port is not None:
                logger.debug(f'Closing existing connection on {self.port} before reopening.')
                try:
                    if hasattr(self.serial_port, 'is_open') and self.serial_port.is_open:
                        self.serial_port.close()
                except (OSError, AttributeError):
                    pass # Ignora erros ao verificar/fechar porta
                self.serial_port = None
            
            self.serial_port = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=1)
            logger.info(f'Successfully opened port {self.port}')
        except Exception as e:
            self.serial_port = None  # Garante que serial_port está None em caso de erro
            logger.error(f'Failed to open port {self.port}: {e}')
            raise e

    def listen(self):
        """
        Listens for the response from the Imon512 device.

        Returns:
            bytes: The response from the Imon512 device.

        """
        response = self.serial_port.readline()
        return response

    def get_temperature(self):
        """
        Retrieves the temperature data from the Imon512 device.

        Returns:
            float: The temperature value.

        """
        self.ask('temperature?')
        response = self.listen()
        response = response.decode().strip()
        self.temp = float(response)
        return self.temp

    def get_wavelength(self):
        """
        Retrieves the wavelength data from the Imon512 device.

        Returns:
            numpy.ndarray: An array containing the wavelength data.

        """
        return self.wl

    def ask(self, command: str, retries=0):
        """
        Send command to Imon512.

        Args:
            command (str): The command to be sent.
        """
        if self.serial_port is None or not self.serial_port.is_open:
            logger.error("Serial port is not open. Opening...")
            self.open()
        try:
            self.serial_port.reset_input_buffer()
            self.serial_port.reset_output_buffer()
        except (serial.SerialException, OSError) as e:
            logger.warning(f'Failed to flush buffers on {self.port}: {e}. Reopening port...')
            self.open()

        string = (command + '\r').encode()
        try:
            self.serial_port.write(string)
        except (serial.SerialException, AttributeError, OSError) as e:
            logger.error(f'Write failed on {self.port}: {e}. Retrying...')
            if retries > 2:
                raise ConnectionError(f'Max retries exceeded on write: {e}')
            self.ask(command, retries+1)

    def update_coefficients(self):
        """
        Reads the wavelength fit coefficients from unit flash memory.
        Updates the wl_param attribute.
        """
        self.ask('*rdusr2 0')
        resp = self.listen()

        wl_param = [None]*6
        for i in range(0,6):
            wl_param[i] = float(resp[(i*16):((i+1)*16)])
        return wl_param

    def update_temperature_coefficients(self):
        """
        Reads the temperature compensation coefficients from unit flash memory.
        Updates the tem_param attribute.
        """
        self.ask(f'*rdusr2 1')
        resp = self.listen()

        tem_param = [None]*4
        for i in range(0,4):
            tem_param[i] = float(resp[(i*16):((i+1)*16)])
        return tem_param

    def fit_wavelength(self, n_pix):
        """
        Fit pixels to wavelength.
        Updates the wavelength attribute.

        Args:
            n_pix (int): The number of pixels.

        """
        pix = np.arange(0, n_pix, dtype=float)
        wl = np.zeros_like(pix)
        for n, coef in enumerate(self.wl_param):
            wl += coef * pix ** float(n)
        self.wl = wl
        self.temperature_compensation()

    def temperature_compensation(self):
        """
        Compensates the wavelength data for temperature.
        Updates the wavelength attribute.

        """
        self.ask('*meas:temper')
        try:
            response = self.listen()
            logger.debug(f'Temp response: {response.decode()}')
            temp = float(response.decode().split('\t')[-1].split('\r')[0])
            
            self.temp = temp
            self.wl = (self.wl - self.tem_param[2] * temp - self.tem_param[2]) \
                      / (1 + self.tem_param[0] * temp + self.tem_param[1])
        except Exception as e:
            logger.error(f'erro ao compensar a temperatura: {e}')        

    def measure(self, n_mean=1, return_spectrum=True):
        """
        Measure the spectrum.
        
        Args:
            n_mean (int): The number of measurements to be averaged.
            return_spectrum (bool): If True, returns the spectrum data.
        
        Returns:
            numpy.ndarray: The spectrum data.
        """
        
        measurements = []
        self.fit_wavelength(510)
        self.ask('*meas:fstmeas')
        for i in range(0, n_mean):
            try:
                # Verifica se a porta e seus objetos internos estão válidos
                if (self.serial_port is not None and 
                hasattr(self.serial_port, 'is_open') and
                self.serial_port.is_open):
                    serialString = self.serial_port.read(size=2*510)
                else:
                    logger.error('Serial port or internal objects became invalid during measurement')
                    self.open()
                    serialString = self.serial_port.read(size=2*510)
            except (AttributeError, OSError, TypeError) as e:
                logger.error(f'Read error in measurement {i}: {e}. Reopening port...')
                self.open()
                # Aguarda um pouco para garantir que a porta está estável
                time.sleep(0.1)
                serialString = self.serial_port.read(size=2*510)
            values = self.bytes2adc(serialString, n=510)
            measurements.append(values[1::])
        self.ask('esc')
        measurements = np.array(measurements)
        measurements = 10*np.log10(np.abs(measurements)+1e-12)
        measurements = savgol_filter(measurements, 31, 2) # Suaviza o sinal para melhor detecção de picos

        if n_mean > 1:
            measurements = np.mean(measurements, axis=0)
        if return_spectrum:
            spectrum = np.stack((self.wl[1::], measurements), axis=1)
            return np.flipud(spectrum)
        else:
            return measurements
    
    def get_osa_trace(self):
        """
        Retrieves the OSA trace data.
        
        Returns:
            numpy.ndarray: The OSA trace data.
        """
        spec = self.measure(n_mean=10, return_spectrum=True)
        return spec

    @staticmethod
    def bytes2adc(streamed_bytes, n=512):
        """
        Convert bytes to ADC values.
        
        Args:
            streamed_bytes (bytes): The streamed bytes.
            n (int): The number of ADC values.
        
        Returns:
            list: The ADC values.
        """
        values = []
        for i in range(0, 2*n, 2):
            v = int.from_bytes(streamed_bytes[i:i + 2], byteorder='little')
            values.append(v)
        return values
    
    def set_exposure_time(self, et: int):
        """
        Sets the exposure time of the Imon512 device.

        Args:
            et (int): The exposure time in microseconds.

        """  
        self.ask(f'*para:fftpara 3000 {et} 0')
        logger.debug(f'Set integration time to {et} µs')

    def get_exposure_time(self) -> int:
        """
        Gets the exposure time of the Imon512 device.

        Returns:
            int: The exposure time in microseconds.

        """  
        self.ask('*para:fftpara?')
        response = self.listen()
        response = response.decode().strip()
        et = response.split('\t')[2]
        et = int(et.split('\r')[0])
        return et

class ThorLabsCCT:
    """
    Bridge class to access pyCCT and interact with Thorlabs Compact Spectrograph SDK.
    
    """

    def __init__(self, cct):
        self.cct = cct
        devices = self.cct.discover_devices()
        if not devices:
            raise RuntimeError("No Thorlabs Compact Spectrograph devices found.")
        try:
            self.device = self.cct.connect_to_device(devices[0])
        except Exception as e:
            raise RuntimeError(f"Failed to connect to device: {e}")

    def close(self):
        """
        Cleans up the device instance.
        """
        self.device = None

    def get_osa_trace(self):
        """
        Retrieves the OSA trace data from the Thorlabs Compact Spectrograph.

        Returns:
            numpy.ndarray: The OSA trace data.

        """
        if self.device is None:
            raise RuntimeError("Device not connected.")

        try:
            resp = self.device.acquire_single_spectrum()
            wl, intensities, exp_meas, ave_meas = resp
            intensities = savgol_filter(intensities, 101, 2, axis=0)
            spec = np.stack((wl, intensities), axis=1)
            return spec
        except Exception as e:
            raise RuntimeError(f"Failed to acquire spectrum: {e}")

    def get_exposure_time(self) -> int:
        """
        Gets the exposure time of the Thorlabs Compact Spectrograph.

        Returns:
            int: The exposure time in miliseconds.

        """  
        if self.device is None:
            raise RuntimeError("Device not connected.")
        try:
            et = self.device.get_manual_exposure()
            return et
        except Exception as e:
            raise RuntimeError(f"Failed to get exposure time: {e}")

    def set_exposure_time(self, et: float):
        """
        Sets the exposure time of the Thorlabs Compact Spectrograph.

        Args:
            et (float): The exposure time in miliseconds.

        """  
        if self.device is None:
            raise RuntimeError("Device not connected.")
        try:
            self.device.set_manual_exposure(et)
            logger.info(f"Exposure time set to {et} ms.")
        except Exception as e:
            raise RuntimeError(f"Failed to set exposure time: {e}")

class ThorLabs:
    """
    Class to access pyOSA and interact with Thorlabs OSA 20X.
    
    """

    def __init__(self, osa):
        self.device = osa
        try:
            self.device.setup(autogain=False)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize device: {e}")

    def close(self):
        """
        Cleans up the device instance.
        """
        self.osa = None

    def get_osa_trace(self):
        """
        Retrieves the OSA trace data from the Thorlabs OSA 20X.

        Returns:
            numpy.ndarray: The OSA trace data.

        """
        if self.device is None:
            raise RuntimeError("Device not connected.")

        try:
            resp = self.device.acquire(apodization='None', y_unit="dBm", ignore_errors=["Reference Warmup"])
            spectrum = resp[-1]["spectrum"]

            validity = spectrum.check_validity()
            if not validity["ref_laser_locked"]:
                raise RuntimeError("Reference laser is not locked")
            
            wl = spectrum.get_x()
            intensities = spectrum.get_y()
            intensities = savgol_filter(intensities, 101, 2, axis=0)
            spec = np.stack((wl, intensities), axis=1)
            return spec
        except Exception as e:
            raise RuntimeError(f"Failed to acquire spectrum: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)