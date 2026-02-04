#!/bin/bash

# Script de inicio para el contenedor Docker
# Inicia tanto el servicio de escaneo como la aplicación principal

echo "=========================================="
echo "🚀 INICIANDO SISTEMA NOTARIAL (DOCKER)"
echo "=========================================="

# 0. Configurar IP del escáner si existe la variable
if [ -n "$SCANNER_IP_ADDRESS" ]; then
    echo "🌐 Configurando escáner de red en: $SCANNER_IP_ADDRESS"
    # Asegurar que el directorio existe
    mkdir -p /etc/sane.d/
    # Escribir configuración de red para driver Kodak (sin sudo, usuario tiene permisos)
    echo "net $SCANNER_IP_ADDRESS" > /etc/sane.d/kds_s2000w.conf
fi

# 1. Iniciar servicio de escaneo en segundo plano (dentro del contenedor)
echo ""
echo "🖨️  Iniciando Servicio de Escaneo Local (Puerto 5001)..."
python scanner_service.py &
SCANNER_PID=$!
sleep 2

# 2. Iniciar aplicación principal en primer plano
echo ""
echo "🌐 Iniciando Aplicación Principal (Puerto 5000)..."
# Usamos exec para que tome el PID 1 y reciba señales (como SIGTERM)
exec python app.py