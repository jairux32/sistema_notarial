"""Documents window for listing and downloading processed documents"""
import os
import subprocess
import platform
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QMessageBox, QFileDialog
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

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Archivo", "Ano", "Tamano", "Accion"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
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

        self.table.setRowCount(len(filtered))
        for row, doc in enumerate(filtered):
            self.table.setItem(row, 0, QTableWidgetItem(doc['filename']))
            self.table.setItem(row, 1, QTableWidgetItem(doc['year']))

            size_kb = doc['size'] / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
            self.table.setItem(row, 2, QTableWidgetItem(size_str))

            dl_btn = QPushButton("Descargar")
            dl_btn.setProperty('doc_path', doc['path'])
            dl_btn.setProperty('doc_name', doc['filename'])
            dl_btn.clicked.connect(self._on_download)
            self.table.setCellWidget(row, 3, dl_btn)

        self.count_label.setText(f"{len(filtered)} documento(s)")

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
