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

    def __init__(self, host='10.0.0.150', port: int=3500, legacy_cmds=False):
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
        self.timeout = 2
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
            except PermissionError as e:
                logger.debug(f'Permission error closing socket on {self.host}:{self.port}, ignoring: {e}')
            except Exception as e:
                logger.warning(f'Error closing socket: {e}')
            finally:
                self.sock = None

    def open(self):
        """
        Opens a socket connection to the BraggMeter device.
        """
        last_error = None
        for attempt in range(3):
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
                return
            except Exception as e:
                self.sock = None
                if attempt < 2:
                    logger.warning(
                        f'Failed to open socket to {self.host}:{self.port} on attempt {attempt + 1}/3: {e}. Retrying...')
                    time.sleep(0.15)
                else:
                    logger.error(f'Failed to open socket to {self.host}:{self.port}: {e}')
                    raise ConnectionError(f'Failed to open socket: {e}') from e

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

    def get_osa_trace(self, n_mean: int=1, channel: int=0):
        """
        Retrieves the OSA trace data from the specified channel.

        Args:
            n_mean (int): The number of samples to average.
            channel (int): The channel number.

        Returns:
            numpy.ndarray: An array containing the wavelength and trace data.
            str: An warning message if the spectrum is saturated, otherwise None.
        """
        traces_db = []
        wl = None
        warn = None

        for _ in range(n_mean):
            resp = self.ask(f'trace{channel}')
            resp = resp.split(':')

            if self.legacy_cmds:
                pot = resp[-1]
                trace_raw = np.array([float(x) for x in pot.split(',')], dtype=float)
                wl = np.linspace(1500, 1600, len(trace_raw))
            else:
                pot, wl_str = resp[-2], resp[-1]
                hex_values = [pot[i:i+3] for i in range(0, len(pot), 3)]
                trace_raw = np.array([int(hex_value, 16) for hex_value in hex_values], dtype=float)
                wl = np.array([float(x) for x in wl_str.split(',')])

            if np.max(trace_raw) == 4095:
                warn = "Optical connector saturated."

            trace_raw *= -1
            traces_db.append(trace_raw)

        trace = np.array(traces_db)
        if n_mean > 1:
            trace = np.mean(trace, axis=0)
        else:
            trace = trace[0]

        spec = np.stack((wl, trace), axis=1)
        spec = np.flipud(spec)
        return spec, warn

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
        resp = self.ask(f'gain{channel}?')
        return resp

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
        last_error = None
        for attempt in range(3):
            try:
                # Fecha conexão existente antes de abrir uma nova
                if self.serial_port is not None:
                    logger.debug(f'Closing existing connection on {self.port} before reopening.')
                    try:
                        if hasattr(self.serial_port, 'is_open'):
                            self.serial_port.close()
                    except (OSError, AttributeError):
                        pass # Ignora erros ao verificar/fechar porta
                    self.serial_port = None

                self.serial_port = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=1)
                logger.info(f'Successfully opened port {self.port}')
                return
            except Exception as e:
                self.serial_port = None  # Garante que serial_port está None em caso de erro
                if attempt < 2:
                    logger.warning(f'Failed to open port {self.port} on attempt {attempt + 1}/3: {e}. Retrying...')
                    time.sleep(0.15)
                else:
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

    def ask(self, command: str, retries=2):
        """
        Send command to Imon512.

        Args:
            command (str): The command to be sent.
        """
        string = (command + '\r').encode()

        for attempt in range(retries + 1):
            if self.serial_port is None or not self.serial_port.is_open:
                logger.warning('Serial port is not open.')
                try:
                    self.open()
                except Exception as e:
                    logger.warning(f'Failed to open port {self.port} on attempt {attempt + 1}/{retries + 1}: {e}')
                    time.sleep(0.1)
                    continue

            try:
                self.serial_port.reset_input_buffer()
                self.serial_port.reset_output_buffer()
            except (serial.SerialException, OSError, AttributeError) as e:
                logger.warning(f'Failed to flush buffers on {self.port}: {e}. Reopening port...')
                self.close()
                time.sleep(0.05)
                continue

            try:
                self.serial_port.write(string)
                return True
            except (serial.SerialException, AttributeError, OSError) as e:
                if self.serial_port is not None:
                    logger.warning(
                        f'Write failed on {self.port} (attempt {attempt + 1}/{retries + 1}): {e}')
                    self.close()
                    time.sleep(0.1)

        logger.error(f'Unable to send command to {self.port} after {retries + 1} attempts: {command}')
        return False

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

    def temperature_compensation(self, retries: int=3):
        """
        Compensates the wavelength data for temperature.
        Updates the wavelength attribute.

        """
        temp = self.temp
        self.ask('*meas:temper')
        try:
            for _ in range(retries):
                response = self.listen()
                decoded = response.decode(errors='ignore')
                logger.debug(f'Temp response: {decoded}')
                try:
                    temp = float(decoded.split('\t')[-1].split('\r')[0].strip())
                    self.temp = temp
                    break
                except ValueError:
                    time.sleep(0.02)
                    continue
                except IndexError as e:
                    logger.warning(f'Failed to parse temperature response, using cached value: {e}')
            else:
                logger.warning('Temperature unavailable; skipping wavelength compensation.')
                return

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
            bool: Pixel count exceed the saturation threshold.
        """
        
        measurements = []
        warn = False
        self.fit_wavelength(510)
        self.ask('*meas:fstmeas')
        for i in range(0, n_mean):
            try:
                # Verifica se a porta e seus objetos internos estão válidos
                if (self.serial_port is not None and hasattr(self.serial_port, 'is_open')):
                    serialString = self.serial_port.read(size=2*510)
                else:
                    logger.error('Serial port or internal objects became invalid during measurement')
                    self.open()
                    serialString = self.serial_port.read(size=2*510)
            except (AttributeError, OSError, TypeError) as e:
                logger.error(f'Read error in measurement {i}: {e}. Reopening port...')
                self.open()
                serialString = self.serial_port.read(size=2*510)
            values, current_warn = self.bytes2adc(serialString, n=510)
            warn = warn or current_warn
            measurements.append(values[1::])
        self.ask('esc')
        measurements = np.array(measurements, dtype=float)
        if n_mean > 1:
            measurements = np.mean(measurements, axis=0)
        
        if return_spectrum:
            spectrum = np.stack((self.wl[1::], measurements), axis=1)
            return np.flipud(spectrum), warn
        else:
            return measurements
    
    def get_osa_trace(self, n_mean: int=1, *args):
        """
        Retrieves the OSA trace data.
        
        Returns:
            numpy.ndarray: The OSA trace data.
            str: An warning message if the spectrum is saturated, otherwise None.
        """
        spec, warn = self.measure(n_mean=n_mean, return_spectrum=True)
        warn = None if not warn else "Pixel count exceed the saturation threshold."
        return spec, warn

    @staticmethod
    def bytes2adc(streamed_bytes, n=512):
        """
        Convert bytes to ADC values.
        
        Args:
            streamed_bytes (bytes): The streamed bytes.
            n (int): The number of ADC values.
        
        Returns:
            list: The ADC values.
            bool: Pixel count exceed the saturation threshold.
        """
        values = []
        for i in range(0, 2*n, 2):
            v = int.from_bytes(streamed_bytes[i:i + 2], byteorder='little')
            values.append(v)
        warn = np.max(values) > 60000
        return values, warn

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

    def get_osa_trace(self, n_mean: int=1, *args):
        """
        Retrieves the OSA trace data from the Thorlabs Compact Spectrograph.

        Returns:
            numpy.ndarray: The OSA trace data.
            str: An warning message if the spectrum is saturated, otherwise None.

        """
        if self.device is None:
            raise RuntimeError("Device not connected.")

        try:
            err = not self.device.set_hardware_average(n_mean)
            resp = self.device.acquire_single_spectrum()
            wl, intensities, exp_meas, ave_meas = resp
            spec = np.stack((wl, intensities), axis=1)

            warn = None if not self.device.is_saturated() else "Spectrum is saturated."
            if err:
                warn = "Failed to set hardware average." if not warn else warn + " Failed to set hardware average."
            return spec, warn
        except Exception as e:
            raise RuntimeError(f"Failed to acquire spectrum: {e}")

    def get_exposure_time(self) -> int:
        """
        Gets the exposure time of the Thorlabs Compact Spectrograph.

        Returns:
            int: The exposure time in microseconds.

        """  
        if self.device is None:
            raise RuntimeError("Device not connected.")
        try:
            et = self.device.get_manual_exposure() * 1e3 # Convert from ms to µs
            return et
        except Exception as e:
            raise RuntimeError(f"Failed to get exposure time: {e}")

    def set_exposure_time(self, et: float):
        """
        Sets the exposure time of the Thorlabs Compact Spectrograph.

        Args:
            et (float): The exposure time in microseconds.

        """  
        if self.device is None:
            raise RuntimeError("Device not connected.")
        try:
            self.device.set_manual_exposure(et * 1e-3)  # Convert from µs to ms
            logger.info(f"Exposure time set to {et} µs.")
        except Exception as e:
            raise RuntimeError(f"Failed to set exposure time: {e}")

class ThorLabs:
    """
    Class to access pyOSA and interact with Thorlabs OSA 20X.
    
    """

    def __init__(self, osa):
        self.device = osa
        self.warming_error = False
        try:
            self.device.setup(autogain=False)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize device: {e}")

    def close(self):
        """
        Cleans up the device instance.
        """
        self.osa = None

    def get_osa_trace(self, n_mean: int=1, *args):
        """
        Retrieves the OSA trace data from the Thorlabs OSA 20X.

        Returns:
            numpy.ndarray: The OSA trace data.
            str: An warning message if the spectrum has validity issues, otherwise None.
        """
        if self.device is None:
            raise RuntimeError("Device not connected.")

        try:
            wl = None
            all_intensities = []
            warn_flags = {
                "ref_laser_locked": False,
                "interferogram_within_detector_range": False,
                "interferogram_is_linear": False,
                "autogain_satisfied": False,
            }

            for resp in self.device.acquire_continuous(number_of_acquisitions=n_mean,
                                                       apodization='None', y_unit="dBm",
                                                       ignore_errors=["Reference Warmup"]):
                spectrum = resp["spectrum"]
                wl = np.asarray(spectrum.get_x(), dtype=float)
                all_intensities.append(np.asarray(spectrum.get_y(), dtype=float))

                validity = spectrum.check_validity()
                warn_flags["ref_laser_locked"] |= not validity["ref_laser_locked"]
                warn_flags["interferogram_within_detector_range"] |= not validity["interferogram_within_detector_range"]
                warn_flags["interferogram_is_linear"] |= not validity["interferogram_is_linear"]
                warn_flags["autogain_satisfied"] |= not validity["autogain_satisfied"]

            if not all_intensities or wl is None:
                raise RuntimeError("No spectrum acquired.")

            intensities = np.asarray(all_intensities, dtype=float)
            if n_mean > 1:
                intensities = np.mean(intensities, axis=0)
            else:
                intensities = intensities[0]

            warn_messages = []
            if warn_flags["ref_laser_locked"]:
                warn_messages.append("Reference laser not locked")
            if warn_flags["interferogram_within_detector_range"]:
                warn_messages.append("Interferogram is clipped")
            if warn_flags["interferogram_is_linear"]:
                warn_messages.append("Interferogram is non-linear")
            if warn_flags["autogain_satisfied"]:
                warn_messages.append("Autogain was not finished adjusting")

            warn = ", ".join(warn_messages) if warn_messages else None
            spec = np.stack((wl, intensities), axis=1)
            return spec, warn
        except Exception as e:
            raise RuntimeError(f"Failed to acquire spectrum: {e}")
        
class SercaloSwitch:
    """
    Class to control Sercalo switch via serial and handle the acquisitions as a intermediary.
    
    """

    def __init__(self, port='COM3', baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_port = None
        self.open()

        try:
            self.ask(':iden?')
            if not self.ack():
                raise RuntimeError('Sercalo switch not found.')
        except Exception as e:
            logger.error(f'Communication error after opening port: {e}')
            raise e

    def close(self):
        if self.serial_port is not None:
            try:
                self.serial_port.close()
                logger.info(f'Successfully closed port {self.port}')
            except Exception as e:
                logger.warning(f'Error closing port {self.port}: {e}')
            finally:
                self.serial_port = None

    def open(self):
        for attempt in range(3):
            try:
                if self.serial_port is not None:
                    logger.debug(f'Closing existing connection on {self.port} before reopening.')
                    try:
                        self.serial_port.close()
                    except (OSError, AttributeError):
                        pass
                    self.serial_port = None

                self.serial_port = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=1)
                logger.info(f'Successfully opened port {self.port}')
                return
            except Exception as e:
                self.serial_port = None
                if attempt < 2:
                    logger.warning(f'Failed to open port {self.port} on attempt {attempt + 1}/3: {e}. Retrying...')
                    time.sleep(0.15)
                else:
                    logger.error(f'Failed to open port {self.port}: {e}')
                    raise e

    def ask(self, command: str, retries=1):
        if self.serial_port is None or not self.serial_port.is_open:
            logger.warning("Serial port is not open.")
            self.open()
        try:
            full_command = f'{command}\r\n'
            self.serial_port.write(full_command.encode())
            logger.debug(f'Sent command: {command}')

        except (serial.SerialException, AttributeError, OSError) as e:
            logger.error(f'Write failed on {self.port}: {e}. Retrying...')
            if retries > 2:
                raise ConnectionError(f'Max retries exceeded on write: {e}')
            self.ask(command, retries+1)

    def ack(self, timeout=3.0, retries=3):
        timeout += time.monotonic()

        for attempt in range(retries + 1):
            while time.monotonic() < timeout:
                if self.serial_port is None or not self.serial_port.is_open:
                    return -1
                response = self.serial_port.readline().decode(errors="ignore").strip()
                if response:
                    logger.debug(f'Received response: {response}')
                    if ':ack' in response:
                        return True
                    elif ':nack' in response:
                        return False

            if attempt < retries:
                logger.warning(
                    f'No response received from {self.port} within {timeout}s. '
                    f'Retrying {attempt + 1}/{retries}...')
                try:
                    self.serial_port.reset_input_buffer()
                except (serial.SerialException, OSError, AttributeError):
                    pass
                timeout += time.monotonic()

        raise TimeoutError(
            f'No response received on Sercalo switch on {self.port} after {retries+1} attempt(s).')

    def set_channel(self, channel: int):
        command = f':set-chan-{channel}'
        self.ask(command)
        if not self.ack():
            raise RuntimeError(f"Failed to set channel: {channel}")
        
    def get_channel(self, retries=2, settle_delay=0.05):
        for attempt in range(retries + 1):
            if settle_delay > 0:
                time.sleep(settle_delay)

            self.ask(':get-chan?')
            timeout = time.monotonic() + 3.0 # 3 seconds timeout
            response = []

            while time.monotonic() < timeout:
                if self.serial_port is None or not self.serial_port.is_open:
                    raise RuntimeError("Serial port is not open.")

                response.append(self.serial_port.readline().decode(errors="ignore").strip())
                if not response:
                    continue

                logger.debug(f'Received response: {response}')

                if ':ack' in response:
                    try:
                        channel_line = next(
                            line for line in reversed(response)
                            if line and ':ack' not in line and ':nack' not in line)
                        channel_str = channel_line.split(':')[-1].split(',')[0].strip()
                        return int(channel_str)
                    except StopIteration:
                        raise RuntimeError(f'Invalid channel response: {response}')
                    except ValueError as e:
                        logger.error(f'Failed to parse channel from response: {e}')
                        raise RuntimeError(f'Invalid channel response: {response}')

                if ':nack' in response:
                    logger.warning(f'Failed to get channel on attempt {attempt + 1}/{retries + 1}: {response}')
                    break

            if attempt < retries:
                time.sleep(0.05)

        raise RuntimeError(f'Failed to get channel after {retries + 1} attempt(s).')


class MultiSercaloSwitch:
    """
    Class to control multiple Sercalo switches simultaneously and ensure they are all commanded at the same time.

    """

    def __init__(self, ports: list[str]):
        """
        Initialize multiple Sercalo switches on the specified COM ports.
        
        Args:
            ports (list[str]): list of COM port for the Sercalo switches
        
        """
        if not ports:
            raise RuntimeError('No switch ports provided.')
        
        self.ports = ports
        self.switches: list[SercaloSwitch] = []
        
        # Inicializa todos os switches
        for port in ports:
            try:
                switch = SercaloSwitch(port=port)
                self.switches.append(switch)
                logger.info(f'Switch Sercalo initialized on port {port}')
            except Exception as e:
                # Fecha todos os switches já inicializados em caso de erro
                self.close()
                raise RuntimeError(f'Failed to initialize switch on port {port}: {e}')
    
    def close(self):
        """
        Close all Sercalo switches.

        """
        for switch in self.switches:
            try:
                switch.close()
            except PermissionError as e:
                logger.debug(f'Permission error closing switch on {switch.port}, ignoring: {e}')
            except Exception as e:
                logger.warning(f'Error closing switch: {e}')
        self.switches = []
    
    def set_channel(self, channel: int):
        """
        Define the channel on all switches simultaneously.
        
        Args:
            channel (int): Number of the channel to be configured
        
        """
        for switch in self.switches:
            try:
                switch.set_channel(channel)
            except Exception as e:
                raise RuntimeError(f'Failed to configure channel {channel} on switch {switch.port}: {e}')
    
    def get_channel(self):
        """
        Gets the channel from the first switch and validates that all are on the same channel.
        
        Returns:
            int: Number of the current channel
        
        """
        if not self.switches:
            raise RuntimeError('No switches available.')
        
        channels = []
        for switch in self.switches:
            try:
                if switch.serial_port is not None and switch.serial_port.is_open:
                    channel = switch.get_channel()
                    channels.append((switch.port, channel))
            except Exception as e:
                raise RuntimeError(f'Failed to get channel from switch {switch.port}: {e}')
        
        # Check if all channels are the same
        first_channel = channels[0][1]
        for port, channel in channels:
            if channel != first_channel:
                mismatched = [f'{p}: {c}' for p, c in channels]
                raise RuntimeError(
                    f'Switches unsynchronized. Channels detected: {", ".join(mismatched)}')

        return first_channel


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)