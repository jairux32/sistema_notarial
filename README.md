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
- Flask
- pytesseract

## Instalación

```bash
# Clonar repositorio
git clone <url-del-repositorio>
cd sistema_notarial

# Ejecutar script de configuración
chmod +x setup.sh
./setup.sh

# O manualmente:
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Uso

```bash
# Iniciar servidor
./start.sh

# O manualmente:
source venv/bin/activate
python3 app.py
```

Acceder a: http://127.0.0.1:5000

## Credenciales por Defecto

- **Usuario:** admin
- **Contraseña:** PabloPunin1970@

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
