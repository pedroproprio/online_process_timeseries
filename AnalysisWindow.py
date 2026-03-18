from PySide6.QtWidgets import QMainWindow, QFileDialog, QMessageBox, QGraphicsRectItem, QInputDialog, QDialog
from PySide6.QtCore import Signal, QThread, QTimer, Qt

from ui.AnalysisWindow_ui import Ui_AnalysisWindow
from processing import find_resonant_wavelength
from DataAcquisition import DataAcquisition

from scipy.interpolate import interp1d
from datetime import datetime
import pyqtgraph as pg
import numpy as np
import h5py

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
    request_data_signal = Signal(float)

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
        # Comprimentos de onda fixos para cada interface para interpolação (em metros)
        self.fixed_wavelengths = { # usando valores padrão para as resoluções
            'IBSEN IMON-512': np.arange(380e-9, 780e-9, .1e-9), 
            'BRAGGMETER FS22DI': np.arange(1500e-9, 1600e-9, .1e-9),
            'BRAGGMETER FS22DI HBM': np.arange(1500e-9, 1600e-9, .1e-9),
            'THORLABS CCT11': np.arange(350e-9, 700e-9, .1e-9),
            'THORLABS OSA203': np.arange(1450e-9, 1650e-9, .1e-9)}
        # Dicionário de listas para armazenar os resultados processados
        self.results_df = {'Timestamp': [], 'Intensidade': [], 'ComprimentoRessonante': []}
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
        self.pending_hdf5 = {'Timestamp': [], 'Intensidade': [], 'ComprimentoRessonante': []}
        # Tamanho do lote para flush no modo contínuo
        self.flush_batch_size: int = 25
        # Intervalo para flush automático no modo contínuo (ms)
        self.flush_interval_ms: int = 5000
        # Limite de pontos mantidos em memória para evitar lentidão da UI
        self.max_live_points: int = 5000
        
        self.thread: QThread | None = None
        self.worker: DataAcquisition | None = None
        self.timer: QTimer | None = None
        self._is_stopping = False
        
        # Instância compartilhada de PyCCT para evitar conflito de múltiplas instâncias
        self.osa = None

        self.setup_plot()
        self.setup_connections()

    def setup_plot(self):
        """
        Configura os widgets de gráfico da pyqtgraph.
        
        """
        # --- Configuração do gráfico: Espectro ---
        self.spectraPlotWidget.setBackground('w')
        self.spectraPlotWidget.setLabel('left', 'Potência', units='dBm')
        self.spectraPlotWidget.showGrid(x=False, y=True)
        xAxis = pg.AxisItem(orientation='bottom')
        xAxis.setLabel(text='Comprimento de Onda', units='nm')
        xAxis.enableAutoSIPrefix(False) # Mantém unidades em nm
        self.spectraPlotWidget.setAxisItems({'bottom': xAxis})

        # Adiciona a região de seleção (ROI)
        self.roi_region = pg.LinearRegionItem(orientation=pg.LinearRegionItem.Vertical)
        self.roi_region.setBrush([0, 0, 255, 50])
        self.spectraPlotWidget.addItem(self.roi_region)

        # --- Configuração do gráfico: Evolução Temporal ---
        self.temporalPlotWidget.setBackground('w')
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
        self.boxPlotWidget.setBackground('w')
        self.boxPlot = self.boxPlotWidget.addPlot()
        self.boxLegend = self.boxPlot.addLegend()
        self.boxPlot.setXRange(0, 2)
        self.boxPlot.getAxis('bottom').setTicks([]) # Remove os números do eixo X

    def setup_connections(self):
        """
        Conecta os sinais dos widgets (eventos) aos seus respectivos slots (métodos).
        
        """
        self.stop_btn.clicked.connect(self.toggle_thread) # Inicia/Para a aquisição de dados
        self.save_btn.clicked.connect(self.save_data) # Salva os dados processados
        self.clear_btn.clicked.connect(self.clear_plot) # Limpa os gráficos
        self.temporal_roi_region.sigRegionChanged.connect(self.roi_changed) # Atualiza o box plot mesmo com a aquisição parada

    def load_config(self, config: dict):
        """
        Recebe os dados de configuração da ConfigWindow e inicia a leitura dos espectros.
        
        Args:
            config_data (Dict): Dicionário contendo os parâmetros de configuração.
            
        """
        self.config_data = config
        self._run()

    def _run(self):
        if self.thread is not None:
            return
            
        port = self.config_data.get('port')
        inter = self.config_data.get('inter')
        path = self.config_data.get('path')
        ip = self.config_data.get('ip')

        if path != "None":
            logger.info(f"Carregando dados a partir do arquivo: {path}")
            self.load_file(path)

        if self.continuous_chk.isChecked():
            if not self.continuous_cfg():
                return

        # Inicializa a instância compartilhada de PyCCT, se necessário
        if self.osa is None:
            match inter:
                case 'THORLABS CCT11':
                    from pyCCT import PyCCT
                    self.osa = PyCCT()
                case 'THORLABS OSA203':
                    import pyOSA
                    self.osa = pyOSA.initialize()

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

        self.save_btn.setEnabled(False) # Desabilita o botão de salvar durante a aquisição
        self.stop_btn.setText("Parar")
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
        self.timer.timeout.connect(lambda: self.request_data_signal.emit(float(self.cfg_spin.value())))
        self.timer.start(self.sample_rate)

        match self.config_data.get('inter'):
            case 'IBSEN IMON-512':
                self.cfg_lbl.setText("Tempo de Exposição (µs)")
                self.cfg_spin.setRange(3, 65535) # Limita o tempo de exposição
                self.cfg_spin.setSingleStep(100)
            case 'BRAGGMETER FS22DI':
                self.cfg_lbl.setText("Canal")
                self.cfg_spin.setRange(2, 3) # Canais de transmissão do BraggMeter
                self.exposure_time = -1 # Desabilita a alteração do tempo de exposição
            case 'BRAGGMETER FS22DI HBM':
                self.cfg_lbl.setText("Canal")
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
        self.save_btn.setEnabled(True)
        self.stop_btn.setText("Retomar")
        self.sr_spin.setEnabled(True) # Habilita o controle de intervalo entre amostras
        self.sr_lbl.setEnabled(True)
        if self.config_data.get('inter') != 'THORLABS OSA203':
            self.cfg_spin.setEnabled(True) # Habilita o controle de tempo de exposição
            self.cfg_lbl.setEnabled(True)
        self.continuous_chk.setEnabled(True)

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
            resonant_wavelengths = np.asarray(self.pending_hdf5['ComprimentoRessonante'], dtype=np.float64)

            self._append_hdf5_records(
                file_path=file_path,
                inter=inter,
                intensities=intensities,
                timestamps=timestamps,
                resonant_wavelengths=resonant_wavelengths,
                sample_name=self.sample_name or "Atual"
            )

            self.pending_hdf5 = {'Timestamp': [], 'Intensidade': [], 'ComprimentoRessonante': []}
            logger.debug(f"Flush contínuo realizado com {pending_count} registro(s).")
        except Exception as e:
            logger.error(f"Erro ao salvar buffer contínuo: {e}")

    def update_plot(self, data):
        """
        Atualiza o gráfico com os dados adquiridos.
        
        """
        x, y = zip(*data)
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        # Converte de nm para a unidade configurada, caso necessário
        match self.config_data.get('x_unit'):
            case 'um':
                x *= 1e-3
                self.spectraPlotWidget.setLabel('bottom', units='μm')
            case 'm':
                x *= 1e-9
                self.spectraPlotWidget.setLabel('bottom', units='m')

        self.spectra_data = list(zip(x, y))
        self.spectraPlotWidget.clear()
        self.spectraPlotWidget.addItem(self.roi_region)
        self.spectraPlotWidget.plot(x, y, pen=pg.mkPen('b', width=1)) # Plota apenas valores positivos de x e y

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
        Executa o algoritmo de detecção de picos para todos os espectros na ROI.
        
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
        roi_m_min = roi_min * 1e-9
        roi_m_max = roi_max * 1e-9
        match self.config_data.get('x_unit'):
            case 'nm':
                wavelength *= 1e-9
            case 'um':
                wavelength *= 1e-6

        # 3. Chama a função do backend para encontrar o pico
        res_wl = find_resonant_wavelength(np.array(wavelength), np.array(power), roi_m_min, roi_m_max)
        
        # 4. Adiciona o resultado ao dicionário se um pico for encontrado
        if res_wl is not None:
            res_wl = float(res_wl)
            if len(self.results_df['Timestamp']) == 1:
                 self.spectraPlotWidget.autoRange() # Ajusta o gráfico na primeira medição
            now = datetime.now().timestamp()
            inter = self.config_data.get('inter')
            fixed_wavelengths = self.fixed_wavelengths.get(inter)
            if fixed_wavelengths is None:
                logger.warning(f"Interface desconhecida para interpolação: {inter}")
                return

            interp_fn = interp1d(
                wavelength,
                power,
                kind='linear',
                bounds_error=False,
                fill_value=(power[0], power[-1])
            )
            intensities = np.asarray(interp_fn(fixed_wavelengths), dtype=np.float32)

            self.results_df['Timestamp'].append(now)
            self.results_df['Intensidade'].append(intensities)
            self.results_df['ComprimentoRessonante'].append(res_wl)

            # Mantém apenas parte do histórico em memória para evitar degradação da UI.
            if self.continuous_chk.isChecked() and len(self.results_df['Timestamp']) > self.max_live_points:
                excess = len(self.results_df['Timestamp']) - self.max_live_points
                self.results_df['Timestamp'] = self.results_df['Timestamp'][excess:]
                self.results_df['Intensidade'] = self.results_df['Intensidade'][excess:]
                self.results_df['ComprimentoRessonante'] = self.results_df['ComprimentoRessonante'][excess:]

            if self.continuous_chk.isChecked():
                self.pending_hdf5['Timestamp'].append(now)
                self.pending_hdf5['Intensidade'].append(intensities)
                self.pending_hdf5['ComprimentoRessonante'].append(res_wl)
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
        Acrescenta registros no arquivo HDF5 no grupo da interface selecionada.
        """
        with h5py.File(file_path, "a") as f:
            if inter not in f:
                g = f.create_group(inter)
                spec_len = intensities.shape[1]

                g.create_dataset(
                    "Intensidades",
                    data=intensities,
                    maxshape=(None, spec_len),
                    dtype="float32",
                    chunks=(256, spec_len),
                    compression="gzip"
                )

                g.create_dataset(
                    "Timestamp",
                    data=timestamps,
                    maxshape=(None,),
                    dtype="float64",
                    chunks=True
                )

                g.create_dataset(
                    "ComprimentoRessonante",
                    data=resonant_wavelengths,
                    maxshape=(None,),
                    dtype="float64",
                    chunks=True
                )

                g.create_dataset(
                    "Amostra",
                    data=np.asarray([sample_name.encode()] * len(timestamps), dtype="S64"),
                    maxshape=(None,),
                    chunks=True
                )
                return

            g = f[inter]
            intensities_ds = g["Intensidades"]
            timestamps_ds = g["Timestamp"]
            wavelengths_ds = g["ComprimentoRessonante"]
            samples_ds = g["Amostra"]

            n_old = intensities_ds.shape[0]
            n_new = len(timestamps)

            intensities_ds.resize((n_old + n_new, intensities_ds.shape[1]))
            timestamps_ds.resize((n_old + n_new,))
            wavelengths_ds.resize((n_old + n_new,))
            samples_ds.resize((n_old + n_new,))

            intensities_ds[n_old:n_old+n_new] = np.asarray(intensities, dtype=np.float32)
            timestamps_ds[n_old:n_old+n_new] = np.asarray(timestamps, dtype=np.float64)
            wavelengths_ds[n_old:n_old+n_new] = np.asarray(resonant_wavelengths, dtype=np.float64)
            samples_ds[n_old:n_old+n_new] = np.asarray([sample_name.encode()] * n_new, dtype="S64")
    
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

        resonant_wavelengths = list(self.results_df['ComprimentoRessonante'])

        # converte novamente para a escala configurada
        match self.config_data.get('x_unit'):
            case 'nm':
                resonant_wavelengths = [i * 1e9 for i in resonant_wavelengths]
            case 'um':
                resonant_wavelengths = [i * 1e6 for i in resonant_wavelengths]
        resonant_wavelengths = np.array(resonant_wavelengths, dtype=float)
        
        # Plota os pontos e uma linha conectando-os
        self.temporalPlotWidget.plot(
            x=timestamps_numeric,
            y=resonant_wavelengths,
            pen={'color': 'b', 'width': 2},
            symbol='o',
            symbolBrush='r',
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
        line = pg.InfiniteLine(pos=resonant_wavelengths[-1], angle=90, movable=False, pen={'color': 'r', 'style': pg.QtCore.Qt.DashLine})
        self.spectraPlotWidget.addItem(line)
        logger.debug(f"Marcador de pico adicionado ao gráfico de espectros.")
        
        # Seleciona a ROI temporal atual para filtrar os dados computados pelo box plot
        roi_min_ts, roi_max_ts = self.temporal_roi_region.getRegion()
        mask = [(r >= roi_min_ts) and (r <= roi_max_ts) for r in timestamps_numeric]
        boxplot_resonant_wavelengths = [resonant_wavelengths[i] for i in range(len(resonant_wavelengths)) if mask[i]]

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
            self.boxPlot.plot([0.75+i, 1.25+i], [q2, q2], pen=pg.mkPen('r', width=2))
            #Linha vertical
            self.boxPlot.plot([1.0+i, 1.0+i], [q1, q3], pen='k')
            # Whiskers (linhas verticais dos limites)
            self.boxPlot.plot([1.0+i, 1.0+i], [q3, upper_whisker], pen='k')
            self.boxPlot.plot([1.0+i, 1.0+i], [q1, lower_whisker], pen='k')
            # Topo e base dos whiskers
            self.boxPlot.plot([0.85+i, 1.15+i], [upper_whisker, upper_whisker], pen='b')
            self.boxPlot.plot([0.85+i, 1.15+i], [lower_whisker, lower_whisker], pen='b')

            # Outliers (se existirem)
            if len(outliers) > 0:
                self.boxPlot.plot(
                    np.ones(len(outliers))*(1.0+i),
                    outliers,
                    pen=None,
                    symbol='o',
                    symbolBrush='r',
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
        Limpa todos os gráficos e os dados armazenados.
        """
        self.spectraPlotWidget.clear()
        self.spectraPlotWidget.addItem(self.roi_region)
        self.temporalPlotWidget.clear()
        self.temporalPlotWidget.addItem(self.temporal_roi_region)
        self.results_df = {'Timestamp': [], 'Intensidade': [], 'ComprimentoRessonante': []}
        self.boxPlot.clear()
        self.boxLegend.clear()
        self._add_legend = True
        logger.info("Gráficos limpos.")

    def save_data(self):
        """
        Abre um diálogo para selecionar um arquivo .h5. Se o arquivo já existir,
        anexa os novos dados; caso contrário, cria um novo arquivo.
        Os dados são filtrados pela ROI temporal antes de serem salvos.
        
        """
        # --- Passo 1: Validação inicial ---
        if len(self.results_df['Timestamp']) == 0:
            logger.warning("Tentativa de salvar sem dados processados.")
            QMessageBox.warning(self, "Atenção", "Não há dados processados para salvar.")
            return

        logger.info("Iniciando processo para salvar dados.")

        # --- Passo 2: Abre diálogo para inserir o nome da amostra ---
        sample_name, ok = QInputDialog.getText(
            self,
            "Nome da Amostra",
            "Insira o nome da amostra para salvar os dados:"
        )

        if not ok:
            return # Usuário cancelou a entrada do nome da amostra

        # --- Passo 3: Obtém o caminho do arquivo do usuário ---
        file_path, _ = QFileDialog.getSaveFileName(
            self,   
            "Salvar ou Anexar Resultados",
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
            resonant_wavelengths = np.asarray(self.results_df['ComprimentoRessonante'], dtype=np.float64)
            
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

            # Calcula e armazena as estatísticas do box plot na escala configurada
            resonant_for_box = np.array(resonant_filtered, dtype=float)
            match self.config_data.get('x_unit'):
                case 'nm':
                    resonant_for_box *= 1e9
                case 'um':
                    resonant_for_box *= 1e6
            self.samples[sample_name] = self.box_plot_statistics(resonant_for_box)
            self.samples = dict(reversed(self.samples.items())) # Mantém a ordem de inserção (última amostra salva aparece primeiro)
            self._add_legend = True
            self.clear_plot()
            self.toggle_thread() # Reinicia a aquisição para atualizar os gráficos

        except Exception as e:
            logger.error(f"Falha ao processar ou salvar os dados: {e}")
            QMessageBox.critical(self, "Erro", f"Ocorreu um erro ao salvar o arquivo:\n{e}")

    def load_file(self, path: str):
        """
        Carrega dados de amostras de um arquivo HDF5 para análise.
        O arquivo deve conter no grupo da interface os datasets
        'ComprimentoRessonante' e 'Amostra'.

        Args:
            path (str): Caminho do arquivo HDF5 contendo os dados das amostras.
            
        """
        try:
            inter = self.config_data.get('inter')
            with h5py.File(path, "r") as f:
                if inter not in f:
                    raise ValueError(f"Grupo '{inter}' não encontrado no arquivo.")

                g = f[inter]
                if "ComprimentoRessonante" not in g or "Amostra" not in g:
                    raise ValueError("Datasets obrigatórios ausentes: 'ComprimentoRessonante' e/ou 'Amostra'.")

                wavelengths = np.asarray(g["ComprimentoRessonante"][:], dtype=float)
                sample_names = [
                    s.decode() if isinstance(s, (bytes, np.bytes_)) else str(s)
                    for s in g["Amostra"][:]
                ]

            grouped_samples = {}
            for idx, sample_name in enumerate(sample_names):
                grouped_samples.setdefault(sample_name, []).append(wavelengths[idx])

            last_wavelengths = []
            for sample_name, sample_wavelengths in grouped_samples.items():
                sample_wavelengths = np.asarray(sample_wavelengths, dtype=float)

                match self.config_data.get('x_unit'):
                    case 'nm':
                        sample_wavelengths *= 1e9
                    case 'um':
                        sample_wavelengths *= 1e6

                self.samples[sample_name] = self.box_plot_statistics(sample_wavelengths)
                last_wavelengths = sample_wavelengths

            if len(last_wavelengths) == 0:
                raise ValueError("Nenhum dado de amostra encontrado no arquivo.")
            
            self._add_legend = True
            self.boxLegend.clear()
            self.update_box_plot(last_wavelengths, loading=True) # Atualiza os gráficos com os box plots carregados
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
        self.sample_name, ok = QInputDialog.getText(
            self,
            "Nome da Amostra",
            "Insira o nome da amostra para salvar os dados:"
        )

        if not ok:
            return False # Usuário cancelou a entrada do nome da amostra

        # Obtém o caminho do arquivo do usuário ---
        file_path, _ = QFileDialog.getSaveFileName(
            self,   
            "Salvar ou Anexar Resultados",
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
        dialog.setIntValue(5*self.sample_rate//1000)
        dialog.setIntMinimum(5*self.sample_rate//1000)
        dialog.setIntMaximum(24*3600)
        dialog.setIntStep(1)
        dialog.setOkButtonText("Iniciar")

        if dialog.exec() == QDialog.Accepted:
            self.sample_duration = dialog.intValue()
        else:
            return False # Usuário cancelou a entrada da duração da amostra
        
        # Atualiza o caminho de salvamento para o modo contínuo
        self.config_data['path'] = file_path
        logger.debug(f"Caminho de salvamento definido para o modo contínuo: {file_path}")
        
        self.clear_plot()
        # Interrompe a aquisição após a duração especificada
        if self.continuous_timer is not None:
            if self.continuous_timer.isActive():
                self.continuous_timer.stop()
            self.continuous_timer.deleteLater()

        self.pending_hdf5 = {'Timestamp': [], 'Intensidade': [], 'ComprimentoRessonante': []}
        self.continuous_timer = QTimer(self)
        self.continuous_timer.setSingleShot(True)
        self.continuous_timer.timeout.connect(self.continuous_timer_shot)
        self.continuous_timer.start(self.sample_duration * 1000)
        return True
        
    def closeEvent(self, event):
        """
        Sobrescreve o evento de fechar a janela.

        Em vez de fechar a aplicação, esta função emite um sinal 'closing'
        para que a janela principal possa reaparecer.
        
        """
        self._cleanup_thread()
        super().closeEvent(event)