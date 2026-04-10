from PySide6.QtWidgets import QFileDialog, QMessageBox

import numpy as np
import h5py

def append_hdf5_samples(
        range_cfg: tuple,
        res: float,
        file_path: str,
        inter: str,
        intensities: np.ndarray,
        timestamps: np.ndarray,
        valleys: np.ndarray,
        sample_name: str):
    """
    Acrescenta registros no arquivo HDF5 usando o formato:
    interface -> parâmetros -> amostra -> datasets (Intensidades, Timestamp, Vale)
    Args:
    - range_cfg: tupla (nm_min, nm_max) representando o intervalo de comprimento de onda.
    - res: resolução espectral em pm.
    - file_path: caminho do arquivo HDF5.
    - inter: nome da interface
    - intensities: array 1D de intensidades interpoladas.
    - timestamps: array 1D de timestamps correspondentes a cada registro.
    - valleys: array 1D de comprimentos de onda dos vales correspondentes a cada registro.
    - sample_name: nome da amostra

    """
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
                data=np.asarray(valleys, dtype=np.float64),
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
        wavelengths_ds[n_old:n_old+n_new] = np.asarray(valleys, dtype=np.float64)

def prompt_save_file(self) -> str:
    """
    Abre um diálogo para seleção do caminho do arquivo a ser salvo.
    Returns:
        str: O caminho do arquivo selecionado ou uma string vazia se a seleção for cancelada.

    """
    return QFileDialog.getSaveFileName(
            self,   
            "Salvar ou Anexar Experimento",
            "",
            "HDF5 Files (*.h5)",
            options=QFileDialog.DontConfirmOverwrite
        )[0]
    
def prompt_open_file(self) -> str | None:
    """
    Abre um diálogo para seleção de um arquivo HDF5.
    Returns:
        str: O caminho do arquivo selecionado ou None se a seleção for cancelada.

    """
    inter = self.config_data.get('inter')
    file_dialog = QFileDialog(self, "Selecione o arquivo de dados", filter="HDF5 Files (*.h5)")
    file_dialog.setFileMode(QFileDialog.ExistingFile)
    if file_dialog.exec():
        selected_files = file_dialog.selectedFiles()
        if selected_files:
            file_path = selected_files[0]
    else:
        return None # Usuário cancelou a seleção de arquivo

    # Verifica se o arquivo selecionado é válido
    try:
        with h5py.File(file_path, "r") as f:
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
            return file_path

    except Exception as e:
        QMessageBox.warning(self, "Arquivo inválido", f"Falha ao abrir arquivo HDF5: {e}")

def load_hdf5_samples(file_path: str, inter: str) -> dict:
    """
    Carrega os dados de um arquivo HDF5 e organiza os datasets por amostra.
    Returns:
        dict: Um dicionário onde as chaves são os nomes das amostras e os valores são listas de datasets.

    """
    with h5py.File(file_path, "r") as f:
        g = f[inter]
        grouped_samples = {}

        # Formato: interface -> parâmetros -> amostra -> datasets
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
    return grouped_samples