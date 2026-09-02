#!/bin/bash

# Script de inicio para el contenedor Docker

echo "=========================================="
echo "🚀 INICIANDO SISTEMA NOTARIAL (DOCKER)"
echo "=========================================="

# 0. Configurar IP del escáner si existe la variable
if [ -n "$SCANNER_IP_ADDRESS" ]; then
    echo "🌐 Configurando escáner de red en: $SCANNER_IP_ADDRESS"
    mkdir -p /etc/sane.d/
    echo "net $SCANNER_IP_ADDRESS" > /etc/sane.d/kds_s2000w.conf
fi

# 1. Iniciar aplicación principal en primer plano
echo ""
echo "🌐 Iniciando Aplicación Principal (Puerto 5000)..."
exec python app.py