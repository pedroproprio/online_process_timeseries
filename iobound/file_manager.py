from PySide6.QtWidgets import QFileDialog, QMessageBox

import numpy as np
import h5py

def append_samples(
    range_cfg: tuple,
    res: float,
    file_path: str,
    inter: str,
    intensities: np.ndarray,
    timestamps: np.ndarray,
    values,
    sample_name: str,
    dataset_name: str = "Vale",
    extra_datasets: dict[str, list] | None = None):
    """
    Acrescenta registros no arquivo HDF5 usando o formato:
    interface -> parâmetros -> amostra -> datasets (Intensidades, Timestamp, Vale/Picos)
    Args:
    - range_cfg: tupla (nm_min, nm_max) representando o intervalo de comprimento de onda.
    - res: resolução espectral em pm.
    - file_path: caminho do arquivo HDF5.
    - inter: nome da interface
    - intensities: array 1D de intensidades interpoladas.
    - timestamps: array 1D de timestamps correspondentes a cada registro.
    - values: array 1D de vales/picos correspondentes a cada registro.
    - sample_name: nome da amostra
    - dataset_name: nome do dataset de valores ('Vale' ou 'Picos').
    - extra_datasets: datasets extras para salvar (ex.: {'NOME': [[...], [...]]}).

    """
    param = f"{int(range_cfg[0]*1e9)}-{int(range_cfg[1]*1e9)},{res*1e12:.1f}" # nm, nm, pm
    spec_len = intensities.shape[1]
    values_list = list(values)

    def _ensure_peak_dataset(group, name: str, size: int):
        if name in group:
            return group[name]
        return group.create_dataset(
            name,
            shape=(size,),
            maxshape=(None,),
            dtype=h5py.vlen_dtype(np.float64),
            chunks=True
        )

    def _store_peak_values(dataset, start_index: int, peak_values):
        for offset, peak_value in enumerate(peak_values):
            dataset[start_index + offset] = np.asarray(peak_value, dtype=np.float64)

    def _store_extra_datasets(group, start_index: int, n_rows: int, extras: dict[str, list] | None):
        if not extras:
            return

        for extra_name, extra_values in extras.items():
            values_local = list(extra_values) if extra_values is not None else []
            if len(values_local) == 0:
                values_local = [[] for _ in range(n_rows)]
            if len(values_local) != n_rows:
                raise ValueError(
                    f"Dataset extra '{extra_name}' incompatível com timestamps. "
                    f"Esperado {n_rows}, recebido {len(values_local)}."
                )

            ds = _ensure_peak_dataset(group, extra_name, start_index + n_rows)
            ds.resize((start_index + n_rows,))
            _store_peak_values(ds, start_index, values_local)

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
            if dataset_name == "Picos":
                peaks_ds = s.create_dataset(
                    "Picos",
                    shape=(len(values_list),),
                    maxshape=(None,),
                    dtype=h5py.vlen_dtype(np.float64),
                    chunks=True
                )
                _store_peak_values(peaks_ds, 0, values_list)
            else:
                s.create_dataset(
                    "Vale",
                    data=np.asarray(values_list, dtype=np.float64),
                    maxshape=(None,),
                    dtype="float64",
                    chunks=True
                )

            _store_extra_datasets(s, 0, len(timestamps), extra_datasets)
            return

        intensities_ds = s["Intensidades"]
        timestamps_ds = s["Timestamp"]

        if intensities_ds.shape[1] != spec_len:
            raise ValueError(
                f"Comprimento do espectro incompatível para append. "
                f"Esperado {intensities_ds.shape[1]}, recebido {spec_len}."
            )

        n_old = intensities_ds.shape[0]
        n_new = len(timestamps)

        intensities_ds.resize((n_old + n_new, spec_len))
        timestamps_ds.resize((n_old + n_new,))

        intensities_ds[n_old:n_old+n_new] = np.asarray(intensities, dtype=np.float32)
        timestamps_ds[n_old:n_old+n_new] = np.asarray(timestamps, dtype=np.float64)

        if dataset_name == "Picos":
            peaks_ds = _ensure_peak_dataset(s, "Picos", n_old + n_new)
            peaks_ds.resize((n_old + n_new,))
            _store_peak_values(peaks_ds, n_old, values_list)
        else:
            if "Vale" not in s:
                s.create_dataset(
                    "Vale",
                    shape=(n_old + n_new,),
                    maxshape=(None,),
                    dtype="float64",
                    chunks=True
                )
            valleys_ds = s["Vale"]
            valleys_ds.resize((n_old + n_new,))
            valleys_ds[n_old:n_old+n_new] = np.asarray(values_list, dtype=np.float64)

        _store_extra_datasets(s, n_old, n_new, extra_datasets)

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
                    if isinstance(sample_group, h5py.Group) and "Timestamp" in sample_group and ("Vale" in sample_group or "Picos" in sample_group):
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

def load_samples(file_path: str, inter: str) -> dict:
    """
    Carrega os dados de um arquivo HDF5 e organiza os datasets por amostra.
    Returns:
        dict: {sample_name: {"dataset": "Vale"|"Picos", "values": [...]}}

    """
    with h5py.File(file_path, "r") as f:
        g = f[inter]
        grouped_samples = {}

        def _to_peak_list(entry) -> list[float]:
            values = np.asarray(entry, dtype=float)
            if values.ndim == 0:
                return [float(values)]
            return values.ravel().tolist()

        # Formato: interface -> parâmetros -> amostra -> datasets
        for param_name, param_group in g.items():
            if not isinstance(param_group, h5py.Group):
                continue
            for sample_name, sample_group in param_group.items():
                if not isinstance(sample_group, h5py.Group):
                    continue
                if "Timestamp" not in sample_group:
                    continue

                dataset_name = "Picos" if "Picos" in sample_group else "Vale" if "Vale" in sample_group else None
                if dataset_name is None:
                    continue

                if dataset_name == "Picos":
                    peaks_by_timestamp = [_to_peak_list(entry) for entry in sample_group[dataset_name][:]]
                    if len(peaks_by_timestamp) == 0:
                        continue
                    grouped_samples.setdefault(sample_name, {"dataset": "Picos", "values": []})["values"].extend(peaks_by_timestamp)
                else:
                    valleys = np.asarray(sample_group[dataset_name][:], dtype=float).ravel().tolist()
                    if len(valleys) == 0:
                        continue
                    grouped_samples.setdefault(sample_name, {"dataset": "Vale", "values": []})["values"].extend(valleys)
    return grouped_samples