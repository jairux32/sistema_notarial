#!/bin/bash
# Script de inicio del servicio de escaneo para Linux

echo "=========================================="
echo "🖨️  SERVICIO DE ESCANEO MULTIPLATAFORMA"
echo "=========================================="
echo ""

# Verificar si SANE está instalado
if ! command -v scanimage &> /dev/null; then
    echo "⚠️  SANE no está instalado"
    echo "Instalando SANE..."
    sudo apt-get update
    sudo apt-get install -y sane sane-utils libsane-dev
fi

# Activar entorno virtual si existe
if [ -d "venv" ]; then
    echo "📦 Activando entorno virtual..."
    source venv/bin/activate
fi

# Instalar dependencias si es necesario
echo "📦 Verificando dependencias..."
pip install -q flask flask-cors pillow requests

# Iniciar servicio
echo ""
echo "🚀 Iniciando servicio de escaneo..."
echo "📡 El servicio estará disponible en http://localhost:5001"
echo ""
echo "Para detener el servicio, presiona Ctrl+C"
echo ""

python3 scanner_service.py
