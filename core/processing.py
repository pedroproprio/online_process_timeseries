# -*- coding: utf-8 -*-

"""
Módulo de backend para processamento de dados espectrais.

Este arquivo contém funções puras de cálculo, independentes da interface
gráfica, para analisar os espectros dos sensores.
"""

import logging
import numpy as np
from scipy.optimize import curve_fit
from scipy.signal import savgol_filter, windows

# Configura o logger para este módulo
logger = logging.getLogger(__name__)


def find_resonant_wavelength(wavelengths: np.ndarray,
                             power: np.ndarray,
                             roi_min: float,
                             roi_max: float) -> float | None:
    """
    Encontra o comprimento de onda ressonante (mínimo de potência) em uma ROI.

    Args:
        wavelengths (np.ndarray): Array com os comprimentos de onda.
        power (np.ndarray): Array com os valores de potência.
        roi_min (float): Limite inferior da Região de Interesse (ROI).
        roi_max (float): Limite superior da Região de Interesse (ROI).

    Returns:
        [float | None]: O valor do comprimento de onda ressonante encontrado,
                         ou None se nenhum dado estiver presente na ROI.
    """
    try:
        # 1. Cria uma máscara booleana para filtrar os dados dentro da ROI.
        # Esta é a forma mais eficiente de selecionar dados em numpy.
        mask = (wavelengths >= roi_min) & (wavelengths <= roi_max)

        # 2. Aplica a máscara para obter apenas os dados da região de interesse.
        roi_wavelengths = wavelengths[mask]
        roi_power = power[mask]

        # 3. Verifica se existe algum dado na ROI selecionada.
        if len(roi_wavelengths) == 0:
            logger.warning("Nenhum ponto de dados encontrado na ROI especificada.")
            return None

        # 4. Encontra o ÍNDICE do menor valor de potência na ROI.
        min_power_index = np.argmin(roi_power)

        # 5. Usa o índice para encontrar o COMPRIMENTO DE ONDA correspondente.
        resonant_wavelength = roi_wavelengths[min_power_index]

        pop, _ = curve_fit(lorentz, roi_wavelengths, roi_power, 
                           p0=[-10, resonant_wavelength, 100, max(power), 0],
                           bounds=([-np.inf, roi_min, 1, -np.inf, -1], [0, roi_max, np.inf, np.inf, 1]))
        resonant_wavelength = pop[1]

        return resonant_wavelength

    except Exception as e:
        logger.error(f"Ocorreu um erro ao buscar o comprimento de onda ressonante: {e}")
        return None

def lorentz(x: np.ndarray, a: float, x0: float, w: float, bias: float, incl: float) -> np.ndarray:
    """
    Calcula o valor de uma função Lorentziana em um determinado ponto.

    Esta função modela um pico Lorentziano, frequentemente usado para
    ajustar curvas em espectroscopia.

    Args:
        x (np.ndarray): Ponto(s) de entrada onde a função será calculada.
        a (float): Amplitude ou escala da função (altura do pico).
        x0 (float): Posição do centro do pico (média, Mu).
        w (float): Largura à meia altura (FWHM - Full Width at Half Maximum, Gama).
        bias (float): Deslocamento vertical (offset no eixo Y).
        incl (float): Inclinação linear (tendência linear no eixo Y).
    Returns:
        np.ndarray: O valor da função Lorentziana calculado em `x`.
    """
    return a * (1 + ((x - x0) / (w / 2)) ** 2) ** (-1) + bias + incl * (x - x0)

def _apodize_plot_data(y_values: np.ndarray, methods: dict, apodization: str | None = None) -> np.ndarray:
    if apodization is None:
        return y_values

    method = methods.get(apodization)
    if method is None:
        return y_values

    try:
        window = method(y_values.size, np.std(y_values))
        window /= np.mean(window)
        y_apodized = y_values * window
        return y_apodized
    except Exception as exc:
        logger.error(f"Erro ao aplicar apodizacao '{apodization}': {exc}")
        return y_values

def preprocess_plot_data(y_values: np.ndarray, methods: dict, savgol_window_size: int, savgol_polyorder: int, apodization: str | None = None) -> np.ndarray:
    """
    Faz o pré-processamento dos dados de potência para visualização, aplicando apodização e filtro de Savitzky-Golay.
    Args:
        y_values (np.ndarray): Array de valores de potência a serem processados.
        methods (dict): Dicionário mapeando nomes de métodos de apodização para suas funções correspondentes.
        savgol_window_size (int): Tamanho da janela para o filtro de Savitzky-Golay (deve ser ímpar).
        savgol_polyorder (int): Ordem do polinômio para o filtro de Savitzky-Golay.
        apodization (str | None): Nome do método de apodização a ser aplicado, ou None para não aplicar apodização.
    """
    y_values = _apodize_plot_data(y_values, methods, apodization)
    y_values = savgol_filter(y_values, savgol_window_size, savgol_polyorder)
    return y_values