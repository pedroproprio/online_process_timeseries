from PySide6.QtCore import Signal, QObject

import logging
from serial.serialutil import SerialException

from Hardware import Imon512, BraggMeter, ThorLabsCCT, ThorLabs

logger = logging.getLogger(__name__)

class DataAcquisition(QObject):
    """
    Classe responsável pela aquisição de dados dos dispositivos IMON512 e FS22DI.

    Args:
        port (str): Porta de comunicação (número da porta serial ou TCP/IP).
        ip (str): Endereço IP do dispositivo (apenas para BraggMeter).
        inter (str): Tipo de interface do sensor.

    """
    # Sinal para indicar que novos dados foram adquiridos
    data_acquired = Signal(list, str)  # spectrum, warn
    # Sinal para indicar que a aquisição foi finalizada
    finished = Signal()
    # Sinal para indicar erro (para mostrar mensagem na thread principal)
    error_occurred = Signal(str, str)  # title, message

    def __init__(self, inter: str, ip: str, port: str, osa):
        super().__init__()
        # Inicializa o dispositivo como None
        self.device: object | None = None

        # Inicializa os parâmetros de porta e interface
        self.inter = inter
        self.ip = ip
        self.port = port
        self.osa = osa

    def run(self):
        """
        Inicia a aquisição de dados com base na interface selecionada.

        """
        if hasattr(self, 'device') and self.device is not None:
            self.stop()
            
        try:
            match self.inter:
                case 'IBSEN IMON-512':
                    self.device = Imon512(port=self.port)
                case 'BRAGGMETER FS22DI':
                    self.device = BraggMeter(self.ip, int(self.port), True)
                case 'BRAGGMETER FS22DI HBM':
                    self.device = BraggMeter(self.ip, int(self.port), False)
                case 'THORLABS CCT11':
                    self.device = ThorLabsCCT(cct=self.osa)
                case 'THORLABS OSA203':
                    self.device = ThorLabs(osa=self.osa)
                case _:
                    logger.error(f"Interface desconhecida: {self.inter}")
                    self.error_occurred.emit("Erro", f"Interface desconhecida: {self.inter}")
                    self.finished.emit()
                    return
        except PermissionError as e:
            logger.error(f"Permissão negada ao abrir porta {self.port}. {e}")
            self.error_occurred.emit("Erro", f"Permissão negada ao abrir porta {self.port}. Certifique-se que a porta não está em uso.")
            self.finished.emit()
            self.device = None
            return
        except Exception as e:
            logger.error(f"Erro ao inicializar o {self.inter}: {e}")
            self.error_occurred.emit("Erro", f"Falha ao inicializar o {self.inter}.")
            self.finished.emit()
            self.device = None
            return

    def stop(self):
        """
        Encerra a aquisição de dados e fecha a conexão com o dispositivo.

        """
        try:
            logger.info(f"Fechando conexão com {self.inter}.")
            self.device.close()
            logger.info("Conexão fechada.")
        except AttributeError:
            logger.debug("Dispositivo já estava fechado ou não inicializado.")
        except Exception as e:
            logger.error(f"Erro ao fechar dispositivo: {e}")
        finally:
            self.device = None
        self.finished.emit()

    def request_data(self, n_mean: int, channel: int):
        """
        Solicita um novo conjunto de dados do dispositivo.
        Args:
            n_mean (int): Número de amostras para média espectral.
            channel (int): Canal a ser lido (apenas para BraggMeter).

        """
        if not hasattr(self, 'device') or self.device is None:
            logger.error("Dispositivo não inicializado.")
            self.finished.emit()
            return
        try:
            spectrum, warn = self.device.get_osa_trace(n_mean, int(channel))
            if spectrum is not None:
                self.data_acquired.emit(spectrum, warn)
            else:
                logger.warning("Falha ao ler espectro ou espectro vazio.")
        except SerialException as e:
            logger.error(f"Dispositivo desconectado: {e}", exc_info=True)
            self.error_occurred.emit("Erro de Comunicação", f"A conexão com o dispositivo na porta {self.port} foi perdida.")
            self.stop()
            return
        except Exception as e:
            logger.error(f"Ocorreu um erro durante a execução: {e}", exc_info=True)
            self.error_occurred.emit("Erro inesperado", str(e))
            self.stop()
            return

    def set_exposure_time(self, et: float):
        """
        Altera o tempo de exposição.
        Args:
            et (float): Novo tempo de exposição.
        """
        if hasattr(self, 'device') and self.device is not None:
            self.device.set_exposure_time(et)
            logger.info(f"Tempo de exposição alterado para {et}.")

    def get_exposure_time(self) -> int:
        """
        Retorna o tempo de exposição atual.

        """
        if hasattr(self, 'device') and self.device is not None:
            et = self.device.get_exposure_time()
            logger.info(f"Tempo de exposição atual: {et}.")
            return et
        return 0