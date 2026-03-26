from PySide6.QtWidgets import QMainWindow, QFileDialog, QMessageBox, QApplication
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon

from ui.ConfigWindow_ui import Ui_ConfigWindow
from AnalysisWindow import AnalysisWindow

from serial.tools import list_ports
import h5py
import os

class ConfigWindow(QMainWindow, Ui_ConfigWindow):
    """
    Janela de configuração para análise em tempo real de sensores LPG.

    O usuário deve configurar:
    - Unidade do eixo X (comprimento de onda ou frequência).
    - Tipo de interface do sensor.
    - Porta de comunicação (serial ou TCP/IP).
    """
    def __init__(self):
        super().__init__()

        self.setupUi(self)
        self.retranslateUi(self)

        # --- Atributos da Classe ---
        # Mantém uma referência à janela de análise para evitar que ela seja
        # coletada pelo garbage collector e para garantir que apenas uma
        # instância seja aberta por vez.
        self.analysis_window: AnalysisWindow | None = None
        # Caminho do arquivo de dados selecionado pelo usuário.
        self.file_path: str | None = None
        # Instância compartilhada de PyCCT/OSA para evitar conflito de múltiplas instâncias
        self.osa = None

        self.setup_connections()
        self.update_imon_port()

    def setup_connections(self):
        """
        Conecta os sinais dos widgets (eventos) aos seus respectivos slots (métodos).
        """
        self.start_btn.clicked.connect(self.start_analysis)
        self.inter_combo.currentTextChanged.connect(self.set_port_options)
        self.refreshTimer = QTimer(self)
        self.refreshTimer.timeout.connect(self.update_imon_port)
        self.start_btn.setShortcut('Return') # Atalho do teclado

        self.inter_combo.addItems(['IBSEN IMON-512', 'BRAGGMETER FS22DI', 'BRAGGMETER FS22DI HBM', 'THORLABS CCT11', 'THORLABS OSA203'])

    def start_analysis(self):
        """
        Inicia a janela de análise com as configurações selecionadas.
        """
        QApplication.instance().setOverrideCursor(Qt.WaitCursor)

        inter = self.inter_combo.currentText()
        if self.osa is None:
            match inter:
                case 'THORLABS CCT11':
                    from sdk.pyCCT import PyCCT
                    self.osa = PyCCT()
                case 'THORLABS OSA203':
                    from sdk.pyOSA import pyOSA
                    self.osa = pyOSA.initialize()

        config = {
            'inter': inter,
            'range': (self.minNm_spin.value()*1e-9, self.maxNm_spin.value()*1e-9),
            'res': self.resPm_spin.value()*1e-12,
            'port': self.port_combo.currentText(),
            'ip': self.ip_lineEdit.text(),
            'path': self.file_path,
            'sdk': self.osa
        }

        for x in config.get('ip').split('.'):
            if not x.isdigit() or not 0 <= int(x) <= 255:
                QMessageBox.warning(self, "IP inválido", "O endereço IP inserido não é válido.")
                return 

        if self.analysis_window is None:
            self.analysis_window = AnalysisWindow()
            cur_dir = os.path.dirname(os.path.abspath(__file__))
            icon = os.path.join(cur_dir, "img", "logo.png")
            self.analysis_window.setWindowIcon(QIcon(icon))
            self.analysis_window.closing.connect(self.on_analysis_window_closed)
            self.analysis_window.load_config(config)
            self.analysis_window.show()
            self.hide()

    def on_analysis_window_closed(self):
        """
        Callback chamado quando a janela de análise é fechada.
        """
        self.analysis_window = None
        self.show()

    def bragg(self):
        self.refreshTimer.stop()
        self.com_lbl.setEnabled(True)
        self.port_combo.clear()
        self.port_combo.addItem('3500')
        self.port_combo.addItem('3365')
        self.port_combo.setEnabled(True)
        self.start_btn.setEnabled(True)
        self.ip_lbl.setEnabled(True)
        self.ip_lineEdit.setEnabled(True)

    def setSpins(self, min: int, max: int, minVal: int = None, maxVal: int = None):
        self.minNm_spin.setRange(min, max-1)
        self.maxNm_spin.setRange(min+1, max)
        if minVal:
            self.minNm_spin.setValue(minVal)
        else:
            self.minNm_spin.setValue(min)
        if maxVal:
            self.maxNm_spin.setValue(maxVal)
        else:
            self.maxNm_spin.setValue(max)

    def set_port_options(self, inter: str):
        """
        Ajusta as opções de porta com base no tipo de interface selecionado (serial ou TCP/IP).
        """
        match inter:
            case 'IBSEN IMON-512':
                self.ip_lbl.setEnabled(False)
                self.ip_lineEdit.setEnabled(False)
                self.com_lbl.setEnabled(True)
                self.setSpins(1510, 1595)
                self.update_imon_port()
                self.refreshTimer.start(1000)  # Atualiza as portas seriais a cada segundo
            case 'BRAGGMETER FS22DI':
                self.bragg()
                self.setSpins(1500, 1600)
                self.ip_lineEdit.setText("10.0.0.10")
            case 'BRAGGMETER FS22DI HBM':
                self.bragg()
                self.setSpins(1500, 1600)
                self.ip_lineEdit.setText("192.168.1.19")
            case 'THORLABS CCT11':
                self.ip_lbl.setEnabled(False)
                self.ip_lineEdit.setEnabled(False)
                self.com_lbl.setEnabled(False)
                self.port_combo.setEnabled(False)
                self.setSpins(350, 700)
                self.refreshTimer.stop()
            case 'THORLABS OSA203':
                self.ip_lbl.setEnabled(False)
                self.ip_lineEdit.setEnabled(False)
                self.com_lbl.setEnabled(False)
                self.port_combo.setEnabled(False)
                self.setSpins(1000, 2500, 1450, 1650)
                self.refreshTimer.stop()

    def update_imon_port(self):
        """
        Procura por portas seriais com o fabricante FTDI.
        """
        self.port_combo.clear()
        ports = list_ports.comports()
        ports = [port for port in ports if 'FTDI' in port.manufacturer]

        if not ports:
            self.port_combo.addItem("Dispositivo não encontrado")
            self.port_combo.setEnabled(False)
            self.start_btn.setEnabled(False)
        else:
            self.port_combo.setEnabled(True)
            self.start_btn.setEnabled(True)
            for port in ports:
                self.port_combo.addItem(port.device)