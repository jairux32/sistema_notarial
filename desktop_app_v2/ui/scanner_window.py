"""Scanner window with gallery, metadata, upload, and manual PDF upload"""
import os
import uuid
import tempfile
import fitz
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QLineEdit, QScrollArea,
    QFrame, QGridLayout, QProgressBar, QSizePolicy,
    QSpinBox, QMessageBox, QFileDialog, QTabWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QImage


class ScanWorker(QThread):
    finished = pyqtSignal(list, str)

    def __init__(self, scanner_service, device_id, mode='single'):
        super().__init__()
        self.scanner = scanner_service
        self.device_id = device_id
        self.mode = mode

    def run(self):
        if self.mode == 'batch':
            images, error = self.scanner.scan_batch(self.device_id)
        else:
            images, error = self.scanner.scan_single(self.device_id)
        self.finished.emit(images, error or '')


class UploadWorker(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, api_client, pdf_path, username, ano, mes, tipo, numero):
        super().__init__()
        self.api = api_client
        self.pdf_path = pdf_path
        self.username = username
        self.ano = ano
        self.mes = mes
        self.tipo = tipo
        self.numero = numero

    def run(self):
        success, result, error = self.api.upload_scan(
            self.pdf_path, self.username,
            self.ano, self.mes, self.tipo, self.numero
        )
        msg = result.get('message', result.get('error', error)) if isinstance(result, dict) else error
        self.finished.emit(success, msg or 'Completado')


