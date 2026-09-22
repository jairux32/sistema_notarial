"""Documents window for listing and downloading processed documents"""
import os
import zipfile
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QMessageBox, QFileDialog,
    QCheckBox, QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


class DocumentsLoader(QThread):
    finished = pyqtSignal(list, dict)

    def __init__(self, api_client, processed_folder):
        super().__init__()
        self.api = api_client
        self.processed_folder = processed_folder

    def run(self):
        documents = []
        file_map = {}
        if os.path.isdir(self.processed_folder):
            for year_dir in sorted(os.listdir(self.processed_folder), reverse=True):
                year_path = os.path.join(self.processed_folder, year_dir)
                if not os.path.isdir(year_path) or not year_dir.isdigit():
                    continue
                for root, dirs, files in os.walk(year_path):
                    for f in files:
                        if f.endswith('.pdf'):
                            full_path = os.path.join(root, f)
                            rel_path = os.path.relpath(full_path, self.processed_folder)
                            documents.append({
                                'filename': f,
                                'path': rel_path,
                                'year': year_dir,
                                'size': os.path.getsize(full_path)
                            })
                            file_map[f] = rel_path
        self.finished.emit(documents, file_map)


class DocumentsWindow(QWidget):
    back_to_scanner = pyqtSignal()

    def __init__(self, api_client, processed_folder):
        super().__init__()
        self.api = api_client
        self.processed_folder = processed_folder
        self.documents = []
        self.file_map = {}
        self.filtered = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header_layout = QHBoxLayout()

        title = QLabel("Documentos Procesados")
        title.setObjectName("title")
        title.setStyleSheet("font-size: 16px;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        back_btn = QPushButton("Volver al Escaner")
        back_btn.clicked.connect(lambda: self.back_to_scanner.emit())
        header_layout.addWidget(back_btn)

        layout.addLayout(header_layout)

        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)

        filter_layout.addWidget(QLabel("Ano:"))
        self.year_combo = QComboBox()
        self.year_combo.setMinimumWidth(100)
        self.year_combo.currentTextChanged.connect(self._filter_documents)
        filter_layout.addWidget(self.year_combo)

        filter_layout.addWidget(QLabel("Tipo:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(['Todos', 'PROTOCOLO', 'DILIGENCIA', 'CERTIFICACIONES', 'ARRIENDOS', 'OTROS'])
        self.type_combo.setMinimumWidth(150)
        self.type_combo.currentTextChanged.connect(self._filter_documents)
        filter_layout.addWidget(self.type_combo)

        filter_layout.addStretch()

        refresh_btn = QPushButton("Actualizar")
        refresh_btn.clicked.connect(self._load_documents)
        filter_layout.addWidget(refresh_btn)

        layout.addLayout(filter_layout)

        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)

        self.select_all_cb = QCheckBox("Seleccionar todos")
        self.select_all_cb.stateChanged.connect(self._toggle_all)
        action_layout.addWidget(self.select_all_cb)

        self.selected_label = QLabel("")
        self.selected_label.setStyleSheet("color: #888; font-size: 12px;")
        action_layout.addWidget(self.selected_label)

        action_layout.addStretch()

        self.download_selected_btn = QPushButton("Descargar Seleccionados (ZIP)")
        self.download_selected_btn.setEnabled(False)
        self.download_selected_btn.clicked.connect(self._download_selected)
        action_layout.addWidget(self.download_selected_btn)

        self.download_all_btn = QPushButton("Descargar Todos (ZIP)")
        self.download_all_btn.clicked.connect(self._download_all)
        action_layout.addWidget(self.download_all_btn)

        layout.addLayout(action_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["", "Archivo", "Ano", "Tamano", "Descargar"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.cellChanged.connect(self._on_cell_changed)
        layout.addWidget(self.table)

        self.count_label = QLabel("0 documentos")
        self.count_label.setStyleSheet("color: #888;")
        layout.addWidget(self.count_label)

    def _load_documents(self):
        loader = DocumentsLoader(self.api, self.processed_folder)
        loader.finished.connect(self._on_documents_loaded)
        loader.start()

    def _on_documents_loaded(self, documents, file_map):
        self.documents = documents
        self.file_map = file_map

        years = sorted(set(d['year'] for d in documents), reverse=True)
        self.year_combo.clear()
        self.year_combo.addItem('Todos')
        self.year_combo.addItems(years)

        self._filter_documents()

    def _filter_documents(self):
        year_filter = self.year_combo.currentText()
        type_filter = self.type_combo.currentText()

        filtered = self.documents

        if year_filter != 'Todos':
            filtered = [d for d in filtered if d['year'] == year_filter]

        if type_filter != 'Todos':
            tipo_map = {
                'PROTOCOLO': 'P', 'DILIGENCIA': 'D',
                'CERTIFICACIONES': 'C', 'ARRIENDOS': 'A', 'OTROS': 'O'
            }
            tipo_code = tipo_map.get(type_filter, '')
            if tipo_code:
                filtered = [d for d in filtered if tipo_code in d['filename']]

        self.filtered = filtered

        self.table.blockSignals(True)
        self.table.setRowCount(len(filtered))
        for row, doc in enumerate(filtered):
            cb_item = QTableWidgetItem()
            cb_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            cb_item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, cb_item)

            self.table.setItem(row, 1, QTableWidgetItem(doc['filename']))
            self.table.setItem(row, 2, QTableWidgetItem(doc['year']))

            size_kb = doc['size'] / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
            self.table.setItem(row, 3, QTableWidgetItem(size_str))

            dl_btn = QPushButton("Descargar")
            dl_btn.setProperty('doc_path', doc['path'])
            dl_btn.setProperty('doc_name', doc['filename'])
            dl_btn.clicked.connect(self._on_download)
            self.table.setCellWidget(row, 4, dl_btn)

        self.table.blockSignals(False)
        self.select_all_cb.setChecked(False)
        self._update_selection_count()
        self.count_label.setText(f"{len(filtered)} documento(s)")

    def _on_cell_changed(self, row, col):
        if col == 0:
            self._update_selection_count()

    def _update_selection_count(self):
        count = 0
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                count += 1

        if count > 0:
            self.selected_label.setText(f"{count} seleccionado(s)")
            self.download_selected_btn.setEnabled(True)
        else:
            self.selected_label.setText("")
            self.download_selected_btn.setEnabled(False)

    def _toggle_all(self, state):
        self.table.blockSignals(True)
        check_state = Qt.CheckState.Checked if state == Qt.CheckBoxState.Checked.value else Qt.CheckState.Unchecked
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(check_state)
        self.table.blockSignals(False)
        self._update_selection_count()

    def _get_selected_files(self):
        files = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                doc = self.filtered[row]
                files.append(doc)
        return files

    def _download_selected(self):
        files = self._get_selected_files()
        if not files:
            return
        self._download_as_zip(files, "documentos_seleccionados.zip")

    def _download_all(self):
        if not self.filtered:
            return
        self._download_as_zip(self.filtered, "documentos_todos.zip")

    def _download_as_zip(self, files, default_name):
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar ZIP", default_name, "ZIP files (*.zip)"
        )
        if not save_path:
            return

        try:
            with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for doc in files:
                    full_path = os.path.join(self.processed_folder, doc['path'])
                    if os.path.exists(full_path):
                        zf.write(full_path, doc['filename'])

            QMessageBox.information(
                self, "Descargado",
                f"ZIP guardado con {len(files)} archivo(s):\n{save_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo crear el ZIP:\n{str(e)}")

    def _on_download(self):
        btn = self.sender()
        doc_path = btn.property('doc_path')
        doc_name = btn.property('doc_name')
        full_path = os.path.join(self.processed_folder, doc_path)

        if not os.path.exists(full_path):
            QMessageBox.warning(self, "Error", f"Archivo no encontrado:\n{full_path}")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar PDF", doc_name, "PDF files (*.pdf)"
        )
        if save_path:
            import shutil
            shutil.copy2(full_path, save_path)
            QMessageBox.information(self, "Descargado", f"Archivo guardado en:\n{save_path}")
