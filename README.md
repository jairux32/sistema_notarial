# Sistema de Procesamiento Notarial

Sistema automatizado para procesamiento de documentos notariales con OCR, validación de secuenciales y división de PDFs.

## Características

- ✅ **Extracción híbrida de texto** - Texto nativo + OCR (98.5% precisión)
- ✅ **División inteligente de PDFs** - Por rangos de páginas entre códigos
- ✅ **Detección de códigos** - Códigos alfanuméricos notariales
- ✅ **Corrección manual** - Interfaz para agregar códigos faltantes
- ✅ **Validación de secuenciales** - Detecta saltos y códigos faltantes
- ✅ **Generación de reportes** - PDFs con detalles y hashes de integridad
- ✅ **Auditoría** - Registro de procesamiento y accesos

## Requisitos

- Python 3.8+
- Tesseract OCR
- PyMuPDF (fitz)
## Arquitectura Híbrida (Escáner USB + Backend Docker)
El sistema utiliza una **App de Escritorio (Python/Flet)** para escanear documentos vía USB y subirlos al servidor web.

## Instalación y Uso

### 1. Iniciar Servidor (Docker)
El backend procesa los archivos y gestiona la base de datos.
```bash
docker-compose up -d
```
Acceder a: http://localhost:5000

### 2. Iniciar Escáner (App Escritorio)
Para escanear documentos (requiere escáner Kodak conectado por USB):
```bash
./run_desktop.sh
```
Esto abrirá la ventana del escáner en `http://localhost:8550`.

## Características Clave
- **Validación Local:** La App de escritorio verifica si el código de barras es legible ANTES de subirlo, ahorrando tiempo.
- **Searchable PDF:** Los archivos subidos ya van con capa de texto (OCR) generada localmente.
- **Conexión Directa:** Usa drivers USB KODAK nativos de Linux.

## Credenciales Mensajería
- **Usuario:** admin
- **Contraseña (Restaurada):** admin123

## Estructura del Proyecto

```
sistema_notarial/
├── app.py                 # Aplicación Flask principal
├── utils/
│   ├── ocr_processor.py   # Extracción de texto híbrida
│   ├── pdf_splitter.py    # División de PDFs
│   ├── validator.py       # Validación de secuenciales
│   └── auditor.py         # Sistema de auditoría
├── templates/
│   ├── login.html
│   └── dashboard.html
├── static/
│   └── style.css
├── uploads/               # PDFs subidos (no en Git)
├── processed/             # PDFs procesados (no en Git)
└── reportes/              # Reportes generados (no en Git)
```

## Rendimiento

- **Tiempo de procesamiento:** ~22 segundos para 388 páginas
- **Precisión de detección:** 98.5%
- **Extracción híbrida:** 72% texto nativo, 28% OCR

## Licencia

Uso interno - Notaría Pablo Fernando Punín Castillo
