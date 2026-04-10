from PySide6.QtWidgets import (QMainWindow, QMessageBox, QGraphicsRectItem, QInputDialog, QDialog, QPushButton, 
    QMenu, QApplication, QFormLayout, QSpinBox, QDialogButtonBox, QLineEdit, QCompleter)
from PySide6.QtGui import QColor, QLinearGradient, QBrush, QIcon, QPalette, QGradient
from PySide6.QtCore import Signal, QThread, QTimer, Qt

from ui.AnalysisWindow_ui import Ui_AnalysisWindow
from ui.toggle import ToggleSwitch
from core.processing import find_resonant_wavelength, preprocess_plot_data
from core.data_acquisition import DataAcquisition
from iobound.file_manager import append_hdf5_samples, prompt_save_file, prompt_open_file, load_hdf5_samples

from scipy.signal import windows
from scipy.interpolate import interp1d
from datetime import datetime
import pyqtgraph as pg
from sys import argv
import numpy as np
import webbrowser
import os

import qdarktheme

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
    stop_worker_signal = Signal()

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
        # Intervalo entre amostras (ms)
        self.sample_rate: int = 100
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
        self.flush_interval_ms: int = 15000
        # Limite de pontos mantidos em memória para evitar lentidão da UI
        self.max_live_points: int = 5000
        # Unidade do eixo x (comprimento de onda)
        self.xUnit: str = 'nm'
        # Unidade fixa para temporal/boxplot (não muda com actions de unidade)
        self.resultUnit: str = 'nm'
        # Tema atual da interface
        self.theme: str = ''
        self.theme_colors = {}
        # Cores fixas para os canais exibidos na tab Merge
        self.merge_channel_colors = [
            QColor(139, 0, 0),
            QColor(0, 152, 0),
            QColor(0, 0, 188),
            QColor(255, 170, 0),
        ]
        # Dicionário para armazenar os espectros fixados
        self.fixed_traces = {}
        # Lista de botões de fixação atualmente ativos (para manter o estado ao mudar de aba)
        self.active_traces = []
        # Botão de aviso (criado dinamicamente em _show_warning)
        self.warning_btn: QPushButton | None = None
        # Flag para indicar se a aquisiçao está ativa
        self._running: bool = False
        # Caminho para o arquivo de dados selecionado pelo usuário
        self.file_path: str | None = None
        # Lista com as mensagens de erro recebidas
        self.error_messages: list = []
        # Estado por aba/canal para manter análises independentes
        self.channel_states: dict[int, dict] = {}
        self.active_channel_idx: int = 0
        # Lista dos canais habilitados para aquisição cíclica
        self.enabled_channels: list[int] = []

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
        # Parametros do filtro Savitzky-Golay aplicados no plot
        self.savgol_window_points: int = 51
        self.savgol_polyorder: int = 2
        # Numero de amostras para a média espectral
        self.mean_samples: int = 10

        # Thread e worker para aquisição de dados
        self.thread: QThread | None = None
        self.worker: DataAcquisition | None = None
        #Timer para solicitar dados periodicamente
        self.timer: QTimer | None = None
        # Flag para evitar chamadas concorrentes de _cleanup_thread
        self._is_stopping = False
        
        # Instância compartilhada de PyCCT/OSA para evitar conflito de múltiplas instâncias
        self.osa = None

        self.set_theme(qdarktheme.get_theme()) # Aplica o tema inicial
        self.actionNm.setChecked(True) # Define nm como unidade inicial do eixo X
        self.setup_plot()
        self.setup_connections()

    def setup_plot(self):
        """
        Configura os widgets de gráfico da pyqtgraph.
        
        """
        # --- Configuração do gráfico: Espectro ---
        self.spectraPlotWidget.setLabel('left', 'Potência', units='dBm')
        self.spectraPlotWidget.showGrid(x=True, y=True)
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

        self._setup_merge_plots()

        # Ícones dos botões
        cur_dir = os.path.dirname(os.path.abspath(argv[0]))
        apo = os.path.join(cur_dir, "img", "apodization.png")
        self.apodization_btn.setIcon(QIcon(apo))
        svg = os.path.join(cur_dir, "img", "savgol.png")
        self.savgol_btn.setIcon(QIcon(svg))
        mean = os.path.join(cur_dir, "img", "mean.png")
        self.mean_btn.setIcon(QIcon(mean))

    def _setup_merge_plots(self):
        """
        Configura os widgets da tab Merge com a mesma base visual dos demais widgets.

        """
        self.merge_plot_specs = [
            (self.mergePlotWidget, self.mergePlotWidget.addLegend()),
            (self.mergeCh1PlotWidget, None),
            (self.mergeCh2PlotWidget, None),
            (self.mergeCh3PlotWidget, None),
            (self.mergeCh4PlotWidget, None),
        ]

        self._set_merge_axis_unit()

        for plot_widget, _ in self.merge_plot_specs:
            plot_widget.setBackground(self.theme_colors['plot_bg'])
            item = plot_widget.getPlotItem()
            item.getAxis('left').setPen(pg.mkPen(self.theme_colors['axis']))
            item.getAxis('left').setTextPen(pg.mkPen(self.theme_colors['axis']))
            item.getAxis('bottom').setPen(pg.mkPen(self.theme_colors['axis']))
            item.getAxis('bottom').setTextPen(pg.mkPen(self.theme_colors['axis']))

    def _set_merge_axis_unit(self):
        """
        Atualiza os eixos X da tab Merge conforme a unidade atual.

        """
        unit_label = {
            'm': 'm',
            'um': 'μm',
            'nm': 'nm',
            'pm': 'pm',
        }.get(self.xUnit, 'nm')

        for idx, (plot_widget, _) in enumerate(getattr(self, 'merge_plot_specs', [])):
            if idx == 0:
                plot_widget.setLabel('left', 'Potência', units='dBm')
            else:
                plot_widget.setLabel('left', '')
            plot_widget.showGrid(x=(idx==0), y=(idx==0))
            bottom_axis = pg.AxisItem(orientation='bottom')
            if idx == 0:
                bottom_axis.setLabel(text='Comprimento de Onda', units=unit_label)
            else:
                bottom_axis.setLabel(text='')
            bottom_axis.enableAutoSIPrefix(False)
            plot_widget.setAxisItems({'bottom': bottom_axis})

    def _refresh_merge_views(self):
        """
        Redesenha a tab Merge com os espectros fixados salvos por canal.

        """
        if not hasattr(self, 'merge_plot_specs'):
            return

        for idx, (plot_widget, legend) in enumerate(self.merge_plot_specs):
            plot_widget.clear()
            if legend is not None:
                legend.clear()
            if idx == 0:
                plot_widget.setLabel('left', 'Potência', units='dBm')
            else:
                plot_widget.setLabel('left', '')
            plot_widget.showGrid(x=(idx==0), y=(idx==0))

        channel_widgets = [spec[0] for spec in self.merge_plot_specs[1:]]
        fix_button_colors = {
            str(button): button.palette().color(QPalette.ColorRole.Button)
            for button in self._list_fix_buttons()
        }

        for channel_idx in range(len(self.channel_states)):
            state = self.channel_states.get(channel_idx, {})
            fixed_traces = state.get('fixed_traces', {}) or {}
            if not fixed_traces:
                continue

            color = self.merge_channel_colors[channel_idx % len(self.merge_channel_colors)]
            channel_plot = channel_widgets[channel_idx]
            channel_name = f'Canal {channel_idx + 1}'
            first_trace = True

            for trace_key, trace in fixed_traces.items():
                if trace is None:
                    continue

                x_vals = np.asarray(trace[0], dtype=float)
                y_vals = preprocess_plot_data(
                    np.asarray(trace[1], dtype=float),
                    self.apodization_methods,
                    self.savgol_window_points,
                    self.savgol_polyorder,
                    self.apodization,
                )

                main_name = channel_name if first_trace else None
                self.mergePlotWidget.plot(x_vals, y_vals, pen=pg.mkPen(color, width=1), name=main_name)
                trace_color = fix_button_colors.get(trace_key, color)
                channel_plot.plot(x_vals, y_vals, pen=pg.mkPen(trace_color, width=1))
                first_trace = False

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
        self.roi_region.sigRegionChanged.connect(self._spectrum_roi_changed)
        
        # Botões de fixar um espectro
        for button in self._list_fix_buttons():
            button.setContextMenuPolicy(Qt.CustomContextMenu)
            button.customContextMenuRequested.connect(lambda pos, btn=button: self.toggle_fix(btn, pos))
            button.clicked.connect(lambda b, btn=button: self.fix_btn_clicked(btn, btn.isChecked()))

        self.actionM.triggered.connect(lambda: self.unit_changed('m'))
        self.actionUm.triggered.connect(lambda: self.unit_changed('um'))
        self.actionNm.triggered.connect(lambda: self.unit_changed('nm'))
        self.actionPm.triggered.connect(lambda: self.unit_changed('pm'))
        self.actionLight.triggered.connect(lambda: self.set_theme('light'))
        self.actionDark.triggered.connect(lambda: self.set_theme('dark'))
        self.actionHelp.triggered.connect(lambda: webbrowser.open(
            'https://github.com/pedroproprio/online_process_timeseries/blob/main/README.md'))
        self.actionOpenFile.triggered.connect(self.open_file)
        self.actionNewWindow.triggered.connect(self.open_new_window)

        # Toggle
        self.continuous_chk = ToggleSwitch(self.continuous_hlay)

        # Conecta atalhos do teclado
        self.actionOpenFile.setShortcut('Ctrl+A')
        self.actionNewWindow.setShortcut('Ctrl+N')
        self.stop_btn.setShortcut('Return')
        self.clear_btn.setShortcut('Ctrl+L')
        self.save_btn.setShortcut('Ctrl+S')
        self.apodization_btn.setShortcut('A')
        self.savgol_btn.setShortcut('S')
        self.mean_btn.setShortcut('M')
        for i, button in enumerate(self._list_fix_buttons()):
            button.setShortcut(f'{i+1}') # Atalhos 1-6 para fixar espectros

        # Tabs
        self.tabWidget.currentChanged.connect(self._on_tab_changed)

    def _default_channel_state(self) -> dict:
        """
        Retorna o estado inicial padrão para um canal/aba, 
        usado para inicializar novos canais ou resetar canais existentes.
        Returns:
            dict: Dicionário com o estado inicial padrão para um canal/aba.

        """
        return {
            'spectra_data': None,
            'roi_range': None,
            'temporal_roi_range': None,
            'results_df': {'Timestamp': [], 'Intensidade': [], 'Vale': []},
            'samples': {},
            'pending_hdf5': {'Timestamp': [], 'Intensidade': [], 'Vale': []},
            'fixed_traces': {},
            'active_traces': [],
            'error_messages': [],
            'add_legend': True,
        }

    def _enabled_tab_indices(self) -> list[int]:
        """
        Returns: 
            list[int]: Os índices das abas de canal atualmente habilitadas, ignorando a aba Merge.

        """
        merge_index = self.tabWidget.indexOf(getattr(self, 'tab_merge'))
        return [i for i in range(self.tabWidget.count()) if i != merge_index and self.tabWidget.isTabEnabled(i)]

    def _active_channel_number(self) -> int:
        """
        Returns:
            int: O número do canal ativo (1-4) com base no índice da aba ativa, ignorando a aba Merge.
        """
        return self.active_channel_idx + 1

    def _channel_index_from_number(self, channel: int) -> int:
        """
        Args:
            channel (int): Número do canal (1-4) para o qual se deseja obter o índice da aba.
        Returns:
            int: O índice da aba correspondente ao número do canal (1-4), ignorando a aba Merge.

        """
        merge_index = self.tabWidget.indexOf(getattr(self, 'tab_merge'))
        channel_tabs = [i for i in range(self.tabWidget.count()) if i != merge_index]
        return channel_tabs[channel - 1]

    def _save_active_channel_state(self, save_button_state: bool = True):
        """
        Salva o estado do canal ativo.
        Args:
            save_button_state (bool): Se True, salva o estado dos botões de fixação. Caso contrário, mantém o estado atual dos botões.
        
        """
        state = self.channel_states.get(self.active_channel_idx, self._default_channel_state())
        active_traces = [str(btn) for btn in self._list_fix_buttons() if btn.isChecked()] if save_button_state else state.get('active_traces', [])
        self.channel_states[self.active_channel_idx] = {
            'spectra_data': self.spectra_data or [],
            'roi_range': self.roi_range,
            'temporal_roi_range': self.temporal_roi_region.getRegion() if self.temporal_roi_region is not None else None,
            'results_df': self.results_df,
            'samples': self.samples,
            'pending_hdf5': self.pending_hdf5,
            'fixed_traces': self.fixed_traces,
            'active_traces': active_traces,
            'error_messages': self.error_messages,
        }

    def _restore_channel_state(self, index: int):
        """
        Restaura o estado de um canal específico.
        Args:
            index (int): Índice do canal/aba a ser restaurado.
        
        """
        state = self.channel_states.setdefault(index, self._default_channel_state())
        self.active_channel_idx = index
        self.spectra_data = state['spectra_data']
        self.roi_range = state['roi_range']
        temporal_roi_range = state.get('temporal_roi_range')
        self.results_df = state['results_df']
        self.samples = state['samples']
        self.pending_hdf5 = state['pending_hdf5']
        self.fixed_traces = state['fixed_traces']
        self.active_traces = state['active_traces']
        self.error_messages = state['error_messages']

        if temporal_roi_range is not None and self.temporal_roi_region is not None:
            self.temporal_roi_region.setRegion(temporal_roi_range)

        self._sync_fix_buttons_ui()

    def _sync_fix_buttons_ui(self):
        """
        Sincroniza a interface dos botões de fixação com o estado atual.
        
        """
        for i, button in enumerate(self._list_fix_buttons()):
            has_trace = str(button) in self.fixed_traces
            checked = has_trace and str(button) in self.active_traces
            button.setChecked(checked)

            item = self.fixedLines_vlay.itemAt(i)
            line = item.widget()
            if has_trace:
                color = button.palette().color(QPalette.ColorRole.Button)
                line.setStyleSheet(
                    f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, 255)")
            else:
                line.setStyleSheet("background-color: transparent")

    def _refresh_active_channel_view(self, sync_buttons: bool = True):
        """
        Atualiza a visualização do canal ativo.
        Args:
            sync_buttons (bool): Se True, sincroniza o estado dos botões de fixação. Caso contrário, mantém o estado atual dos botões.
        
        """
        self.spectraPlotWidget.clear()
        self.spectraPlotWidget.addItem(self.roi_region)
        self.temporalPlotWidget.clear()
        self.temporalPlotWidget.addItem(self.temporal_roi_region)
        self.boxPlot.clear()
        self.boxLegend.clear()

        if self.roi_range is not None:
            self.roi_region.setRegion(self.roi_range)

        temporal_roi_range = self.channel_states[self.active_channel_idx].get('temporal_roi_range')
        if temporal_roi_range is not None:
            self.temporal_roi_region.setRegion(temporal_roi_range)

        if sync_buttons:
            self._sync_fix_buttons_ui()

        if self.spectra_data:
            x, y = zip(*self.spectra_data)
            self._plot_spectrum_curve(np.asarray(x, dtype=float), np.asarray(y, dtype=float))

        if self.results_df['Timestamp']:
            self._update_plots_with_results()
        elif self.samples:
            self.update_box_plot()

        if self.file_path:
            self.setWindowTitle(f"Análise de dados - {os.path.basename(self.file_path)}")
        else:
            self.setWindowTitle("Análise de dados")

    def _request_cycle_data(self):
        """
        Solicita dados cíclicos da thread de aquisição para os canais habilitados. 
        
        """
        if (not self._running) or self._is_stopping or self.worker is None or self.thread is None:
            return

        if self.enabled_channels:
            for tab_idx in self.enabled_channels:
                self.request_data_signal.emit(self.mean_samples, tab_idx + 1)
            return

        self.request_data_signal.emit(self.mean_samples, int(self.cfg_spin.value()))

    def _on_tab_changed(self, index: int):
        """
        Event handler chamado quando o usuário muda de aba.
        Args:
            index (int): Índice da aba selecionada.

        """
        self._save_active_channel_state()
        self.main_qwt.setParent(None) # Remove o gráfico da hierarquia atual

        if index == self.tabWidget.indexOf(getattr(self, 'tab_merge')):
            self._refresh_merge_views()
            return

        self._restore_channel_state(index)
        self.tabWidget.widget(index).layout().addWidget(self.main_qwt) # Adiciona o container principal à aba selecionada
        self._refresh_active_channel_view(sync_buttons=False)

    def _unit_to_meter_factor(self, unit: str) -> float:
        """
        Args:
            unit (str): Unidade de comprimento ('m', 'um', 'nm', 'pm').
        Returns:
            float: o fator de conversão para converter valores para metros.

        """
        factors = {
            'm': 1.0,
            'um': 1e-6,
            'nm': 1e-9,
            'pm': 1e-12,
        }
        return factors.get(unit, 1e-9)

    def _set_spectrum_axis_unit(self):
        """
        Seleciona a unidade do eixo X do gráfico de espectro com base na configuração atual e atualiza o rótulo do eixo.

        """
        unit_label = {
            'm': 'm',
            'um': 'μm',
            'nm': 'nm',
            'pm': 'pm',
        }.get(self.xUnit, 'nm')
        self.spectraPlotWidget.setLabel('bottom', text='Comprimento de Onda', units=unit_label)

    def _from_meter(self, values, unit: str):
        """
        Returns:
            float: O fator de conversão para converter de metros para a unidade especificada.

        """
        return np.asarray(values, dtype=float) / self._unit_to_meter_factor(unit)

    def select_apodization_method(self):
        """
        Abre um diálogo para selecionar o método de apodização a ser aplicado no espectro, ou 'None' para desabilitar a apodização.

        """
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
        logger.info(f"Método de apodização selecionado: {self.apodization or 'None'}")

        if self.spectra_data:
            x, y = zip(*self.spectra_data)
            self._plot_spectrum_curve(np.asarray(x, dtype=float), np.asarray(y, dtype=float))

    def select_savgol_parameters(self):
        """
        Abre um diálogo para configurar os parâmetros do filtro Savitzky-Golay (tamanho da janela e grau do polinômio).

        """
        dialog = QDialog(self)
        dialog.setWindowTitle('Filtro Savitzky-Golay')

        layout = QFormLayout(dialog)

        window_spin = QSpinBox(dialog)
        window_spin.setRange(3, 1000)
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
        """
        Abre um diálogo para selecionar o número de espectros a serem utilizados na média espectral.

        """
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
        """
        Cria um pincel com gradiente para representar a faixa visível do espectro.
        Args:
            x_values (np.ndarray): Array de valores do eixo X (comprimento de onda) para o espectro atual.
        Returns:
            QBrush: Pincel com gradiente colorido para a faixa visível, ou None se os valores de x forem inválidos.

        """
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
        clamp_rel = lambda p: float(np.clip(p, 0.0, 1.0))

        gradient.setColorAt(0.0, transparent)
        gradient.setColorAt(clamp_rel(start_rel - eps), transparent)

        # Espectro visível
        for wl_nm, color_hex in spectrum_stops_nm:
            wl = float(self._from_meter(np.array([wl_nm * 1e-9]), self.xUnit)[0])
            rel = (wl - x_min) / span

            if 0.0 <= rel <= 1.0:
                gradient.setColorAt(clamp_rel(rel), QColor(color_hex))

        gradient.setColorAt(clamp_rel(end_rel + eps), transparent)
        gradient.setColorAt(1.0, transparent)

        return QBrush(gradient)

    def _plot_spectrum_curve(self, x_values: np.ndarray, y_values: np.ndarray):
        """
        Plota o(s) espectro(s) e um preenchimento colorido para a faixa visível.
        Args:
            x_values (np.ndarray): Array de valores do eixo X (comprimento de onda) para o espectro atual.
            y_values (np.ndarray): Array de valores do eixo Y (intensidade) para o espectro atual.
        
        """
        self.spectraPlotWidget.clear()
        self.spectraPlotWidget.addItem(self.roi_region)

        y_values = preprocess_plot_data(y_values, self.apodization_methods, 
                                        self.savgol_window_points, self.savgol_polyorder, self.apodization)

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
                x = np.asarray(self.fixed_traces[str(button)][0], dtype=float)
                y = preprocess_plot_data(np.asarray(self.fixed_traces[str(button)][1], dtype=float), self.apodization_methods, 
                                         self.savgol_window_points, self.savgol_polyorder, self.apodization)
                self.spectraPlotWidget.plot(x, y, pen=pg.mkPen(color, width=1, style=Qt.PenStyle.DashLine))

    def _list_fix_buttons(self) -> list[QPushButton]:
        """
        Returns:
            list: lista com os botões de fixação presentes na interface.

        """
        buttons = []
        for i in range(self.fixedTraces_vlay.count()):
            item = self.fixedTraces_vlay.itemAt(i)
            widget = item.widget()
            buttons.append(widget)
        return buttons

    def set_theme(self, theme: str):
        """
        Aplica tema claro/escuro para widgets Qt e gráficos pyqtgraph.
        Args:
            theme (str): Nome do tema a ser aplicado ('light' ou 'dark').

        """
        if theme not in ('light', 'dark'):
            return
        if theme == self.theme:
            self.actionLight.setChecked(theme == 'light')
            self.actionDark.setChecked(theme == 'dark')
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
        
        for plot_widget, _ in getattr(self, 'merge_plot_specs', []):
            plot_widget.setBackground(self.theme_colors['plot_bg'])

        for plot_widget in (self.spectraPlotWidget, self.temporalPlotWidget, *[spec[0] for spec in getattr(self, 'merge_plot_specs', [])]):
            item = plot_widget.getPlotItem()
            item.getAxis('left').setPen(pg.mkPen(self.theme_colors['axis']))
            item.getAxis('left').setTextPen(pg.mkPen(self.theme_colors['axis']))
            item.getAxis('bottom').setPen(pg.mkPen(self.theme_colors['axis']))
            item.getAxis('bottom').setTextPen(pg.mkPen(self.theme_colors['axis']))

        if self.roi_region:
            self.roi_region.setBrush(self.theme_colors['roi_spec'])
            self.temporal_roi_region.setBrush(self.theme_colors['roi_temp'])

        if self.results_df['Timestamp']:
            self._update_plots_with_results()

        self._refresh_merge_views()

    def open_file(self):
        """
        Abre um diálogo para seleção do arquivo de dados e carrega os dados selecionados.
        
        """
        file_path = prompt_open_file(self)
        if not file_path:
            return

        self.load_file(file_path)

    def open_new_window(self):
        """
        Abre nova janela limpa e fecha o arquivo atual, se houver.

        """
        merge_index = self.tabWidget.indexOf(getattr(self, 'tab_merge'))
        self.channel_states = {
            i: self._default_channel_state()
            for i in range(self.tabWidget.count())
            if i != merge_index
        }
        current_index = self.tabWidget.currentIndex()
        if current_index == merge_index:
            enabled_tabs = self._enabled_tab_indices()
            current_index = enabled_tabs[0] if enabled_tabs else 0
            self.tabWidget.setCurrentIndex(current_index)
        self._restore_channel_state(current_index)
        self.clear_plot()
        self.boxPlot.clear()
        self.boxLegend.clear()
        self._refresh_merge_views()
        self.setWindowTitle("Análise de dados")

    def load_config(self, config: dict):
        """
        Recebe os dados de configuração da ConfigWindow, habilita as abas e inicia a leitura dos espectros.
        
        Args:
            config_data (Dict): Dicionário contendo os parâmetros de configuração.
            
        """
        channels = config.get('channels')
        merge_index = self.tabWidget.indexOf(getattr(self, 'tab_merge'))
        channel_tabs = [i for i in range(self.tabWidget.count()) if i != merge_index]
        for channel_pos, tab in enumerate(channel_tabs):
            enabled = bool(channels[channel_pos]) if channel_pos < len(channels) else False
            self.tabWidget.setTabEnabled(tab, enabled) # Habilita as abas selecionas na configuração

        self.channel_states = {
            i: self._default_channel_state()
            for i in channel_tabs
        }
        self.enabled_channels = self._enabled_tab_indices()

        first_enabled = self.enabled_channels[0] if self.enabled_channels else 0
        self.tabWidget.setCurrentIndex(first_enabled)
        self._restore_channel_state(first_enabled)
        self._refresh_active_channel_view()
        self._refresh_merge_views()

        self.config_data = config
        self._run()
        QApplication.instance().restoreOverrideCursor()

    def unit_changed(self, unit: str):
        """
        Callback chamado quando a unidade do eixo X é alterada.
        Atualiza os dados e os gráficos para refletir a nova unidade.
        Args:
            unit (str): Nova unidade selecionada ('m', 'um', 'nm', 'pm').
        
        """
        old_unit = self.xUnit
        if unit == old_unit:
            self.actionM.setChecked(unit == 'm')
            self.actionUm.setChecked(unit == 'um')
            self.actionNm.setChecked(unit == 'nm')
            self.actionPm.setChecked(unit == 'pm')
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

        for tab_idx, state in self.channel_states.items():
            roi_range = state.get('roi_range')
            if roi_range is not None:
                state['roi_range'] = [roi_range[0] * scale_old_to_new, roi_range[1] * scale_old_to_new]

            spectra = state.get('spectra_data')
            if spectra:
                x_old, y_vals = zip(*spectra)
                x_new = np.asarray(x_old, dtype=float) * scale_old_to_new
                y_new = np.asarray(y_vals, dtype=float)
                state['spectra_data'] = list(zip(x_new, y_new))

            fixed_traces = state.get('fixed_traces', {})
            for btn, trace in list(fixed_traces.items()):
                x_old, y_vals = trace
                x_new = np.asarray(x_old, dtype=float) * scale_old_to_new
                fixed_traces[btn] = (x_new, np.asarray(y_vals, dtype=float))

            if tab_idx == self.active_channel_idx:
                self._restore_channel_state(tab_idx)

        self._refresh_active_channel_view()
        self._refresh_merge_views()

    def _run(self):
        """
        Inicia a thread de aquisição de dados.

        """
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

        # Obtém a instância compartilhada, se necessário
        if self.osa is None and 'THORLABS' in inter:
            self.osa = self.config_data.get('sdk')

        # Inicia a thread de aquisição de dados
        self.thread = QThread()
        switch_ports = self.config_data.get('switch_ports', [])
        self.worker = DataAcquisition(inter, ip, port, osa=self.osa, switch_ports=switch_ports)
        self.worker.moveToThread(self.thread)

        # Conecta os sinais e slots da thread e do worker
        self.thread.started.connect(self.worker.run)
        self.thread.started.connect(self._thread_started)
        self.request_data_signal.connect(self.worker.request_data, Qt.QueuedConnection)
        self.stop_worker_signal.connect(self.worker.stop, Qt.QueuedConnection)
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
        self.continuous_lbl.setEnabled(False)
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
        self.timer.timeout.connect(self._request_cycle_data)
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
                self.cfg_lbl.setText("Tempo de Exposição (µs)")
                self.cfg_spin.setRange(1000, 30000000) # Limita o tempo de exposição
                self.cfg_spin.setSingleStep(100)
            case 'THORLABS OSA203':
                self.cfg_lbl.setText("Tempo de Exposição (µs)")
                self.exposure_time = -1

        if self.exposure_time >= 0:
            if self.exposure_time == 0:
                self.cfg_spin.setValue(self.worker.get_exposure_time()) # Obtém o tempo de exposição atual
                self.exposure_time = self.cfg_spin.value()
            elif self.exposure_time != self.cfg_spin.value():
                self.worker.set_exposure_time(self.cfg_spin.value()) # Altera o tempo de exposição
                self.exposure_time = self.cfg_spin.value()

    def _pause_thread(self):
        """
        Pausa a aquisição sem fechar o hardware para permitir retomada imediata.

        """
        if self.timer is not None and self.timer.isActive():
            self.timer.stop()

        if self.worker is not None:
            try:
                self.worker.pause()
            except Exception:
                pass

        self._running = False
        self.stop_btn.setText("Retomar")
        self.stop_btn.setStyleSheet("QPushButton { background-color: #60fa93; color: #0f172a; }")
        self.sr_spin.setEnabled(True)
        self.sr_lbl.setEnabled(True)
        if self.config_data.get('inter') != 'THORLABS OSA203':
            self.cfg_spin.setEnabled(True)
            self.cfg_lbl.setEnabled(True)
        self.continuous_chk.setEnabled(True)
        self.continuous_lbl.setEnabled(True)
        QApplication.instance().restoreOverrideCursor()
        self.stop_btn.setEnabled(True)

    def _resume_thread(self):
        """
        Retoma a aquisição usando a mesma thread/worker já inicializados.

        """
        if self.thread is None or self.worker is None:
            self._run()
            return

        # Reaplica o modo contínuo sem recriar thread/worker para evitar
        # fechamento e reabertura da porta serial no Retomar.
        if self.continuous_chk.isChecked():
            if self.continuous_timer is None:
                if not self.continuous_cfg():
                    QApplication.instance().restoreOverrideCursor()
                    self.stop_btn.setEnabled(True)
                    return
            if self.continuous_timer is not None and self.sample_duration is not None:
                self.continuous_timer.start(self.sample_duration * 1000)
        elif self.continuous_timer is not None:
            if self.continuous_timer.isActive():
                self.continuous_timer.stop()
            try:
                self.continuous_timer.timeout.disconnect()
            except Exception:
                pass
            self.continuous_timer.deleteLater()
            self.continuous_timer = None

        try:
            self.worker.resume()
        except Exception:
            pass

        self.sample_rate = self.sr_spin.value()

        if self.timer is None:
            self.timer = QTimer(self)
            self.timer.timeout.connect(self._request_cycle_data)
        self.timer.start(self.sample_rate)

        self._running = True
        self.stop_btn.setText("Parar")
        self.stop_btn.setStyleSheet("QPushButton { background-color: #fd4d4d; color: white; }")
        self.cfg_spin.setEnabled(False)
        self.cfg_lbl.setEnabled(False)
        self.sr_spin.setEnabled(False)
        self.sr_lbl.setEnabled(False)
        self.continuous_chk.setEnabled(False)
        self.continuous_lbl.setEnabled(False)

    def _show_error(self, title: str, message: str):
        """
        Mostra uma caixa de diálogo de erro de forma não-bloqueante.
        Args:
            title (str): Título da caixa de diálogo.
            message (str): Mensagem de erro a ser exibida.
        
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
        Args:
            message (str): Mensagem de aviso a ser exibida.
        
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
                cur_dir = os.path.dirname(os.path.abspath(argv[0]))
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
        """
        Obtém o espectro fixado associado ao botão, remove-o da lista de espectros fixados e atualiza a interface.
        Args:
            button (QPushButton): Botão de fixação cujo espectro deve ser removido.

        """
        self.fixed_traces.pop(str(button), None)

        idx = self._list_fix_buttons().index(button)
        item = self.fixedLines_vlay.itemAt(idx)
        line = item.widget()
        line.setStyleSheet("background-color: transparent")
        if button.isChecked():
            button.setChecked(False)
            if not self._running:
                x_vals, y_vals = zip(*self.spectra_data)
                # Redesenha o espectro atual para limpar as curvas fixadas
                self._plot_spectrum_curve(np.asarray(x_vals, dtype=float), np.asarray(y_vals, dtype=float))
            self._save_active_channel_state()
        self._refresh_merge_views()

    def toggle_fix(self, button: QPushButton, pos):
        """
        Callback para exibir um menu de contexto ao clicar com o botão direito em um botão de fixação, 
        permitindo remover o espectro fixado.

        """
        menu = QMenu()

        if str(button) in self.fixed_traces:
            menu.addAction("Remover")
            menu.triggered.connect(lambda: self._update_fixed_list(button))
            menu.exec_(button.mapToGlobal(pos))

    def fix_btn_clicked(self, button: QPushButton, checked: bool):
        """
        Gerencia a lógica de fixar/desfixar um espectro ao clicar nos botões de fixação.
        Args:
            button (QPushButton): Botão de fixação que foi clicado.
            checked (bool): Estado do botão após o clique (True se marcado, False se desmarcado).

        """
        if str(button) in self.fixed_traces:
            if not self._running:
                if checked:
                    x, y = self.fixed_traces[str(button)]
                    color = button.palette().color(QPalette.ColorRole.Button)
                    self.spectraPlotWidget.plot(x, 
                                                preprocess_plot_data(y, self.apodization_methods, 
                                                    self.savgol_window_points, self.savgol_polyorder, self.apodization),
                                                pen=pg.mkPen(color, width=1))
                else:
                    x_vals, y_vals = zip(*self.spectra_data)
                    # Redesenha o espectro atual para limpar as curvas fixadas
                    self._plot_spectrum_curve(np.asarray(x_vals, dtype=float), np.asarray(y_vals, dtype=float))
        elif checked:
            if self.spectraPlotWidget.getPlotItem().listDataItems() == []:
                button.setChecked(False) # Impede de marcar se não houver espectro para fixar
                return
            x, y = zip(*self.spectra_data)
            self.fixed_traces[str(button)] = (np.asarray(x, dtype=float), np.asarray(y, dtype=float))

            idx = self._list_fix_buttons().index(button)
            item = self.fixedLines_vlay.itemAt(idx)
            line = item.widget()
            color = button.palette().color(QPalette.ColorRole.Button)
            line.setStyleSheet(
                f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, 255)"
            )
            if not self._running:
                color = button.palette().color(QPalette.ColorRole.Button)
                self.spectraPlotWidget.plot(x, 
                                            preprocess_plot_data(y, self.apodization_methods, 
                                                self.savgol_window_points, self.savgol_polyorder, self.apodization),
                                            pen=pg.mkPen(color, width=1))
        else:
            idx = self._list_fix_buttons().index(button)
            item = self.fixedLines_vlay.itemAt(idx)
            line = item.widget()
            if str(button) in self.fixed_traces:
                color = button.palette().color(QPalette.ColorRole.Button)
                line.setStyleSheet(
                    f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, 90)"
                )
        self._save_active_channel_state()
        self.active_traces = [str(btn) for btn in self._list_fix_buttons() if btn.isChecked()]
        self._refresh_merge_views()
            
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
                self.worker.stop()
            except Exception:
                pass
            try:
                self.stop_worker_signal.emit()
            except Exception:
                pass
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
            try:
                self.stop_worker_signal.disconnect(self.worker.stop)
            except:
                pass
            
        if self.thread is not None:
            self.thread.requestInterruption()
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
        self.continuous_lbl.setEnabled(True)
        QApplication.instance().restoreOverrideCursor()
        self.stop_btn.setEnabled(True)

    def roi_changed(self):
        """
        Callback chamado quando a região de interesse (ROI) é alterada.
        Atualiza o box plot mesmo com a aquisição parada.
        
        """
        if self.temporal_roi_region is not None:
            self.channel_states[self.active_channel_idx]['temporal_roi_range'] = self.temporal_roi_region.getRegion()

        if self.timer is None or not self.timer.isActive():
            self._update_plots_with_results()

    def _spectrum_roi_changed(self):
        if self.roi_region is not None:
            roi_min, roi_max = self.roi_region.getRegion()
            self.roi_range = [roi_min, roi_max]
            if self.active_channel_idx in self.channel_states:
                self.channel_states[self.active_channel_idx]['roi_range'] = self.roi_range

    def toggle_thread(self):
        """
        Inicia ou para a thread de aquisição de dados com lógica de toggle.
        
        """
        if not self.continuous_chk.isChecked():
            QApplication.instance().setOverrideCursor(Qt.WaitCursor)
            self.stop_btn.setEnabled(False) # Evita múltiplos cliques durante a transição
        try:
            if self.continuous_timer is not None:
                self._flush_continuous_buffer(force=True)
                self._cleanup_thread()
                QMessageBox.warning(self, "Amostra Contínua", "Amostra contínua interrompida pelo usuário.")
            elif self.thread is not None:
                if self._running:
                    self._pause_thread()
                else:
                    self._resume_thread()
            else:
                self._run()
        except Exception:
            QApplication.instance().restoreOverrideCursor()
            self.stop_btn.setEnabled(True)
            raise

    def continuous_timer_shot(self):
        """
        Callback chamado quando o timer da amostra contínua dispara.
        Para a aquisição de dados e informa o usuário.
        
        """
        self._flush_continuous_buffer(force=True)
        QMessageBox.information(
            self,
            "Amostra Contínua",
            f"A amostra \"{self.sample_name}\" coletada por {self.sample_duration} segundos foi salva com sucesso."
        )

    def _flush_continuous_buffer(self, force: bool = False):
        """
        Salva em lote o buffer do modo contínuo para reduzir overhead de I/O.
        Args:
            force (bool): Se True, força a gravação de todos os dados pendentes, ignorando o tamanho do lote.

        """
        targets = [self.active_channel_idx]
        if force and self.enabled_channels:
            targets = list(self.enabled_channels)

        for idx in targets:
            state = self.channel_states.get(idx)
            if state is None:
                continue

            pending = state['pending_hdf5']
            pending_count = len(pending['Timestamp'])
            if pending_count == 0:
                continue
            if not force and pending_count < self.flush_batch_size:
                continue

            try:
                inter = self.config_data.get('inter') if self.config_data else None
                file_path = self.file_path or (self.config_data.get('path') if self.config_data else None)
                if not inter or not file_path:
                    continue

                intensities = np.asarray(pending['Intensidade'], dtype=np.float32)
                timestamps = np.asarray(pending['Timestamp'], dtype=np.float64)
                valleys = np.asarray(pending['Vale'], dtype=np.float64)

                append_hdf5_samples(
                    range_cfg=self.config_data.get('range'),
                    res=self.config_data.get('res'),
                    file_path=file_path,
                    inter=inter,
                    intensities=intensities,
                    timestamps=timestamps,
                    valleys=valleys,
                    sample_name=self.sample_name or "Atual"
                )

                state['pending_hdf5'] = {'Timestamp': [], 'Intensidade': [], 'Vale': []}
                if idx == self.active_channel_idx:
                    self.pending_hdf5 = state['pending_hdf5']
                logger.debug(f"Flush contínuo realizado no canal {idx + 1} com {pending_count} registro(s).")
            except Exception as e:
                logger.error(f"Erro ao salvar buffer contínuo (canal {idx + 1}): {e}")

    def update_plot(self, data, warning, channel: int):
        """
        Atualiza o gráfico com os dados adquiridos.
        Args:
            data (list of tuples): Lista de tuplas contendo os dados do espectro (x, y).
            warning (str): Mensagem de aviso a ser exibida, se houver.
            channel (int): Número do canal de onde os dados foram adquiridos.
        
        """
        if not self._running:
            return

        QApplication.instance().restoreOverrideCursor()
        self.stop_btn.setEnabled(True)
        self._show_warning(warning)

        target_idx = self._channel_index_from_number(channel)
        if target_idx not in self.channel_states:
            self.channel_states[target_idx] = self._default_channel_state()

        current_visible_idx = self.active_channel_idx
        self._save_active_channel_state()
        self._restore_channel_state(target_idx)
        
        x, y = zip(*data)
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        # Converte de nm para a unidade configurada, caso necessário
        x *= self._unit_to_meter_factor('nm') / self._unit_to_meter_factor(self.xUnit)
        self._set_spectrum_axis_unit()

        self.spectra_data = list(zip(x, y))
        self._plot_spectrum_curve(x, y)

        if self.roi_range is None:
            x_min = min(x)
            x_max = max(x)
            x_range = x_max - x_min
            self.roi_range = [(x_min+0.25*x_range), x_max-0.25*x_range] # Intervalo fixo
            self.roi_region.setRegion(self.roi_range)
            logger.debug(f"ROI inicial definida para: {self.roi_range}")

        self.process_spectra()

        self._save_active_channel_state(save_button_state=False)
        if target_idx != current_visible_idx:
            self._restore_channel_state(current_visible_idx)
            self._refresh_active_channel_view(sync_buttons=False)

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
    
    def _update_plots_with_results(self):
        """
        Atualiza os gráficos para exibir os resultados processados.
        - Plota os pontos no gráfico de evolução temporal.
        - Desenha linhas verticais nos picos encontrados no gráfico de espectros.
        
        """
        if not self.results_df['Timestamp']:
            if not self.samples:
                logger.warning("Nenhum resultado para exibir nos gráficos.")
            else:
                self.update_box_plot()
            return

        # --- Atualiza Gráfico 2: Evolução Temporal ---
        self.temporalPlotWidget.clear()
        
        # pyqtgraph precisa de timestamps numéricos (Unix timestamp) para o eixo de datas
        timestamps_numeric = self.results_df['Timestamp']

        valleys_m = np.asarray(self.results_df['Vale'], dtype=float)
        resonant_temporal = self._from_meter(valleys_m, self.resultUnit)
        resonant_spectrum = self._from_meter(valleys_m, self.xUnit)
        
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
        boxplot_valleys = [resonant_temporal[i] for i in range(len(resonant_temporal)) if mask[i]]

        if not boxplot_valleys and timestamps_numeric:
            logger.warning("ROI temporal vazia para box plot, nada a plotar.")
            return

        self.update_box_plot(boxplot_valleys)

    def update_box_plot(self, boxplot_valleys: list = None):
        """
        Atualiza o box plot com os dados processados.
        Args:
            boxplot_valleys (list): Lista de valores com as estatísticas para o box plot.
            
        """
        self.boxPlot.clear()
        self.boxLegend.clear()

        samples = list(self.samples.items())
        if boxplot_valleys:
            samples.append(("Atual", self.box_plot_statistics(boxplot_valleys)))

        y_values = []
        for i, (sample_name, stats) in enumerate(samples):
            q1, q2, q3, lower_whisker, upper_whisker, outliers = stats
            y_values.extend([q1, q2, q3, lower_whisker, upper_whisker]) # amostras anteriores

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
            legend = pg.PlotDataItem([0], [1], pen=None, symbol='s', symbolBrush=pg.mkBrush(rgb))
            self.boxLegend.addItem(legend, sample_name)

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
        
        if y_values:
            self.boxPlot.setYRange(min(y_values) - 1, max(y_values) + 1)

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
        self.pending_hdf5 = {'Timestamp': [], 'Intensidade': [], 'Vale': []}
        self.spectra_data = []
        self.roi_range = None
        self.fixed_traces = {}
        self._sync_fix_buttons_ui()
        self._save_active_channel_state()
        self._refresh_merge_views()
        logger.info("Gráficos limpos.")

    def _prompt_sample_name(self) -> tuple[str, bool]:
        """
        Abre diálogo para entrada do nome da amostra com sugestões.
        As sugestões são baseadas nas amostras já carregadas do arquivo aberto.
        Returns:
            tuple: (nome_da_amostra, ok) ou ("", False) se o usuário cancelar a entrada.

        """
        dialog = QInputDialog(self)
        dialog.setWindowModality(Qt.WindowModal)
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
        Abre um diálogo para selecionar um arquivo. Se o arquivo já existir,
        anexa os novos dados; caso contrário, cria um novo arquivo.
        Os dados são filtrados pela ROI temporal antes de serem salvos.
        
        """
        # --- Passo 1: Validação inicial ---
        if not self.results_df['Timestamp']:
            logger.warning("Tentativa de salvar sem dados processados.")
            QMessageBox.warning(self, "Atenção", "Não há dados processados para salvar.")
            return

        logger.info("Iniciando processo para salvar dados.")

        # --- Passo 2: Abre diálogo para inserir o nome da amostra ---
        sample_name, ok = self._prompt_sample_name()

        if not ok:
            return # Usuário cancelou a entrada do nome da amostra

        # --- Passo 3: Obtém o caminho do arquivo do usuário ---
        file_path = self.file_path or self.config_data.get('path')
        if file_path is not None:
            logger.info(f"Usando caminho de arquivo pré-configurado: {file_path}")
        else:
            file_path = prompt_save_file(self)

            if not file_path:
                logger.info("Operação de salvamento cancelada pelo usuário.")
                return

        # --- Passo 4: Processa e filtra os dados da ROI ---
        try:
            roi_min_ts, roi_max_ts = self.temporal_roi_region.getRegion()

            timestamps = np.asarray(self.results_df['Timestamp'], dtype=np.float64)
            intensities = self.results_df['Intensidade']
            valleys = np.asarray(self.results_df['Vale'], dtype=np.float64)

            
            mask = (timestamps >= roi_min_ts) & (timestamps <= roi_max_ts)

            timestamps_filtered = timestamps[mask]
            intensities_filtered = np.asarray(
                [intensities[i] for i in range(len(intensities)) if mask[i]],
                dtype=np.float32
            )
            resonant_filtered = valleys[mask]

            if not timestamps_filtered.any():
                logger.warning("A região selecionada não contém dados para salvar.")
                QMessageBox.warning(self, "Atenção", "A região selecionada não contém dados para salvar.")
                return

            inter = self.config_data.get('inter')

            logger.debug(f"Salvando {len(intensities_filtered)} espectros")

            append_hdf5_samples(
                range_cfg=self.config_data.get('range'),
                res=self.config_data.get('res'),
                file_path=file_path,
                inter=inter,
                intensities=intensities_filtered,
                timestamps=timestamps_filtered,
                valleys=resonant_filtered,
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
            self._save_active_channel_state()

        except Exception as e:
            logger.error(f"Falha ao processar ou salvar os dados: {e}")
            QMessageBox.critical(self, "Erro", f"Ocorreu um erro ao salvar o arquivo:\n{e}")

    def load_file(self, file_path: str):
        """
        Carrega dados de amostras de um arquivo HDF5 para análise.

        Args:
            file_path (str): Caminho do arquivo HDF5 contendo os dados das amostras.
            
        """
        try:
            inter = self.config_data.get('inter')
            data = load_hdf5_samples(file_path, inter)

            for sample_name, sample_wavelengths in data.items():
                sample_wavelengths = np.asarray(sample_wavelengths, dtype=float)
                sample_wavelengths = self._from_meter(sample_wavelengths, self.resultUnit)

                self.samples[sample_name] = self.box_plot_statistics(sample_wavelengths)

            if not self.samples:
                raise ValueError("Nenhum dado de amostra encontrado no arquivo.")
            
            self.update_box_plot() # Atualiza os gráficos com os box plots carregados
            self.setWindowTitle(f"Análise de dados - {os.path.basename(file_path)}")
            self.file_path = file_path
            self._save_active_channel_state()
            logger.info(f"Dados carregados com sucesso do arquivo: {file_path}. {len(self.samples)} amostra(s) encontrada(s).")

        except Exception as e:
            logger.error(f"Erro ao carregar o arquivo {file_path}: {e}")
            QMessageBox.critical(self, "Erro", f"Não foi possível carregar o arquivo:\n{e}")

    def continuous_cfg(self) -> bool:
        """
        Configura a aquisição contínua de dados.
        Abre diálogos para o usuário inserir o nome da amostra, o caminho de salvamento e a duração da amostra.
        Returns:
            bool: True se a configuração foi concluída com sucesso, False se o usuário cancelou em alguma etapa.
        
        """
        # Abre diálogo para inserir o nome da amostra ---
        self.sample_name, ok = self._prompt_sample_name()

        if not ok:
            return False # Usuário cancelou a entrada do nome da amostra

        # Obtém o caminho do arquivo do usuário ---
        file_path = prompt_save_file(self) if self.file_path is None else self.file_path

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
        if self.enabled_channels:
            for idx in self.enabled_channels:
                self.channel_states[idx]['file_path'] = file_path
        logger.debug(f"Caminho de salvamento definido para o modo contínuo: {file_path}")
        
        self.clear_plot()
        # Interrompe a aquisição após a duração especificada
        if self.continuous_timer is not None:
            if self.continuous_timer.isActive():
                self.continuous_timer.stop()
            self.continuous_timer.deleteLater()

        self.pending_hdf5 = {'Timestamp': [], 'Intensidade': [], 'Vale': []}
        self._save_active_channel_state()
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