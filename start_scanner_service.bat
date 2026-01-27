@echo off
REM Script de inicio del servicio de escaneo para Windows

echo ==========================================
echo 🖨️  SERVICIO DE ESCANEO MULTIPLATAFORMA
echo ==========================================
echo.

REM Activar entorno virtual si existe
if exist venv\Scripts\activate.bat (
    echo 📦 Activando entorno virtual...
    call venv\Scripts\activate.bat
)

REM Instalar dependencias si es necesario
echo 📦 Verificando dependencias...
pip install -q flask flask-cors pillow requests

REM Iniciar servicio
echo.
echo 🚀 Iniciando servicio de escaneo...
echo 📡 El servicio estará disponible en http://localhost:5001
echo.
echo Para detener el servicio, presiona Ctrl+C
echo.

python scanner_service.py

pause
