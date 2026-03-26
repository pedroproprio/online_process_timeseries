from PySide6.QtWidgets import (QMainWindow, QFileDialog, QMessageBox, QGraphicsRectItem, QInputDialog, 
    QDialog, QPushButton, QMenu, QApplication, QFormLayout, QSpinBox, QDialogButtonBox, QLineEdit, QCompleter)
from PySide6.QtGui import QColor, QLinearGradient, QBrush, QIcon, QPalette, QGradient
from PySide6.QtCore import Signal, QThread, QTimer, Qt

from ui.AnalysisWindow_ui import Ui_AnalysisWindow
from processing import find_resonant_wavelength
from DataAcquisition import DataAcquisition

from scipy.signal import windows, savgol_filter, find_peaks
from scipy.interpolate import interp1d
from datetime import datetime
import pyqtgraph as pg
import numpy as np
import webbrowser
import h5py
import os

from lib.PyQtDarkTheme import qdarktheme

import logging
logger = logging.getLogger(__name__)

class AnalysisWindow(QMainWindow, Ui_AnalysisWindow):
    """
    Janela de Análise Interativa.

    Nesta tela, é feita a leitura e exibição dos dados espectrais. O usuário
    pode interagir com os gráficos para selecionar a região de interesse,
    visualizar os picos detectados em uma variação ao longo do tempo ou
    em um box plot.
    
    """
    # Sinal para indicar à ConfigWindow que esta janela está sendo fechada
    closing = Signal()
    request_data_signal = Signal(int, int)

    def __init__(self):
        super().__init__()

        # Configura a interface do usuário definida no Qt Designer
        self.setupUi(self)
        self.retranslateUi(self)

        # --- Atributos da Classe ---
        # Dicionário para armazenar as configurações recebidas da MainWindow
        self.config_data: dict | None = None
        # Lista para armazenar os dados dos espectros lidos
        # Formato: [(wavelength_array, power_array), ...]
        self.spectra_data: list | None = None
        # Objeto para a Região de Interesse (ROI) no gráfico
        self.roi_region: pg.LinearRegionItem | None = None
        # Objeto para a Região de Interesse (ROI) dos dados processados (no gráfico temporal)
        self.temporal_roi_region: pg.LinearRegionItem | None = None
        # Limites da ROI para o processamento de picos
        self.roi_range: list | None = None
        # Comprimentos de onda fixos para interpolação (em metros)
        self.fixed_wavelengths: np.ndarray | None = None
        # Dicionário de listas para armazenar os resultados processados
        self.results_df = {'Timestamp': [], 'Intensidade': [], 'Vale': []}
        # Dicionário com os dados das amostras para o box plot
        self.samples = {}
        # Tempo de exposição (µs)
        self.exposure_time: float = 0.0
        # Flag para impedir múltiplas legendas no box plot
        self._add_legend: bool = True
        # Intervalo entre amostras (ms)
        self.sample_rate: int = 800
        # Duração da amostra contínua (s)
        self.sample_duration: int | None = None
        # Nome da amostra contínua
        self.sample_name: str | None = None
        # Timer para parar a aquisição contínua
        self.continuous_timer: QTimer | None = None
        # Timer para flush periódico dos dados no modo contínuo
        self.flush_timer: QTimer | None = None
        # Buffer para salvar em lote no modo contínuo
        self.pending_hdf5 = {'Timestamp': [], 'Intensidade': [], 'Vale': []}
        # Tamanho do lote para flush no modo contínuo
        self.flush_batch_size: int = 25
        # Intervalo para flush automático no modo contínuo (ms)
        self.flush_interval_ms: int = 5000
        # Limite de pontos mantidos em memória para evitar lentidão da UI
        self.max_live_points: int = 5000
        # Unidade do eixo x (comprimento de onda)
        self.xUnit: str = 'nm'
        # Unidade fixa para temporal/boxplot (não muda com actions de unidade)
        self.resultUnit: str = 'nm'
        # Tema atual da interface
        self.theme: str = qdarktheme.get_theme()
        self.theme_colors = {}
        # Dicionário para armazenar os espectros fixados
        self.fixed_traces = {}
        # Botão de aviso (criado dinamicamente em _show_warning)
        self.warning_btn: QPushButton | None = None
        # Flag para indicar se a aquisiçao está ativa
        self._running: bool = False
        # Caminho para o arquivo de dados selecionado pelo usuário
        self.file_path: str | None = None
        # Lista com as mensagens de erro recebidas
        self.error_messages: list = []

        # Método de apodização aplicado no plot (None desabilita)
        self.apodization: str | None = None
        self.apodization_methods = {
            'Tukey': lambda m, *a: windows.tukey(m, sym=False),
            'Triangular': lambda m, *a: windows.triang(m, sym=False),
            'Taylor': lambda m, *a: windows.taylor(m, sym=False),
            'Parzen': lambda m, *a: windows.parzen(m, sym=False),
            'Nuttall': lambda m, *a: windows.nuttall(m, sym=False),
            'Lanczos': lambda m, *a: windows.lanczos(m, sym=False),
            'Hann': lambda m, *a: windows.hann(m, sym=False),
            'Hamming': lambda m, *a: windows.hamming(m, sym=False),
            'Gaussian': lambda m, std: windows.gaussian(m, std, sym=False),
            'Flat top': lambda m, *a: windows.flattop(m, sym=False),
            'Cosine': lambda m, *a: windows.cosine(m, sym=False),
            'Boxcar': lambda m, *a: windows.boxcar(m, sym=False),
            'Bohman': lambda m, *a: windows.bohman(m, sym=False),
            'Blackman-Harris 4-term': lambda m, *a: windows.blackmanharris(m, sym=False),
            'Blackman': lambda m, *a: windows.blackman(m, sym=False),
            'Bartlett': lambda m, *a: windows.bartlett(m, sym=False),
            'Bartlett-Hann': lambda m, *a: windows.barthann(m, sym=False),
        }
        # Parametros do filtro Savitzky-Golay aplicados no plot (None desabilita)
        self.savgol_window_points: int = 51
        self.savgol_polyorder: int = 2
        # Numero de amostras para o filtro de média espectral
        self.mean_samples: int = 1

        # Thread e worker para aquisição de dados
        self.thread: QThread | None = None
        self.worker: DataAcquisition | None = None
        #Timer para solicitar dados periodicamente
        self.timer: QTimer | None = None
        # Flag para evitar chamadas concorrentes de _cleanup_thread
        self._is_stopping = False
        
        # Instância compartilhada de PyCCT/OSA para evitar conflito de múltiplas instâncias
        self.osa = None

        self.set_theme(self.theme) # Aplica o tema inicial
        self.actionNm.setChecked(True) # Define nm como unidade inicial do eixo X
        self.setup_plot()
        self.setup_connections()

    def setup_plot(self):
        """
        Configura os widgets de gráfico da pyqtgraph.
        
        """
        # --- Configuração do gráfico: Espectro ---
        self.spectraPlotWidget.setLabel('left', 'Potência', units='dBm')
        self.spectraPlotWidget.showGrid(x=False, y=True)
        xAxis = pg.AxisItem(orientation='bottom')
        xAxis.setLabel(text='Comprimento de Onda', units='nm')
        xAxis.enableAutoSIPrefix(False) # Mantém unidades em nm
        self.spectraPlotWidget.setAxisItems({'bottom': xAxis})

        # Adiciona a região de seleção (ROI)
        self.roi_region = pg.LinearRegionItem(orientation=pg.LinearRegionItem.Vertical)
        self.roi_region.setBrush(self.theme_colors['roi_spec'])
        self.spectraPlotWidget.addItem(self.roi_region)

        # --- Configuração do gráfico: Evolução Temporal ---
        self.temporalPlotWidget.setLabel('bottom', 'Timestamp')
        self.temporalPlotWidget.showGrid(x=False, y=True)
        self.temporalPlotWidget.setAxisItems({'bottom': pg.DateAxisItem()})
        yAxis = pg.AxisItem(orientation='left')
        yAxis.setLabel(text='Comprimento de Onda', units='nm')
        yAxis.enableAutoSIPrefix(False) # Mantém unidades em nm
        self.temporalPlotWidget.setAxisItems({'left': yAxis})

        # Adiciona a região de seleção (ROI) para o gráfico temporal
        self.temporal_roi_region = pg.LinearRegionItem(orientation=pg.LinearRegionItem.Vertical, brush=(0, 255, 0, 30))

        # --- Configuração do gráfico: Box Plot ---
        self.boxPlot = self.boxPlotWidget.addPlot()
        self.boxLegend = self.boxPlot.addLegend()
        self.boxPlot.setXRange(0, 2)
        self.boxPlot.getAxis('bottom').setTicks([]) # Remove os números do eixo X

        #Ícones dos botões
        cur_dir = os.path.dirname(__file__)
        apo = os.path.join(cur_dir, "img", "apodization.png")
        self.apodization_btn.setIcon(QIcon(apo))
        svg = os.path.join(cur_dir, "img", "savgol.png")
        self.savgol_btn.setIcon(QIcon(svg))
        mean = os.path.join(cur_dir, "img", "mean.png")
        self.mean_btn.setIcon(QIcon(mean))

    def setup_connections(self):
        """
        Conecta os sinais dos widgets (eventos) aos seus respectivos slots (métodos).
        
        """
        self.stop_btn.clicked.connect(self.toggle_thread) # Inicia/Para a aquisição de dados
        self.save_btn.clicked.connect(self.save_data) # Salva os dados processados
        self.clear_btn.clicked.connect(self.clear_plot) # Limpa os gráficos
        self.apodization_btn.clicked.connect(self.select_apodization_method)
        self.savgol_btn.clicked.connect(self.select_savgol_parameters)
        self.mean_btn.clicked.connect(self.select_mean_samples)
        self.temporal_roi_region.sigRegionChanged.connect(self.roi_changed) # Atualiza o box plot mesmo com a aquisição parada
        
        # Botões de fixar um espectro
        for button in self._list_fix_buttons():
            button.setContextMenuPolicy(Qt.CustomContextMenu)
            button.customContextMenuRequested.connect(lambda pos, btn=button: self.toggle_fix(btn, pos))
            button.clicked.connect(lambda b, btn=button: self.fix_btn_clicked(btn, btn.isChecked()))

        self.actionM.triggered.connect(lambda checked: checked and self.unit_changed('m'))
        self.actionUm.triggered.connect(lambda checked: checked and self.unit_changed('um'))
        self.actionNm.triggered.connect(lambda checked: checked and self.unit_changed('nm'))
        self.actionPm.triggered.connect(lambda checked: checked and self.unit_changed('pm'))
        self.actionLight.triggered.connect(lambda checked: checked and self.set_theme('light'))
        self.actionDark.triggered.connect(lambda checked: checked and self.set_theme('dark'))
        self.actionHelp.triggered.connect(lambda: webbrowser.open('https://github.com/pedroproprio/online_process_timeseries'))
        self.actionOpenFile.triggered.connect(self.select_file)
        self.actionNewWindow.triggered.connect(self.open_new_window)

        # Conecta atalhos do teclado
        self.actionOpenFile.setShortcut('Ctrl+A')
        self.actionNewWindow.setShortcut('Ctrl+N')
        self.stop_btn.setShortcut('Space')
        self.clear_btn.setShortcut('Ctrl+L')
        self.save_btn.setShortcut('Ctrl+S')
        self.continuous_chk.setShortcut('Ctrl+M')
        self.apodization_btn.setShortcut('A')
        self.savgol_btn.setShortcut('S')
        self.mean_btn.setShortcut('M')
        for i, button in enumerate(self._list_fix_buttons()):
            button.setShortcut(f'{i+1}') # Atalhos 1-6 para fixar espectros

    def _unit_to_meter_factor(self, unit: str) -> float:
        factors = {
            'm': 1.0,
            'um': 1e-6,
            'nm': 1e-9,
            'pm': 1e-12,
        }
        return factors.get(unit, 1e-9)

    def _set_spectrum_axis_unit(self):
        unit_label = {
            'm': 'm',
            'um': 'μm',
            'nm': 'nm',
            'pm': 'pm',
        }.get(self.xUnit, 'nm')
        self.spectraPlotWidget.setLabel('bottom', units=unit_label)

    def _from_meter(self, values, unit: str):
        return np.asarray(values, dtype=float) / self._unit_to_meter_factor(unit)

    def select_apodization_method(self):
        items = [*self.apodization_methods.keys(), 'None']
        current_item = self.apodization if self.apodization is not None else 'None'
        current_index = items.index(current_item)

        selected, accepted = QInputDialog.getItem(
            self,
            'Apodização',
            'Selecione o método:',
            items,
            current_index,
            False,
        )
        if not accepted:
            return

        self.apodization = None if selected == 'None' else selected
        logger.info(f" Método de apodização selecionado: {self.apodization or 'None'}")

        if self.spectra_data:
            x, y = zip(*self.spectra_data)
            self._plot_spectrum_curve(np.asarray(x, dtype=float), np.asarray(y, dtype=float))

    def _apodize_plot_data(self, y_values: np.ndarray):
        if self.apodization is None:
            return y_values

        method = self.apodization_methods.get(self.apodization)
        if method is None:
            return y_values

        try:
            window = method(y_values.size, np.std(y_values))
            window /= np.mean(window)
            y_apodized = y_values * window
            return y_apodized
        except Exception as exc:
            logger.error(f"Erro ao aplicar apodizacao '{self.apodization}': {exc}")
            return y_values

    def select_savgol_parameters(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Filtro Savitzky-Golay')

        layout = QFormLayout(dialog)

        window_spin = QSpinBox(dialog)
        window_spin.setRange(3, 500)
        window_spin.setSingleStep(2)
        window_spin.setValue(self.savgol_window_points)

        poly_spin = QSpinBox(dialog)
        poly_spin.setRange(1, 99)
        poly_spin.setValue(self.savgol_polyorder)

        layout.addRow('Tamanho da janela:', window_spin)
        layout.addRow('Grau do polinômio:', poly_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dialog)
        layout.addRow(buttons)

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec() != QDialog.Accepted:
            return

        window_points = int(window_spin.value())
        polyorder = int(poly_spin.value())

        if window_points % 2 == 0:
            window_points -= 1

        if polyorder >= window_points:
            QMessageBox.warning(self, 'Filtro Savitzky-Golay', 'O grau do polinômio deve ser menor que o número de pontos da janela.')
            return

        self.savgol_window_points = window_points
        self.savgol_polyorder = polyorder
        logger.info(f"Filtro Savitzky-Golay configurado: janela={self.savgol_window_points}, polinômio={self.savgol_polyorder}")

        if self.spectra_data:
            x, y = zip(*self.spectra_data)
            self._plot_spectrum_curve(np.asarray(x, dtype=float), np.asarray(y, dtype=float))

    def select_mean_samples(self):
        value, accepted = QInputDialog.getInt(
            self,
            'Média espectral',
            'Número de espectros:',
            self.mean_samples,
            1,
            1000,
            1,
        )
        if not accepted:
            return

        self.mean_samples = int(value)
        logger.info(f"Número de amostras para mean configurado: {self.mean_samples}")

    def _visible_spectrum_brush(self, x_values: np.ndarray):
        if x_values.size == 0:
            return None

        x_min = float(np.min(x_values))
        x_max = float(np.max(x_values))
        if x_max <= x_min:
            return None

        visible_min = float(self._from_meter(np.array([380e-9]), self.xUnit)[0])
        visible_max = float(self._from_meter(np.array([730e-9]), self.xUnit)[0])

        span = x_max - x_min

        spectrum_stops_nm = [
            (380, '#6a00ff'),
            (440, '#0047ff'),
            (490, '#00c8ff'),
            (510, '#00ff7f'),
            (580, '#ffff00'),
            (640, '#ff7f00'),
            (730, '#ff0000'),]

        gradient = QLinearGradient(x_min, 0.0, x_max, 0.0)
        gradient.setCoordinateMode(QGradient.LogicalMode)

        # Fora do visível = transparente
        transparent = QColor(0, 0, 0, 0)

        start_rel = (visible_min - x_min) / span
        end_rel = (visible_max - x_min) / span

        eps = 1e-9

        gradient.setColorAt(0.0, transparent)
        gradient.setColorAt(max(0.0, start_rel - eps), transparent)

        # Espectro visível
        for wl_nm, color_hex in spectrum_stops_nm:
            wl = float(self._from_meter(np.array([wl_nm * 1e-9]), self.xUnit)[0])
            rel = (wl - x_min) / span

            if 0.0 <= rel <= 1.0:
                gradient.setColorAt(rel, QColor(color_hex))

        gradient.setColorAt(min(1.0, end_rel + eps), transparent)
        gradient.setColorAt(1.0, transparent)

        return QBrush(gradient)

    def _plot_spectrum_curve(self, x_values: np.ndarray, y_values: np.ndarray):
        """
        Plota o(s) espectro(s) e um preenchimento colorido para a faixa visível.
        
        """
        self.spectraPlotWidget.clear()
        self.spectraPlotWidget.addItem(self.roi_region)

        y_values = self._preprocess_plot_data(y_values)

        brush = self._visible_spectrum_brush(x_values)
        plot_kwargs = {'pen': pg.mkPen(self.theme_colors['spectrum'], width=1),}
        if brush is not None:
            plot_kwargs['fillLevel'] = float(np.min(y_values))
            plot_kwargs['brush'] = brush

        self.spectraPlotWidget.plot(x_values, y_values, **plot_kwargs)

        for button in self._list_fix_buttons():
            if button.isChecked():
                if str(button) not in self.fixed_traces:
                    continue
                color = button.palette().color(QPalette.ColorRole.Button)
                x = self.fixed_traces[str(button)][0]
                y = self._preprocess_plot_data(self.fixed_traces[str(button)][1])
                self.spectraPlotWidget.plot(x, y, pen=pg.mkPen(color, width=1))

    def _preprocess_plot_data(self, y_values: np.ndarray) -> np.ndarray:
        y_values = self._apodize_plot_data(y_values)
        y_values = savgol_filter(y_values, self.savgol_window_points, self.savgol_polyorder)
        return y_values

    def _list_fix_buttons(self) -> list:
        buttons = []
        for i in range(self.fixedTraces_vlay.count()):
            item = self.fixedTraces_vlay.itemAt(i)
            widget = item.widget()
            if isinstance(widget, QPushButton):
                buttons.append(widget)
        return buttons

    def set_theme(self, theme: str):
        """
        Aplica tema claro/escuro para widgets Qt e gráficos pyqtgraph.
        """
        if theme not in ('light', 'dark'):
            return

        self.theme = theme
        if theme == 'dark':
            self.theme_colors = {
                'plot_bg': '#0b1220',
                'axis': '#e5e7eb',
                'roi_spec': '#64a5fa3c',
                'roi_temp': '#4bdca037',
                'spectrum': '#19867d',
                'accent': "#961313",}
        else:
            self.theme_colors = {
                'plot_bg': '#ffffffff',
                'axis': '#1f2937',
                'roi_spec': '#2864eb32',
                'roi_temp': '#19a04b2d',
                'spectrum': '#17bdaf',
                'accent': '#961313',}

        self.actionLight.setChecked(theme == 'light')
        self.actionDark.setChecked(theme == 'dark')

        QApplication.instance().setStyleSheet(qdarktheme.load_stylesheet(theme))

        btn_colors =         [QColor(139, 0, 0),
                              QColor(0, 152, 0),
                              QColor(0, 0, 188),
                              QColor(255, 170, 0),
                              QColor(4, 150, 143),
                              QColor(144, 1, 124),]
        btn_colors_checked = [QColor(139, 50, 50),
                              QColor(90, 152, 90),
                              QColor(70, 70, 188),
                              QColor(200, 169, 106),
                              QColor(109, 150, 148),
                              QColor(119, 66, 124),]
        
        for i, button in enumerate((self._list_fix_buttons())):
            color = btn_colors[i]
            color_chk = btn_colors_checked[i]
            button.setStyleSheet(
                f"""QPushButton {{background-color: rgb({color_chk.red()}, {color_chk.green()}, {color_chk.blue()}); color: lightgray;}}
                QPushButton:checked {{background-color: rgb({color.red()}, {color.green()}, {color.blue()}); color: white;}}""")

        for widget in (self.spectraPlotWidget, self.temporalPlotWidget, self.boxPlotWidget):
            widget.setBackground(self.theme_colors['plot_bg'])

        for plot_widget in (self.spectraPlotWidget, self.temporalPlotWidget):
            item = plot_widget.getPlotItem()
            item.getAxis('left').setPen(pg.mkPen(self.theme_colors['axis']))
            item.getAxis('left').setTextPen(pg.mkPen(self.theme_colors['axis']))
            item.getAxis('bottom').setPen(pg.mkPen(self.theme_colors['axis']))
            item.getAxis('bottom').setTextPen(pg.mkPen(self.theme_colors['axis']))

        if self.roi_region:
            self.roi_region.setBrush(self.theme_colors['roi_spec'])
            self.temporal_roi_region.setBrush(self.theme_colors['roi_temp'])

        if len(self.results_df['Timestamp']) > 0:
            self._update_plots_with_results()

    def open_new_window(self):
        self.file_path = None
        self.samples.clear()
        self.clear_plot()
        self.boxPlot.clear()
        self.boxLegend.clear()
        self.setWindowTitle("Análise de dados")

    def load_config(self, config: dict):
        """
        Recebe os dados de configuração da ConfigWindow e inicia a leitura dos espectros.
        
        Args:
            config_data (Dict): Dicionário contendo os parâmetros de configuração.
            
        """
        self.config_data = config
        self._run()
        QApplication.instance().restoreOverrideCursor()

    def unit_changed(self, unit: str):
        """
        Callback chamado quando a unidade do eixo X é alterada.
        Atualiza os dados e os gráficos para refletir a nova unidade.
        
        """
        old_unit = self.xUnit
        if unit == old_unit:
            return

        old_to_m = self._unit_to_meter_factor(old_unit)
        new_to_m = self._unit_to_meter_factor(unit)
        scale_old_to_new = old_to_m / new_to_m

        self.xUnit = unit
        self.actionM.setChecked(unit == 'm')
        self.actionUm.setChecked(unit == 'um')
        self.actionNm.setChecked(unit == 'nm')
        self.actionPm.setChecked(unit == 'pm')
        self._set_spectrum_axis_unit()

        # Mantém ROI proporcional ao trocar unidade do eixo X.
        if self.roi_region is not None:
            roi_min, roi_max = self.roi_region.getRegion()
            new_roi = (roi_min * scale_old_to_new, roi_max * scale_old_to_new)
            self.roi_region.setRegion(new_roi)
            self.roi_range = [new_roi[0], new_roi[1]]

        # Reescala espectro já exibido para evitar distorção visual até a próxima aquisição.
        if self.spectra_data:
            x_old, y_vals = zip(*self.spectra_data)
            x_new = np.asarray(x_old, dtype=float) * scale_old_to_new
            y_new = np.asarray(y_vals, dtype=float)
            self.spectra_data = list(zip(x_new, y_new))
            self._plot_spectrum_curve(x_new, y_new)

        # Reescala espectros fixados para manter consistência com a unidade atual.
        for btn, trace in list(self.fixed_traces.items()):
            x_old, y_vals = trace
            x_new = np.asarray(x_old, dtype=float) * scale_old_to_new
            self.fixed_traces[btn] = (x_new, np.asarray(y_vals, dtype=float))

        if self.results_df['Timestamp']:
            self._update_plots_with_results()

    def _run(self):
        if self.thread is not None:
            return
            
        port = self.config_data.get('port')
        inter = self.config_data.get('inter')
        ip = self.config_data.get('ip')
        range = self.config_data.get('range')
        res = self.config_data.get('res')
        self.fixed_wavelengths = np.arange(range[0], range[1], res) # Atualiza os comprimentos de onda fixos para interpolação

        if self.continuous_chk.isChecked():
            if not self.continuous_cfg():
                return

        # Inicializa a instância compartilhada de PyCCT, se necessário
        if self.osa is None and 'THORLABS' in inter:
            self.osa = self.config_data.get('sdk')

        # Inicia a thread de aquisição de dados
        self.thread = QThread()
        self.worker = DataAcquisition(inter, ip, port, osa=self.osa)
        self.worker.moveToThread(self.thread)

        # Conecta os sinais e slots da thread e do worker
        self.thread.started.connect(self.worker.run)
        self.thread.started.connect(self._thread_started)
        self.request_data_signal.connect(self.worker.request_data, Qt.QueuedConnection)
        self.worker.data_acquired.connect(self.update_plot)
        self.worker.finished.connect(self._cleanup_thread)
        self.worker.error_occurred.connect(self._show_error)
        
        self.thread.start()

        if self.continuous_timer is not None:
             self.continuous_timer.start(self.sample_duration * 1000)

        self._running = True
        self.stop_btn.setText("Parar")
        self.stop_btn.setStyleSheet("QPushButton { background-color: #fd4d4d; color: white; }")
        self._is_stopping = False
        self.cfg_spin.setEnabled(False) # Desabilita o controle de tempo de exposição
        self.cfg_lbl.setEnabled(False)
        self.sr_spin.setEnabled(False) # Desabilita o controle de intervalo entre amostras
        self.sr_lbl.setEnabled(False)
        self.continuous_chk.setEnabled(False)
        self.sample_rate = self.sr_spin.value() # Atualiza o intervalo entre amostras

    def _thread_started(self):
        """
        Callback chamado quando a thread de aquisição de dados é iniciada.
        
        """
        logger.info("Thread de aquisição de dados iniciada.")

        if self.continuous_chk.isChecked() and self.flush_timer is None:
            self.flush_timer = QTimer(self)
            self.flush_timer.timeout.connect(self._flush_continuous_buffer)
            self.flush_timer.start(self.flush_interval_ms)

        # Configura o timer para solicitar dados periodicamente
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.request_data_signal.emit(
                                                self.mean_samples, int(self.cfg_spin.value())))
        self.timer.start(self.sample_rate)

        match self.config_data.get('inter'):
            case 'IBSEN IMON-512':
                self.cfg_lbl.setText("Tempo de Exposição (µs)")
                self.cfg_spin.setRange(3, 65535) # Limita o tempo de exposição
                self.cfg_spin.setSingleStep(100)
            case 'BRAGGMETER FS22DI':
                self.cfg_lbl.setText("Canal (0-3)")
                self.cfg_spin.setRange(2, 3) # Canais de transmissão do BraggMeter
                self.exposure_time = -1 # Desabilita a alteração do tempo de exposição
            case 'BRAGGMETER FS22DI HBM':
                self.cfg_lbl.setText("Canal (0-3)")
                self.cfg_spin.setRange(2, 3) # Canais de transmissão do BraggMeter HBM
                self.exposure_time = -1 # Desabilita a alteração do tempo de exposição
            case 'THORLABS CCT11':
                self.cfg_lbl.setText("Tempo de Exposição (ms)")
                self.cfg_spin.setRange(1, 30000) # Limita o tempo de exposição
                self.cfg_spin.setSingleStep(100)
            case 'THORLABS OSA203':
                self.cfg_lbl.setText("Tempo de Exposição (ms)")
                self.exposure_time = -1

        if self.exposure_time >= 0:
            if self.exposure_time == 0:
                self.cfg_spin.setValue(self.worker.get_exposure_time()) # Obtém o tempo de exposição atual
                self.exposure_time = self.cfg_spin.value()
            elif self.exposure_time != self.cfg_spin.value():
                self.worker.set_exposure_time(self.cfg_spin.value()) # Altera o tempo de exposição
                self.exposure_time = self.cfg_spin.value()

    def _show_error(self, title: str, message: str):
        """
        Mostra uma caixa de diálogo de erro de forma não-bloqueante.
        
        """
        QMessageBox.warning(self, title, message)
        # Em caso de erro de comunicação, apenas interrompe a aquisição
        # mantendo a janela aberta para análise offline.
        try:
            self._cleanup_thread()
        except Exception:
            pass

    def _show_warning(self, message: str):
        """
        Mostra uma caixa de diálogo de aviso de forma não-bloqueante.
        
        """
        if message:
            if self.warning_btn:
                messages = [m.strip() for m in message.split(',') if m.strip()]
                new_messages = []

                for msg in messages:
                    if msg not in self.error_messages:
                        self.error_messages.append(msg)
                        new_messages.append(msg)

                if new_messages:
                    if len(new_messages) == 1:
                        QMessageBox.warning(self, "Aviso", new_messages[0])
                    else:
                        QMessageBox.warning(self, "Aviso", '\n'.join(new_messages))
            else:
                # Cria um novo botão de aviso
                self.warning_btn = QPushButton()
                self.warning_hlay.addWidget(self.warning_btn)
                cur_dir = os.path.dirname(__file__)
                icon = os.path.join(cur_dir, "img", "warning.png")
                self.warning_btn.setIcon(QIcon(icon))

            # Cria conexão com botão e atualiza mensagem a exibir
                self.warning_btn.clicked.connect(lambda: QMessageBox.warning(self, "Aviso", message))

        elif self.warning_btn is not None:
            # Remove o botão de aviso se não houver mensagem
            self.warning_hlay.removeWidget(self.warning_btn)
            self.warning_btn.clicked.disconnect()
            self.warning_btn.deleteLater()
            self.warning_btn = None

    def _update_fixed_list(self, button: QPushButton):
        del self.fixed_traces[str(button)]
        if button.isChecked():
            button.setChecked(False)
            if not self._running:
                x_vals, y_vals = zip(*self.spectra_data)
                # Redesenha o espectro atual para limpar as curvas fixadas
                self._plot_spectrum_curve(np.asarray(x_vals, dtype=float), np.asarray(y_vals, dtype=float))

    def toggle_fix(self, button: QPushButton, pos):
        menu = QMenu()

        if str(button) in self.fixed_traces:
            menu.addAction("Remover")
            menu.triggered.connect(lambda: self._update_fixed_list(button))
            menu.exec_(button.mapToGlobal(pos))

    def fix_btn_clicked(self, button: QPushButton, checked: bool):
        if str(button) in self.fixed_traces:
            if not self._running:
                if checked:
                    x, y = self.fixed_traces[str(button)]
                    color = button.palette().color(QPalette.ColorRole.Button)
                    self.spectraPlotWidget.plot(x, self._preprocess_plot_data(y), pen=pg.mkPen(color, width=1))
                else:
                    x_vals, y_vals = zip(*self.spectra_data)
                    # Redesenha o espectro atual para limpar as curvas fixadas
                    self._plot_spectrum_curve(np.asarray(x_vals, dtype=float), np.asarray(y_vals, dtype=float))
        elif checked:
            if self.spectraPlotWidget.getPlotItem().listDataItems() == []:
                button.setChecked(False) # Impede de marcar se não houver espectro para fixar
                return
            x, y = zip(*self.spectra_data)
            self.fixed_traces[str(button)] = ((x, y))
            if not self._running:
                color = button.palette().color(QPalette.ColorRole.Button)
                self.spectraPlotWidget.plot(x, self._preprocess_plot_data(y), pen=pg.mkPen(color, width=1))
            
    def _cleanup_thread(self):
        """
        Limpa e finaliza a thread de aquisição de dados.
        
        """
        if self._is_stopping:
            return
        self._is_stopping = True
        
        if self.timer is not None:
            if self.timer.isActive():
                self.timer.stop()
            try:
                self.timer.timeout.disconnect()
            except:
                pass
            self.timer.deleteLater()
            self.timer = None

        if self.flush_timer is not None:
            if self.flush_timer.isActive():
                self.flush_timer.stop()
            try:
                self.flush_timer.timeout.disconnect()
            except:
                pass
            self.flush_timer.deleteLater()
            self.flush_timer = None

        self._flush_continuous_buffer(force=True)

        if self.continuous_timer is not None:
            if self.continuous_timer.isActive():
                self.continuous_timer.stop()
            try:
                self.continuous_timer.timeout.disconnect()
            except:
                pass
            self.continuous_timer.deleteLater()
            self.continuous_timer = None
            
        if self.worker is not None:
            try:
                self.request_data_signal.disconnect(self.worker.request_data)
            except:
                pass
            try:
                self.worker.data_acquired.disconnect()
                self.worker.finished.disconnect()
                # Evita que erros tardios durante o desligamento fechem/afetem a UI
                self.worker.error_occurred.disconnect()
            except:
                pass
            self.worker.stop()
            
        if self.thread is not None:
            self.thread.quit()
            if not self.thread.wait(3000):
                logger.warning("Terminating thread...")
                self.thread.terminate()
                self.thread.wait()
            self.thread = None
            
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None
            
        self._is_stopping = False
        self._running = False
        self.stop_btn.setText("Retomar")
        self.stop_btn.setStyleSheet("QPushButton { background-color: #60fa93; color: #0f172a; }")
        self.sr_spin.setEnabled(True) # Habilita o controle de intervalo entre amostras
        self.sr_lbl.setEnabled(True)
        if self.config_data.get('inter') != 'THORLABS OSA203':
            self.cfg_spin.setEnabled(True) # Habilita o controle de tempo de exposição
            self.cfg_lbl.setEnabled(True)
        self.continuous_chk.setEnabled(True)
        QApplication.instance().restoreOverrideCursor()
        self.stop_btn.setEnabled(True)

    def roi_changed(self):
        """
        Callback chamado quando a região de interesse (ROI) é alterada.
        Atualiza o box plot mesmo com a aquisição parada.
        
        """
        if self.timer is None or not self.timer.isActive():
            self._update_plots_with_results()

    def toggle_thread(self):
        """
        Inicia ou para a thread de aquisição de dados com lógica de toggle.
        
        """
        QApplication.instance().setOverrideCursor(Qt.WaitCursor)
        self.stop_btn.setEnabled(False) # Evita múltiplos cliques durante a transição
        if self.continuous_timer is not None:
            self._flush_continuous_buffer(force=True)
            self._cleanup_thread()
            QMessageBox.warning(self, "Amostra Contínua", "Amostra contínua interrompida pelo usuário.")
        elif self.thread is not None:
            self._cleanup_thread()
        else:
            self._run()

    def continuous_timer_shot(self):
        """
        Callback chamado quando o timer da amostra contínua dispara.
        Para a aquisição de dados e informa o usuário.
        
        """
        self._flush_continuous_buffer(force=True)
        self._cleanup_thread()
        QMessageBox.information(self, 
            "Amostra Contínua", 
            f"A amostra \"{self.sample_name}\" coletada por {self.sample_duration} segundos foi salva com sucesso.")
        self.clear_plot()

    def _flush_continuous_buffer(self, force: bool = False):
        """
        Salva em lote o buffer do modo contínuo para reduzir overhead de I/O.
        """
        pending_count = len(self.pending_hdf5['Timestamp'])
        if pending_count == 0:
            return
        if not force and pending_count < self.flush_batch_size:
            return

        try:
            inter = self.config_data.get('inter') if self.config_data else None
            file_path = self.config_data.get('path') if self.config_data else None
            if not inter or not file_path:
                return

            intensities = np.asarray(self.pending_hdf5['Intensidade'], dtype=np.float32)
            timestamps = np.asarray(self.pending_hdf5['Timestamp'], dtype=np.float64)
            resonant_wavelengths = np.asarray(self.pending_hdf5['Vale'], dtype=np.float64)

            self._append_hdf5_records(
                file_path=file_path,
                inter=inter,
                intensities=intensities,
                timestamps=timestamps,
                resonant_wavelengths=resonant_wavelengths,
                sample_name=self.sample_name or "Atual"
            )

            self.pending_hdf5 = {'Timestamp': [], 'Intensidade': [], 'Vale': []}
            logger.debug(f"Flush contínuo realizado com {pending_count} registro(s).")
        except Exception as e:
            logger.error(f"Erro ao salvar buffer contínuo: {e}")

    def update_plot(self, data, warning):
        """
        Atualiza o gráfico com os dados adquiridos.
        
        """
        QApplication.instance().restoreOverrideCursor()
        self.stop_btn.setEnabled(True)
        self._show_warning(warning)
        
        x, y = zip(*data)
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        # Converte de nm para a unidade configurada, caso necessário
        x *= self._unit_to_meter_factor('nm') / self._unit_to_meter_factor(self.xUnit)
        self._set_spectrum_axis_unit()

        self.spectra_data = list(zip(x, y))
        self._plot_spectrum_curve(x, y)

        # peak_indices = list(find_peaks(y,prominence=0.1*(np.max(y)-np.min(y)),width=200,distance=500)[0])
        # print('\n')
        # for i in peak_indices:
        #     print(f'{y[i]}\n')

        if self.roi_range is None:
            x_min = min(x)
            x_max = max(x)
            x_range = x_max - x_min
            self.roi_range = [(x_min+0.25*x_range), x_max-0.25*x_range] # Intervalo fixo
            self.roi_region.setRegion(self.roi_range)
            logger.debug(f"ROI inicial definida para: {self.roi_range}")

        self.process_spectra()

    def process_spectra(self):
        """
        Executa o algoritmo de detecção de picos para o espectro na ROI.
        
        """
        if not self.spectra_data:
            logger.warning("Não há espectros carregados para processar.")
            return
        
        # 1. Obtém os limites da ROI selecionada pelo usuário
        roi_min, roi_max = self.roi_region.getRegion()
        logger.info(f"Processando espectros dentro da ROI: {roi_min:.2f} a {roi_max:.2f}")

        # 2. Processa o espectro atual
        wavelength, power = zip(*self.spectra_data)
        wavelength = np.asarray(wavelength, dtype=float)
        power = np.asarray(power, dtype=float)

        # Wavelength em metros para o processamento
        display_to_m = self._unit_to_meter_factor(self.xUnit)
        roi_m_min = roi_min * display_to_m
        roi_m_max = roi_max * display_to_m
        wavelength *= display_to_m

        # 3. Chama a função do backend para encontrar o pico
        res_wl = find_resonant_wavelength(np.array(wavelength), np.array(power), roi_m_min, roi_m_max)
        
        # 4. Adiciona o resultado ao dicionário se um pico for encontrado
        if res_wl is not None:
            res_wl = float(res_wl)
            if len(self.results_df['Timestamp']) == 1:
                 self.spectraPlotWidget.autoRange() # Ajusta o gráfico na primeira medição
            now = datetime.now().timestamp()

            interp_fn = interp1d(
                wavelength,
                power,
                kind='linear',
                bounds_error=False,
                fill_value=(power[0], power[-1])
            )
            intensities = np.asarray(interp_fn(self.fixed_wavelengths), dtype=np.float32)

            self.results_df['Timestamp'].append(now)
            self.results_df['Intensidade'].append(intensities)
            self.results_df['Vale'].append(res_wl)

            # Mantém apenas parte do histórico em memória para evitar degradação da UI.
            if self.continuous_chk.isChecked() and len(self.results_df['Timestamp']) > self.max_live_points:
                excess = len(self.results_df['Timestamp']) - self.max_live_points
                self.results_df['Timestamp'] = self.results_df['Timestamp'][excess:]
                self.results_df['Intensidade'] = self.results_df['Intensidade'][excess:]
                self.results_df['Vale'] = self.results_df['Vale'][excess:]

            if self.continuous_chk.isChecked():
                self.pending_hdf5['Timestamp'].append(now)
                self.pending_hdf5['Intensidade'].append(intensities)
                self.pending_hdf5['Vale'].append(res_wl)
                self._flush_continuous_buffer()

                logger.debug(f"Dado salvo automaticamente")

        logger.info(f"Processamento concluído. Total de {len(self.results_df['Timestamp'])} medições acumuladas.")
        logger.debug(f"Último pico detectado: {res_wl} m, Total de medições: {len(self.results_df['Timestamp'])}")

        # 5. Chama a função para atualizar os gráficos com os resultados
        self._update_plots_with_results()

    def _append_hdf5_records(
        self,
        file_path: str,
        inter: str,
        intensities: np.ndarray,
        timestamps: np.ndarray,
        resonant_wavelengths: np.ndarray,
        sample_name: str,
    ):
        """
        Acrescenta registros no arquivo HDF5 usando o schema:
        inter/param/sample_name/{Intensidades,Timestamp,Vale}
        """
        range_cfg = self.config_data.get('range')
        res = self.config_data.get('res')
        param = f"{int(range_cfg[0]*1e9)}-{int(range_cfg[1]*1e9)},{res*1e12:.1f}" # nm, nm, pm
        spec_len = intensities.shape[1]

        with h5py.File(file_path, "a") as f:
            if inter not in f:
                f.create_group(inter)
            if param not in f[inter]:
                f[inter].create_group(param)
            if sample_name not in f[inter][param]:
                f[inter][param].create_group(sample_name)
            s = f[inter][param][sample_name]

            if "Intensidades" not in s:
                s.create_dataset(
                    "Intensidades",
                    data=np.asarray(intensities, dtype=np.float32),
                    maxshape=(None, spec_len),
                    dtype="float32",
                    chunks=(256, spec_len),
                    compression="gzip"
                )
                s.create_dataset(
                    "Timestamp",
                    data=np.asarray(timestamps, dtype=np.float64),
                    maxshape=(None,),
                    dtype="float64",
                    chunks=True
                )
                s.create_dataset(
                    "Vale",
                    data=np.asarray(resonant_wavelengths, dtype=np.float64),
                    maxshape=(None,),
                    dtype="float64",
                    chunks=True
                )
                return

            intensities_ds = s["Intensidades"]
            timestamps_ds = s["Timestamp"]
            wavelengths_ds = s["Vale"]

            if intensities_ds.shape[1] != spec_len:
                raise ValueError(
                    f"Comprimento do espectro incompatível para append. "
                    f"Esperado {intensities_ds.shape[1]}, recebido {spec_len}."
                )

            n_old = intensities_ds.shape[0]
            n_new = len(timestamps)

            intensities_ds.resize((n_old + n_new, spec_len))
            timestamps_ds.resize((n_old + n_new,))
            wavelengths_ds.resize((n_old + n_new,))

            intensities_ds[n_old:n_old+n_new] = np.asarray(intensities, dtype=np.float32)
            timestamps_ds[n_old:n_old+n_new] = np.asarray(timestamps, dtype=np.float64)
            wavelengths_ds[n_old:n_old+n_new] = np.asarray(resonant_wavelengths, dtype=np.float64)
    
    def _update_plots_with_results(self):
        """
        Atualiza os gráficos para exibir os resultados processados.
        - Plota os pontos no gráfico de evolução temporal.
        - Desenha linhas verticais nos picos encontrados no gráfico de espectros.
        
        """
        if len(self.results_df['Timestamp']) == 0 and self.samples == {}:
            logger.warning("Nenhum resultado para exibir nos gráficos.")
            return

        # --- Atualiza Gráfico 2: Evolução Temporal ---
        self.temporalPlotWidget.clear()
        
        # pyqtgraph precisa de timestamps numéricos (Unix timestamp) para o eixo de datas
        timestamps_numeric = self.results_df['Timestamp']

        resonant_wavelengths_m = np.asarray(self.results_df['Vale'], dtype=float)
        resonant_temporal = self._from_meter(resonant_wavelengths_m, self.resultUnit)
        resonant_spectrum = self._from_meter(resonant_wavelengths_m, self.xUnit)
        
        # Plota os pontos e uma linha conectando-os
        self.temporalPlotWidget.plot(
            x=timestamps_numeric,
            y=resonant_temporal,
            pen={'color': self.theme_colors['spectrum'], 'width': 2},
            symbol='o',
            symbolBrush=self.theme_colors['accent'],
            symbolSize=8
        )

        if self.timer is not None:
            roi_min = timestamps_numeric[0] # Primeiro timestamp
            roi_max = timestamps_numeric[-1] # Último timestamp
            self.temporal_roi_region.setRegion((roi_min, roi_max)) # Ajusta a ROI temporal
            logger.debug(f"ROI temporal ajustada no intervalo: {roi_min} a {roi_max}")

        self.temporalPlotWidget.addItem(self.temporal_roi_region)
        
        logger.debug("Gráfico de evolução temporal atualizado.")
        
        # --- Atualiza Gráfico 1: Adiciona Marcadores de Pico ---
        # Primeiro, remove marcadores antigos (se existirem)
        for item in self.spectraPlotWidget.items():
            if isinstance(item, pg.InfiniteLine):
                self.spectraPlotWidget.removeItem(item)

        # Adiciona uma linha vertical para o último pico encontrado
        line = pg.InfiniteLine(
            pos=resonant_spectrum[-1],
            angle=90,
            movable=False,
            pen={'color': self.theme_colors['accent'], 'style': pg.QtCore.Qt.DashLine}
        )
        self.spectraPlotWidget.addItem(line)
        logger.debug(f"Marcador de pico adicionado ao gráfico de espectros.")
        
        # Seleciona a ROI temporal atual para filtrar os dados computados pelo box plot
        roi_min_ts, roi_max_ts = self.temporal_roi_region.getRegion()
        mask = [(r >= roi_min_ts) and (r <= roi_max_ts) for r in timestamps_numeric]
        boxplot_resonant_wavelengths = [resonant_temporal[i] for i in range(len(resonant_temporal)) if mask[i]]

        if len(boxplot_resonant_wavelengths) == 0 and len(timestamps_numeric) > 0:
            logger.warning("ROI temporal vazia para box plot, nada a plotar.")
            return

        self.boxPlot.clear()
        if self._add_legend:
            self.boxLegend.clear()
        self.boxPlot.setYRange(min(boxplot_resonant_wavelengths) - 1, max(boxplot_resonant_wavelengths) + 1)
        self.update_box_plot(boxplot_resonant_wavelengths)

    def update_box_plot(self, boxplot_resonant_wavelengths: list, loading: bool = False):
        """
        Atualiza o box plot com os dados processados.
        Args:
            boxplot_resonant_wavelengths (list): Lista de valores para o box plot.
            loading (bool): Indica se os dados estão sendo carregados e adequa a lógica de plotagem.
            
        """
        for i in range(len(self.samples.keys())+1): # +1 para o dado atual
            if i == len(self.samples.keys()):
                q1, q2, q3, lower_whisker, upper_whisker, outliers = self.box_plot_statistics(boxplot_resonant_wavelengths) # amostra atual
            else:
                sample_name = list(self.samples.keys())[i-1+loading]
                q1, q2, q3, lower_whisker, upper_whisker, outliers = self.samples[sample_name] # amostras anteriores

            # Cores alternadas para os box plots
            rgb = [(50*i if (i%3) == 1 else 0) % 250,
                   (50*i if (i%3) == 2 else 0) % 250,
                   (50*i if (i%3) == 0 else 0) % 250]

            # --- Desenho do box plot ---
            # Retângulo entre Q1 e Q3
            box = QGraphicsRectItem(0.75+i, q1, 0.5, q3-q1)
            box.setPen(pg.mkPen('k'))
            box.setBrush(pg.mkBrush(rgb)) # cores alternadas
            self.boxPlot.addItem(box)

            # Legenda
            if self._add_legend:
                legend = pg.PlotDataItem([0], [1], pen=None, symbol='s', symbolBrush=pg.mkBrush(rgb))
                self.boxLegend.addItem(
                    legend, f"{list(self.samples.keys())[i-1+loading] if i < len(self.samples.keys()) else 'Atual'}")

            # Linha da mediana
            self.boxPlot.plot([0.75+i, 1.25+i], [q2, q2], pen=pg.mkPen(self.theme_colors['accent'], width=2))
            #Linha vertical
            self.boxPlot.plot([1.0+i, 1.0+i], [q1, q3], pen='k')
            # Whiskers (linhas verticais dos limites)
            self.boxPlot.plot([1.0+i, 1.0+i], [q3, upper_whisker], pen='k')
            self.boxPlot.plot([1.0+i, 1.0+i], [q1, lower_whisker], pen='k')
            # Topo e base dos whiskers
            self.boxPlot.plot([0.85+i, 1.15+i], [upper_whisker, upper_whisker], pen=pg.mkPen(self.theme_colors['spectrum']))
            self.boxPlot.plot([0.85+i, 1.15+i], [lower_whisker, lower_whisker], pen=pg.mkPen(self.theme_colors['spectrum']))

            # Outliers (se existirem)
            if len(outliers) > 0:
                self.boxPlot.plot(
                    np.ones(len(outliers))*(1.0+i),
                    outliers,
                    pen=None,
                    symbol='o',
                    symbolBrush=self.theme_colors['accent'],
                    symbolSize=5
                )
        
        if self._add_legend:
            # Evita múltiplas legendas
            self._add_legend = False

        # Mantém os box plots visíveis
        self.boxPlot.autoRange()

    def box_plot_statistics(self, data: list):
        """
        Calcula as estatísticas básicas para o box plot.

        Args:
            data (list): Lista de valores numéricos.
        Returns:
            tuple: (Q1, Q2, Q3, lower_whisker, upper_whisker, outliers)
            
        """
        data = np.array(data)
        # quartis
        q1 = np.percentile(data, 25)
        q2 = np.percentile(data, 50)
        q3 = np.percentile(data, 75)

        # whiskers (bigodes)
        lower_whisker = np.min(data[data >= q1 - 1.5 * (q3 - q1)])
        upper_whisker = np.max(data[data <= q3 + 1.5 * (q3 - q1)])
        # outliers
        outliers = data[(data < lower_whisker) | (data > upper_whisker)]
        return q1, q2, q3, lower_whisker, upper_whisker, outliers

    def clear_plot(self):
        """
        Limpa o gráfico do espectro e do plot temporal.
        """
        self.spectraPlotWidget.clear()
        self.spectraPlotWidget.addItem(self.roi_region)
        self.temporalPlotWidget.clear()
        self.temporalPlotWidget.addItem(self.temporal_roi_region)
        self.results_df = {'Timestamp': [], 'Intensidade': [], 'Vale': []}
        self.spectra_data.clear()
        logger.info("Gráficos limpos.")

    def _prompt_sample_name(self) -> tuple[str, bool]:
        """
        Abre diálogo para entrada do nome da amostra com sugestões.

        As sugestões são baseadas nas amostras já carregadas do arquivo aberto.
        """
        dialog = QInputDialog(self)
        dialog.setInputMode(QInputDialog.TextInput)
        dialog.setWindowTitle("Nome da Amostra")
        dialog.setLabelText("Insira o nome da amostra para salvar os dados:")

        line_edit = dialog.findChild(QLineEdit)
        if line_edit is not None and self.samples:
            completer = QCompleter(list(self.samples.keys()), dialog)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setCompletionMode(QCompleter.PopupCompletion)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            line_edit.setCompleter(completer)

        if dialog.exec() != QDialog.Accepted:
            return "", False

        return dialog.textValue(), True

    def save_data(self):
        """
        Abre um diálogo para selecionar um arquivo .h5. Se o arquivo já existir,
        anexa os novos dados; caso contrário, cria um novo arquivo.
        Os dados são filtrados pela ROI temporal antes de serem salvos.
        
        """
        # Interrompe a aquisição de dados
        if self._running:
            self.toggle_thread()

        # --- Passo 1: Validação inicial ---
        if len(self.results_df['Timestamp']) == 0:
            logger.warning("Tentativa de salvar sem dados processados.")
            QMessageBox.warning(self, "Atenção", "Não há dados processados para salvar.")
            return

        logger.info("Iniciando processo para salvar dados.")

        # --- Passo 2: Abre diálogo para inserir o nome da amostra ---
        sample_name, ok = self._prompt_sample_name()

        if not ok:
            return # Usuário cancelou a entrada do nome da amostra

        # --- Passo 3: Obtém o caminho do arquivo do usuário ---
        file_path = self.config_data.get('path')
        if file_path is not None:
            logger.info(f"Usando caminho de arquivo pré-configurado: {file_path}")
        else:
            file_path, _ = QFileDialog.getSaveFileName(
                self,   
                "Salvar ou Anexar Experimento",
                "",
                "HDF5 Files (*.h5)",
                options=QFileDialog.DontConfirmOverwrite
            )

            if not file_path:
                logger.info("Operação de salvamento cancelada pelo usuário.")
                return

        # --- Passo 4: Processa e filtra os dados da ROI ---
        try:
            roi_min_ts, roi_max_ts = self.temporal_roi_region.getRegion()

            timestamps = np.asarray(self.results_df['Timestamp'], dtype=np.float64)
            intensities = self.results_df['Intensidade']
            resonant_wavelengths = np.asarray(self.results_df['Vale'], dtype=np.float64)
            
            mask = (timestamps >= roi_min_ts) & (timestamps <= roi_max_ts)

            timestamps_filtered = timestamps[mask]
            intensities_filtered = np.asarray(
                [intensities[i] for i in range(len(intensities)) if mask[i]],
                dtype=np.float32
            )
            resonant_filtered = resonant_wavelengths[mask]

            if len(timestamps_filtered) == 0:
                logger.warning("A região selecionada não contém dados para salvar.")
                QMessageBox.warning(self, "Atenção", "A região selecionada não contém dados para salvar.")
                return

            inter = self.config_data.get('inter')

            logger.debug(f"Salvando {len(intensities_filtered)} espectros")

            self._append_hdf5_records(
                file_path=file_path,
                inter=inter,
                intensities=intensities_filtered,
                timestamps=timestamps_filtered,
                resonant_wavelengths=resonant_filtered,
                sample_name=sample_name
            )

            logger.info(f"Dados salvos com sucesso em: {file_path}")
            QMessageBox.information(self, "Sucesso", f"{len(timestamps_filtered)} medições foram salvas com sucesso em:\n{file_path}")

            # Armazena o caminho definido para futuro uso
            self.file_path = file_path
            self.setWindowTitle(f"Análise de dados - {os.path.basename(file_path)}")
            # Calcula e armazena as estatísticas do box plot na escala configurada
            resonant_for_box = self._from_meter(resonant_filtered, self.resultUnit)
            self.samples[sample_name] = self.box_plot_statistics(resonant_for_box)
            self.samples = dict(reversed(self.samples.items())) # Mantém a ordem de inserção (última amostra salva aparece primeiro)
            self._add_legend = True
            self.clear_plot()
            self.toggle_thread() # Reinicia a aquisição para atualizar os gráficos

        except Exception as e:
            logger.error(f"Falha ao processar ou salvar os dados: {e}")
            QMessageBox.critical(self, "Erro", f"Ocorreu um erro ao salvar o arquivo:\n{e}")

    def select_file(self):
        """
        Abre um diálogo para seleção de arquivo e armazena o caminho selecionado.
        """
        file_dialog = QFileDialog(self, "Selecione o arquivo de dados", filter="HDF5 Files (*.h5)")
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                path = selected_files[0]
        else:
            return # Usuário cancelou a seleção de arquivo

        # Verifica se o arquivo selecionado é válido
        try:
            inter = self.config_data.get('inter')
            with h5py.File(path, "r") as f:
                if inter not in f:
                    QMessageBox.warning(
                        self,
                        "Arquivo inválido",
                        f"O arquivo HDF5 não contém o grupo da interface selecionada: {inter}."
                    )
                    return

                g = f[inter]
                is_new_valid = False
                for _, param_group in g.items():
                    if not isinstance(param_group, h5py.Group):
                        continue
                    for _, sample_group in param_group.items():
                        if isinstance(sample_group, h5py.Group) and "Vale" in sample_group:
                            is_new_valid = True
                            break
                    if is_new_valid:
                        break

                if not is_new_valid:
                    QMessageBox.warning(
                        self,
                        "Arquivo inválido",
                        "O arquivo não está no formato esperado."
                    )
                    return
                self.load_file(path)

        except Exception as e:
            QMessageBox.warning(self, "Arquivo inválido", f"Falha ao abrir arquivo HDF5: {e}")


    def load_file(self, path: str):
        """
        Carrega dados de amostras de um arquivo HDF5 para análise.

        Args:
            path (str): Caminho do arquivo HDF5 contendo os dados das amostras.
            
        """
        try:
            inter = self.config_data.get('inter')
            with h5py.File(path, "r") as f:
                if inter not in f:
                    raise ValueError(f"Grupo '{inter}' não encontrado no arquivo.")

                g = f[inter]
                grouped_samples = {}

                # Formato novo: interface -> parâmetros -> amostra -> datasets
                for param_name, param_group in g.items():
                    if not isinstance(param_group, h5py.Group):
                        continue
                    for sample_name, sample_group in param_group.items():
                        if not isinstance(sample_group, h5py.Group):
                            continue
                        if "Vale" not in sample_group:
                            continue

                        sample_wavelengths = np.asarray(
                            sample_group["Vale"][:],
                            dtype=float
                        )
                        if len(sample_wavelengths) == 0:
                            continue
                        grouped_samples.setdefault(sample_name, []).extend(sample_wavelengths.tolist())

            last_wavelengths = []
            for sample_name, sample_wavelengths in grouped_samples.items():
                sample_wavelengths = np.asarray(sample_wavelengths, dtype=float)
                sample_wavelengths = self._from_meter(sample_wavelengths, self.resultUnit)

                self.samples[sample_name] = self.box_plot_statistics(sample_wavelengths)
                last_wavelengths = sample_wavelengths

            if len(last_wavelengths) == 0:
                raise ValueError("Nenhum dado de amostra encontrado no arquivo.")
            
            self._add_legend = True
            self.boxLegend.clear()
            self.update_box_plot(last_wavelengths, loading=True) # Atualiza os gráficos com os box plots carregados
            self.setWindowTitle(f"Análise de dados - {os.path.basename(path)}")
            self.file_path = path
            logger.info(f"Dados carregados com sucesso do arquivo: {path}. {len(self.samples)} amostra(s) encontrada(s).")

        except Exception as e:
            logger.error(f"Erro ao carregar o arquivo {path}: {e}")
            QMessageBox.critical(self, "Erro", f"Não foi possível carregar o arquivo:\n{e}")

    def continuous_cfg(self) -> bool:
        """
        Configura a aquisição contínua de dados.
        Abre diálogos para o usuário inserir o nome da amostra, o caminho
        de salvamento e a duração da amostra.
        
        """
        # Abre diálogo para inserir o nome da amostra ---
        self.sample_name, ok = self._prompt_sample_name()

        if not ok:
            return False # Usuário cancelou a entrada do nome da amostra

        # Obtém o caminho do arquivo do usuário ---
        file_path, _ = QFileDialog.getSaveFileName(
            self,   
            "Salvar ou Anexar Experimento",
            "",
            "HDF5 Files (*.h5)",
            options=QFileDialog.DontConfirmOverwrite
        )

        if not file_path:
            logger.info("Operação de salvamento cancelada pelo usuário.")
            return False
        
        # Abre diálogo para inserir a duração da amostra ---
        dialog = QInputDialog(self)
        dialog.setInputMode(QInputDialog.IntInput)
        dialog.setWindowTitle("Duração da Amostra")
        dialog.setLabelText("Insira a duração da amostra em segundos:")
        dialog.setIntValue(2*self.sample_rate//1000)
        dialog.setIntMinimum(2*self.sample_rate//1000)
        dialog.setIntMaximum(24*3600)
        dialog.setIntStep(1)
        dialog.setOkButtonText("Iniciar")

        if dialog.exec() == QDialog.Accepted:
            self.sample_duration = dialog.intValue()
        else:
            return False # Usuário cancelou a entrada da duração da amostra
        
        # Atualiza o caminho de salvamento para o modo contínuo
        self.file_path = file_path
        logger.debug(f"Caminho de salvamento definido para o modo contínuo: {file_path}")
        
        self.clear_plot()
        # Interrompe a aquisição após a duração especificada
        if self.continuous_timer is not None:
            if self.continuous_timer.isActive():
                self.continuous_timer.stop()
            self.continuous_timer.deleteLater()

        self.pending_hdf5 = {'Timestamp': [], 'Intensidade': [], 'Vale': []}
        self.continuous_timer = QTimer(self)
        self.continuous_timer.setSingleShot(True)
        self.continuous_timer.timeout.connect(self.continuous_timer_shot)
        return True
        
    def closeEvent(self, event):
        """
        Sobrescreve o evento de fechar a janela.

        Em vez de fechar a aplicação, esta função emite um sinal 'closing'
        para que a janela de configuração possa reaparecer.
        
        """
        self._cleanup_thread()
        super().closeEvent(event)
        self.closing.emit()