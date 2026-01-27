# Control de Escáner Multiplataforma

## Descripción

Sistema de escaneo directo que funciona en Windows, Linux y Mac. Permite escanear documentos desde el Kodak S2060w directamente desde la interfaz web.

---

## Arquitectura

```
Navegador Web → Flask (5000) → Scanner Service (5001) → Escáner
```

---

## Instalación

### Linux (Ubuntu/Debian)

```bash
# 1. Instalar SANE
sudo apt-get update
sudo apt-get install -y sane sane-utils libsane-dev

# 2. Verificar escáner
scanimage -L

# 3. Instalar dependencias Python
source venv/bin/activate
pip install flask flask-cors pillow requests

# 4. Iniciar servicio
./start_scanner_service.sh
```

### Windows

```batch
REM 1. Instalar dependencias Python
pip install flask flask-cors pillow requests

REM 2. Iniciar servicio
start_scanner_service.bat
```

**Nota:** En Windows, el sistema usa WIA (Windows Image Acquisition) que viene incluido.

### Mac

```bash
# 1. Instalar SANE (opcional, recomendado)
brew install sane-backends

# 2. Instalar dependencias Python
pip install flask flask-cors pillow requests

# 3. Iniciar servicio
./start_scanner_service.sh
```

---

## Uso

### 1. Iniciar Servicio de Escaneo

**Linux/Mac:**
```bash
./start_scanner_service.sh
```

**Windows:**
```
start_scanner_service.bat
```

El servicio quedará corriendo en `http://localhost:5001`

### 2. Usar desde la Interfaz Web

1. Accede al sistema notarial: `http://localhost:5000`
2. Ve al **Módulo de Escaneo**
3. Verifica que el servicio esté activo (✅ verde)
4. Configura resolución y modo de color
5. Clic en **"Escanear Documento"**
6. El archivo se guardará automáticamente en `scanned/`
7. Procesa normalmente con "Buscar Nuevos Documentos"

---

## Configuración

### Resolución

- **150 DPI:** Rápido, para documentos de texto simple
- **300 DPI:** Recomendado, balance entre calidad y velocidad
- **600 DPI:** Alta calidad, para documentos con detalles finos

### Modo de Color

- **Color:** Documentos a color (recomendado)
- **Escala de grises:** Documentos en blanco y negro
- **Lineart:** Solo texto, sin imágenes

---

## Solución de Problemas

### Linux: "scanimage: command not found"

```bash
sudo apt-get install sane sane-utils
```

### Linux: "No scanners were identified"

```bash
# Verificar permisos
sudo usermod -a -G scanner $USER

# Reiniciar sesión o ejecutar:
newgrp scanner

# Verificar escáner
sudo sane-find-scanner
scanimage -L
```

### Windows: "Error al escanear"

- Verifica que el escáner esté conectado y encendido
- Asegúrate de que los drivers del escáner estén instalados
- Prueba escanear desde otra aplicación (Paint, etc.)

### Servicio no disponible

- Verifica que `scanner_service.py` esté corriendo
- Revisa que el puerto 5001 no esté ocupado
- Mira los logs del servicio para errores

---

## Archivos Creados

| Archivo | Descripción |
|---------|-------------|
| `scanner_service.py` | Servicio Python multiplataforma |
| `start_scanner_service.sh` | Script de inicio Linux/Mac |
| `start_scanner_service.bat` | Script de inicio Windows |

---

## Endpoints HTTP

### GET /status
Verifica estado del servicio

**Respuesta:**
```json
{
  "status": "running",
  "os": "Linux",
  "version": "1.0.0"
}
```

### POST /scan
Escanea un documento

**Request:**
```json
{
  "resolution": 300,
  "mode": "Color",
  "output_dir": "scanned"
}
```

**Respuesta:**
```json
{
  "success": true,
  "archivo": "scanned/scan_20250123_173000.pdf",
  "mensaje": "Documento escaneado exitosamente"
}
```

---

## Notas Técnicas

### Formatos Soportados

- **Salida:** PDF (convertido automáticamente desde TIFF)
- **Temporal:** TIFF (eliminado después de conversión)

### Timeouts

- Escaneo: 60 segundos
- Verificación de servicio: 2 segundos

### Dependencias

```
flask==2.3.3
flask-cors==4.0.0
pillow==10.0.0
requests==2.31.0
```

---

## Mejoras Futuras

- [ ] Escaneo duplex (ambos lados)
- [ ] Escaneo de múltiples páginas (ADF)
- [ ] Vista previa antes de guardar
- [ ] Compresión de PDFs
- [ ] Configuración de brillo/contraste
- [ ] Detección automática de bordes

---

## Soporte

Para problemas o preguntas, revisa los logs del servicio o contacta al administrador del sistema.