class ThumbnailWidget(QFrame):
    delete_clicked = pyqtSignal(str)

    def __init__(self, image_path, page_num, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setObjectName("card")
        self.setFixedSize(130, 160)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            thumb = pixmap.scaled(110, 110, Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
        else:
            thumb = QPixmap(110, 110)
            thumb.fill(Qt.GlobalColor.darkGray)

        img_label = QLabel()
        img_label.setPixmap(thumb)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(img_label)

        page_label = QLabel(f"Pag. {page_num}")
        page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        page_label.setStyleSheet("font-size: 11px; color: #aaa;")
        layout.addWidget(page_label)

        delete_btn = QPushButton("X")
        delete_btn.setObjectName("danger")
        delete_btn.setFixedSize(24, 24)
        delete_btn.setStyleSheet("font-size: 10px; padding: 2px;")
        delete_btn.clicked.connect(lambda: self.delete_clicked.emit(image_path))

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)


class ScannerWindow(QWidget):
    back_to_login = pyqtSignal()

    def __init__(self, api_client, scanner_service, user_data):
        super().__init__()
        self.api = api_client
        self.scanner = scanner_service
        self.user_data = user_data
        self.images = []
        self.pdf_path = None
        self.temp_dir = tempfile.mkdtemp(prefix='escaner_')
        self._build_ui()
        self._load_devices()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(280)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 20, 16, 16)
        sidebar_layout.setSpacing(8)

        user_label = QLabel(f"Usuario: {self.user_data.get('username', 'N/A')}")
        user_label.setStyleSheet("color: #00d4ff; font-weight: bold;")
        sidebar_layout.addWidget(user_label)

        sidebar_layout.addSpacing(5)

        # Dispositivo
        dev_label = QLabel("Dispositivo:")
        sidebar_layout.addWidget(dev_label)

        self.device_combo = QComboBox()
        self.device_combo.setMinimumHeight(32)
        sidebar_layout.addWidget(self.device_combo)

        refresh_btn = QPushButton("Refrescar Escaneres")
        refresh_btn.clicked.connect(self._load_devices)
        sidebar_layout.addWidget(refresh_btn)

        sidebar_layout.addSpacing(5)

        # Metadata
        ano_label = QLabel("Ano:")
        sidebar_layout.addWidget(ano_label)

        self.ano_spin = QSpinBox()
        self.ano_spin.setRange(2014, 2030)
        self.ano_spin.setValue(2025)
        self.ano_spin.setMinimumHeight(32)
        sidebar_layout.addWidget(self.ano_spin)

        mes_label = QLabel("Mes:")
        sidebar_layout.addWidget(mes_label)

        self.mes_combo = QComboBox()
        self.mes_combo.addItems([
            'ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO',
            'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE'
        ])
        self.mes_combo.setMinimumHeight(32)
        sidebar_layout.addWidget(self.mes_combo)

        tipo_label = QLabel("Tipo de Libro:")
        sidebar_layout.addWidget(tipo_label)

        self.tipo_combo = QComboBox()
        self.tipo_combo.addItems(['PROTOCOLO', 'DILIGENCIA', 'CERTIFICACIONES', 'ARRIENDOS', 'OTROS'])
        self.tipo_combo.setMinimumHeight(32)
        sidebar_layout.addWidget(self.tipo_combo)

        num_label = QLabel("Numero de Libro:")
        sidebar_layout.addWidget(num_label)

        self.numero_spin = QSpinBox()
        self.numero_spin.setRange(1, 999)
        self.numero_spin.setValue(1)
        self.numero_spin.setMinimumHeight(32)
        sidebar_layout.addWidget(self.numero_spin)

        sidebar_layout.addSpacing(5)

        # Botones de accion
        self.scan_btn = QPushButton("Escanear Hojas")
        self.scan_btn.setObjectName("success")
        self.scan_btn.setMinimumHeight(38)
        self.scan_btn.clicked.connect(self._on_scan)
        sidebar_layout.addWidget(self.scan_btn)

        or_label = QLabel("  -  O  -")
        or_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        or_label.setStyleSheet("color: #888; font-size: 11px;")
        sidebar_layout.addWidget(or_label)

        self.upload_pdf_btn = QPushButton("Subir PDF Existente")
        self.upload_pdf_btn.setObjectName("primary")
        self.upload_pdf_btn.setMinimumHeight(38)
        self.upload_pdf_btn.clicked.connect(self._on_upload_pdf)
        sidebar_layout.addWidget(self.upload_pdf_btn)

        self.process_btn = QPushButton("Procesar y Subir")
        self.process_btn.setObjectName("primary")
        self.process_btn.setMinimumHeight(38)
        self.process_btn.setEnabled(False)
        self.process_btn.clicked.connect(self._on_process)
        sidebar_layout.addWidget(self.process_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)
        sidebar_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Listo")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")
        sidebar_layout.addWidget(self.status_label)

        sidebar_layout.addStretch()

        logout_btn = QPushButton("Cerrar Sesion")
        logout_btn.setObjectName("danger")
        logout_btn.clicked.connect(self._on_logout)
        sidebar_layout.addWidget(logout_btn)

        main_layout.addWidget(sidebar)

        # Panel derecho
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(20, 20, 20, 20)

        self.header_label = QLabel("Documentos (0)")
        self.header_label.setObjectName("title")
        self.header_label.setStyleSheet("font-size: 16px;")
        right_layout.addWidget(self.header_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.gallery_widget = QWidget()
        self.gallery_layout = QGridLayout(self.gallery_widget)
        self.gallery_layout.setSpacing(10)
        self.gallery_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll.setWidget(self.gallery_widget)
        right_layout.addWidget(scroll)

        main_layout.addWidget(right_panel, 1)

    def _load_devices(self):
        self.device_combo.clear()
        self.status_label.setText("Buscando dispositivos...")
        devices = self.scanner.detect_devices()
        self.device_combo.clear()
        if devices:
            for d in devices:
                self.device_combo.addItem(d['name'], d['id'])
            virtual_count = sum(1 for d in devices if 'simulated' in d['id'])
            real_count = len(devices) - virtual_count
            if real_count > 0:
                self.status_label.setText(f"{real_count} escaner(es) encontrado(s)")
            else:
                self.status_label.setText("No se encontro escaner. Use escaner virtual o suba PDF.")
        else:
            self.device_combo.addItem("Escaner Virtual (Simulacion)", "simulated_scanner")
            self.status_label.setText("Use escaner virtual o suba PDF manualmente")

    def _on_scan(self):
        device_id = self.device_combo.currentData()
        if not device_id:
            self.status_label.setText("Seleccione un dispositivo")
            return

        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("Escaneando...")
        self.progress_bar.setVisible(True)
        self.status_label.setText("Escaneando paginas...")

        self.scan_worker = ScanWorker(self.scanner, device_id, mode='single')
        self.scan_worker.finished.connect(self._on_scan_result)
        self.scan_worker.start()

    def _on_scan_result(self, images, error):
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("Escanear Hojas")
        self.progress_bar.setVisible(False)

        if error:
            self.status_label.setText(f"Error: {error}")
            return

        self.images.extend(images)
        self.pdf_path = None
        self._refresh_gallery()
        self.process_btn.setEnabled(len(self.images) > 0)
        self.status_label.setText(f"{len(self.images)} pagina(s) escaneada(s)")

    def _on_upload_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar PDF", "",
            "Archivos PDF (*.pdf);;Todos los archivos (*)"
        )
        if not file_path:
            return

        try:
            pdf_doc = fitz.open(file_path)
            num_pages = len(pdf_doc)
            pdf_doc.close()

            self.images = []
            self.pdf_path = file_path
            self.process_btn.setEnabled(True)

            filename = os.path.basename(file_path)
            self.header_label.setText(f"PDF: {filename} ({num_pages} paginas)")
            self.status_label.setText(f"PDF cargado: {filename}")

            self.gallery_layout.removeWidget(self.gallery_widget)
            self.gallery_widget.deleteLater()
            self.gallery_widget = QWidget()
            self.gallery_layout = QGridLayout(self.gallery_widget)
            self.gallery_layout.setSpacing(10)
            self.gallery_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

            info_label = QLabel(
                f"PDF seleccionado:\n{filename}\n\n"
                f"Total de paginas: {num_pages}\n\n"
                f"Configure ano, mes, tipo y numero,\n"
                f"luego haga clic en 'Procesar y Subir'"
            )
            info_label.setStyleSheet("font-size: 13px; color: #ccc; padding: 20px;")
            info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.gallery_layout.addWidget(info_label, 0, 0)

            scroll = self.gallery_widget.parent().parent()
            if hasattr(scroll, 'setWidget'):
                scroll.setWidget(self.gallery_widget)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo leer el PDF:\n{str(e)}")

    def _refresh_gallery(self):
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if self.pdf_path:
            return

        cols = max(1, (self.gallery_widget.width() - 20) // 140)
        for i, img_path in enumerate(self.images):
            thumb = ThumbnailWidget(img_path, i + 1)
            thumb.delete_clicked.connect(self._delete_image)
            row, col = divmod(i, cols)
            self.gallery_layout.addWidget(thumb, row, col)

        self.header_label.setText(f"Paginas Escaneadas ({len(self.images)})")

    def _delete_image(self, image_path):
        if image_path in self.images:
            self.images.remove(image_path)
            if os.path.exists(image_path):
                os.remove(image_path)
            self._refresh_gallery()
            self.process_btn.setEnabled(len(self.images) > 0 or self.pdf_path is not None)
            self.status_label.setText(f"{len(self.images)} pagina(s)")

    def _on_process(self):
        tipo_map = {
            'PROTOCOLO': 'P', 'DILIGENCIA': 'D',
            'CERTIFICACIONES': 'C', 'ARRIENDOS': 'A', 'OTROS': 'O'
        }
        tipo_display = self.tipo_combo.currentText()
        tipo_code = tipo_map.get(tipo_display, 'P')

        self.process_btn.setEnabled(False)
        self.progress_bar.setVisible(True)

        # Si hay PDF subido directamente, subirlo
        if self.pdf_path:
            self.process_btn.setText("Subiendo PDF...")
            self.status_label.setText("Subiendo PDF al servidor...")
            self.upload_worker = UploadWorker(
                self.api, self.pdf_path,
                self.user_data.get('username', 'admin'),
                str(self.ano_spin.value()),
                self.mes_combo.currentText(),
                tipo_code,
                self.numero_spin.value()
            )
            self.upload_worker.finished.connect(self._on_process_result)
            self.upload_worker.start()
            return

        # Si hay imagenes escaneadas, generar PDF primero
        if not self.images:
            self.process_btn.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.status_label.setText("No hay documentos para procesar")
            return

        self.process_btn.setText("Generando PDF...")
        self.status_label.setText("Generando PDF con OCR...")

        from services.pdf_generator import generate_searchable_pdf

        pdf_path = os.path.join(self.temp_dir, f'scan_{uuid.uuid4().hex[:8]}.pdf')
        success, error = generate_searchable_pdf(self.images, pdf_path)

        if not success:
            self.process_btn.setEnabled(True)
            self.process_btn.setText("Procesar y Subir")
            self.progress_bar.setVisible(False)
            self.status_label.setText(f"Error generando PDF: {error}")
            return

        self.process_btn.setText("Subiendo al servidor...")
        self.status_label.setText("Subiendo al servidor...")

        self.upload_worker = UploadWorker(
            self.api, pdf_path,
            self.user_data.get('username', 'admin'),
            str(self.ano_spin.value()),
            self.mes_combo.currentText(),
            tipo_code,
            self.numero_spin.value()
        )
        self.upload_worker.finished.connect(self._on_process_result)
        self.upload_worker.start()

    def _on_process_result(self, success, message):
        self.process_btn.setEnabled(True)
        self.process_btn.setText("Procesar y Subir")
        self.progress_bar.setVisible(False)

        if success:
            self.status_label.setText(f"Procesado: {message}")
            self.images.clear()
            self.pdf_path = None
            self._refresh_gallery()
            self.process_btn.setEnabled(False)
            self.header_label.setText("Documentos (0)")
        else:
            self.status_label.setText(f"Error: {message}")
            if 'offline' in message.lower() or 'no disponible' in message.lower():
                QMessageBox.information(
                    self, "Modo Offline",
                    "El servidor no esta disponible. El PDF se guardo en la cola "
                    "de sincronizacion. Se subira cuando el servidor este disponible."
                )

    def _on_logout(self):
        self.api.token = None
        self.api.user = None
        self.back_to_login.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_gallery()
