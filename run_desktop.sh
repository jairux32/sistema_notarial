#!/bin/bash
# Script para iniciar la App de Escritorio (Escáner)

echo "🚀 Iniciando Entorno Virtual..."
source desktop_app/venv/bin/activate

echo "📱 Abriendo Sistema de Escaneo..."
python desktop_app/main.py
