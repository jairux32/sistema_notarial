#!/bin/bash

# Script para iniciar el Sistema Notarial

echo "Iniciando Sistema Notarial..."
echo "Resolución 202-2021 - Consejo de la Judicatura"
echo ""

# Verificar si el entorno virtual existe
if [ ! -d "venv" ]; then
    echo "ERROR: No se encontró el entorno virtual."
    echo "Ejecuta primero: ./setup.sh"
    exit 1
fi

# Activar entorno virtual
source venv/bin/activate

# Verificar dependencias
if ! command -v tesseract &> /dev/null; then
    echo "ERROR: Tesseract no está instalado."
    echo "Ejecuta: sudo apt install tesseract-ocr tesseract-ocr-spa"
    exit 1
fi

# Verificar archivos necesarios
if [ ! -f "app.py" ]; then
    echo "ERROR: No se encontró app.py"
    exit 1
fi

# Crear directorios necesarios
mkdir -p uploads processed logs
mkdir -p processed/2014/{PROTOCOLO,DILIGENCIA,CERTIFICACIONES,OTROS,ARRIENDOS}
# ... repetir para otros años ...

# Iniciar aplicación
echo "Iniciando servidor Flask..."
echo "Accede en: http://localhost:5000"
echo "Usuario: admin"
echo "Contraseña: PabloPunin1970@"
echo ""
echo "Presiona Ctrl+C para detener el servidor"
echo ""

python app.py