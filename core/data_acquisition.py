from PySide6.QtCore import Signal, QObject, QThread

import logging
import time
from serial.serialutil import SerialException

from core.hardware import Imon512, BraggMeter, ThorLabsCCT, ThorLabs, MultiSercaloSwitch

logger = logging.getLogger(__name__)

class DataAcquisition(QObject):
    """
    Classe responsável pela aquisição de dados dos dispositivos IMON512 e FS22DI.

    Args:
        inter (str): Modelo da interface.
        ip (str): Endereço IP do dispositivo (se aplicável).
        port (str): Porta de comunicação (número da porta serial ou TCP/IP, se aplicável).
        osa: Instância compartilhada de PyCCT/OSA para evitar conflito de múltiplas instâncias (se aplicável).
        switch_ports (list[str], opcional): Lista de portas dos switches Sercalo (se detectados) - pode haver múltiplos.

    """
    # Sinal para indicar que novos dados foram adquiridos
    data_acquired = Signal(list, str, int)  # spectrum, warn, channel
    # Sinal para indicar que a aquisição foi finalizada
    finished = Signal()
    # Sinal para indicar erro (para mostrar mensagem na thread principal)
    error_occurred = Signal(str, str)  # title, message

    def __init__(self, inter: str, ip: str, port: str, osa, switch_ports: list[str] | None = None):
        super().__init__()
        # Inicializa o dispositivo como None
        self.device: object | None = None
        self.switch: MultiSercaloSwitch | None = None
        self._stopping = False
        self._paused = False

        # Inicializa os parâmetros de porta e interface
        self.inter = inter
        self.ip = ip
        self.port = port
        self.osa = osa
        self.switch_ports = switch_ports if switch_ports else []

    def run(self):
        """
        Inicia a aquisição de dados com base na interface selecionada.

        """
        self._stopping = False
        self._paused = False

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
            if self.switch_ports:
                self.switch = MultiSercaloSwitch(self.switch_ports)
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
        # Se já está parando e não há mais recursos, nada a fazer.
        if self._stopping and self.device is None and self.switch is None:
            return

        self._stopping = True
        device = self.device
        switch = self.switch
        self.device = None
        self.switch = None

        try:
            logger.info(f"Fechando conexão com {self.inter}.")
            if switch is not None:
                switch.close()
            if device is not None:
                device.close()
            logger.info("Conexão fechada.")
        except AttributeError:
            logger.debug("Dispositivo já estava fechado ou não inicializado.")
        except Exception as e:
            logger.error(f"Erro ao fechar dispositivo: {e}")
        self.finished.emit()

    def request_data(self, n_mean: int, channel: int):
        """
        Solicita um novo conjunto de dados do dispositivo.
        
        Se houver múltiplos switches, sincroniza todos para o mesmo canal
        e valida que todos foram alterados corretamente.
        
        Args:
            n_mean (int): Número de amostras para média espectral.
            channel (int): Canal a ser lido (apenas para BraggMeter).

        """
        if self._stopping:
            return

        if self._paused:
            return

        if QThread.currentThread().isInterruptionRequested():
            return

        device = self.device
        switch = self.switch

        if not hasattr(self, 'device') or device is None:
            return

        try:
            if switch is not None:
                # Define o canal em todos os switches simultaneamente
                switch.set_channel(channel)

                # Dá tempo para o switch estabilizar antes da leitura de confirmação.
                time.sleep(0.05)

                # Valida que todos os switches foram alterados corretamente
                max_retries = 3
                cur_channel = -1
                for i in range(max_retries):
                    if switch is not None:
                        cur_channel = switch.get_channel()
                        if cur_channel == channel:
                            break                        
                        else:
                            switch.set_channel(channel)
                
                if cur_channel != channel and switch is not None:
                    raise Exception(f"Falha ao configurar canal {channel} em todos os switches Sercalo.")
                    
            spectrum, warn = device.get_osa_trace(n_mean, int(channel))
            if spectrum is not None and not self._stopping:
                self.data_acquired.emit(spectrum, warn, int(channel))
            else:
                logger.warning("Falha ao ler espectro ou espectro vazio.")
        except SerialException as e:
            if self._stopping:
                return
            logger.error(f"Dispositivo desconectado: {e}", exc_info=True)
            self.error_occurred.emit("Erro de Comunicação", f"A conexão com o dispositivo na porta {self.port} foi perdida.")
            self.stop()
            return
        except Exception as e:
            if self._stopping:
                return
            logger.error(f"Ocorreu um erro durante a execução: {e}", exc_info=True)
            self.error_occurred.emit("Erro inesperado", str(e))
            self.stop()
            return

    def pause(self):
        """
        Pausa temporariamente a aquisição sem fechar o dispositivo.

        """
        self._paused = True

    def resume(self):
        """
        Retoma a aquisição após uma pausa.

        """
        if not self._stopping:
            self._paused = False

    def set_exposure_time(self, et: float):
        """
        Altera o tempo de exposição.
        Args:
            et (float): Novo tempo de exposição.
            
        """
        if not self._stopping and hasattr(self, 'device') and self.device is not None:
            self.device.set_exposure_time(et)
            logger.info(f"Tempo de exposição alterado para {et}.")

    def get_exposure_time(self) -> int:
        """
        Returns:
            int: o tempo de exposição atual.

        """
        if not self._stopping and hasattr(self, 'device') and self.device is not None:
            et = self.device.get_exposure_time()
            logger.info(f"Tempo de exposição atual: {et}.")
            return et
        return 0