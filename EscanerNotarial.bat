@echo off
chcp 65001 >nul
title Escaner Notarial

:: Iniciar servidor en segundo plano
start /min "Servidor Notarial" cmd /c "python app.py"

:: Esperar a que arranque
timeout /t 4 /nobreak >nul

:: Iniciar app de escritorio
cd desktop_app_v2
python main.py
cd ..
