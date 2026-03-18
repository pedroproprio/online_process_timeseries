from PySide6.QtWidgets import QMainWindow, QFileDialog, QMessageBox

from ui.ConfigWindow_ui import Ui_ConfigWindow
from AnalysisWindow import AnalysisWindow

from serial.tools import list_ports
import h5py

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
        self.file_path: str = "None"

        self.setup_connections()
        self.update_serial_ports()

    def setup_connections(self):
        """
        Conecta os sinais dos widgets (eventos) aos seus respectivos slots (métodos).
        """
        self.start_btn.clicked.connect(self.start_analysis)
        self.refresh_btn.clicked.connect(self.update_serial_ports)
        self.inter_combo.currentTextChanged.connect(self.set_port_options)
        self.load_btn.clicked.connect(self.load_file)

        self.inter_combo.addItems(['IBSEN IMON-512', 'BRAGGMETER FS22DI', 'BRAGGMETER FS22DI HBM', 'THORLABS CCT11', 'THORLABS OSA203'])
        self.unit_combo.addItems(['nm', 'µm', 'm'])

    def start_analysis(self):
        """
        Inicia a janela de análise com as configurações selecionadas.
        """
        config = {
            'x_unit': self.unit_combo.currentText(),
            'inter': self.inter_combo.currentText(),
            'port': self.port_combo.currentText(),
            'ip': self.ip_lineEdit.text(),
            'path': self.file_path
        }

        for x in config.get('ip').split('.'):
            if not x.isdigit() or not 0 <= int(x) <= 255:
                QMessageBox.warning(self, "IP inválido", "O endereço IP inserido não é válido.")
                return 

        if self.analysis_window is None:
            self.analysis_window = AnalysisWindow()
            self.analysis_window.closing.connect(self.on_analysis_window_closed)
            self.analysis_window.load_config(config)
            self.analysis_window.show()
            self.hide()

    def load_file(self):
        """
        Abre um diálogo para seleção de arquivo e armazena o caminho selecionado.
        """
        self.file_path_lbl.setText("")
        file_dialog = QFileDialog(self, "Selecione o arquivo de dados", "*.h5")
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.file_path = selected_files[0]
        else:
            return # Usuário cancelou a seleção de arquivo

        # Verifica se o arquivo selecionado é válido
        try:
            inter = self.inter_combo.currentText()
            with h5py.File(self.file_path, "r") as f:
                if inter not in f:
                    QMessageBox.warning(
                        self,
                        "Arquivo inválido",
                        f"O arquivo HDF5 não contém o grupo da interface selecionada: {inter}."
                    )
                    self.file_path = "None"
                    return

                g = f[inter]
                required = ["Amostra", "ComprimentoRessonante"]
                if any(dataset not in g for dataset in required):
                    QMessageBox.warning(
                        self,
                        "Arquivo inválido",
                        "O grupo da interface deve conter os datasets 'Amostra' e 'ComprimentoRessonante'."
                    )
                    self.file_path = "None"
                    return

            self.file_path_lbl.setText(f"Arquivo carregado de: {self.file_path}")
        except Exception as e:
            self.file_path = "None"
            QMessageBox.warning(self, "Arquivo inválido", f"Falha ao abrir arquivo HDF5: {e}")

    def on_analysis_window_closed(self):
        """
        Callback chamado quando a janela de análise é fechada.
        """
        self.analysis_window = None
        self.show()

    def bragg(self):
        self.refresh_btn.setEnabled(False)
        self.com_lbl.setEnabled(True)
        self.port_combo.clear()
        self.port_combo.addItem('3500')
        self.port_combo.addItem('3365')
        self.port_combo.setEnabled(True)
        self.start_btn.setEnabled(True)
        self.ip_lbl.setEnabled(True)
        self.ip_lineEdit.setEnabled(True)

    def set_port_options(self, inter: str):
        """
        Ajusta as opções de porta com base no tipo de interface selecionado (serial ou TCP/IP).
        """
        match inter:
            case 'IBSEN IMON-512':
                self.refresh_btn.setEnabled(True)
                self.ip_lbl.setEnabled(False)
                self.ip_lineEdit.setEnabled(False)
                self.com_lbl.setEnabled(True)
                self.update_serial_ports()
            case 'BRAGGMETER FS22DI':
                self.bragg()
                self.ip_lineEdit.setText("10.0.0.10")
            case 'BRAGGMETER FS22DI HBM':
                self.bragg()
                self.ip_lineEdit.setText("192.168.1.19")
            case 'THORLABS CCT11':
                self.ip_lbl.setEnabled(False)
                self.ip_lineEdit.setEnabled(False)
                self.refresh_btn.setEnabled(False)
                self.com_lbl.setEnabled(False)
                self.port_combo.setEnabled(False)

    def update_serial_ports(self):
        """
        Atualiza a lista de portas seriais disponíveis no sistema.
        """
        self.port_combo.clear()
        ports = list_ports.comports()

        if not ports:
            self.port_combo.addItem("Nenhuma porta serial encontrada")
            self.port_combo.setEnabled(False)
            self.start_btn.setEnabled(False)
        else:
            self.port_combo.setEnabled(True)
            self.start_btn.setEnabled(True)
            for port in ports:
                self.port_combo.addItem(port.device)