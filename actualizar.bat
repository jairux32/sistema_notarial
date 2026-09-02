@echo off
chcp 65001 >nul
echo ==========================================
echo  ESCANER NOTARIAL - Actualizar Sistema
echo ==========================================
echo.

:: Verificar Git
git --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git no encontrado
    echo Descarga desde: https://git-scm.com/download/win
    pause
    exit /b 1
)

echo [1/3] Descargando ultima version...
git pull

if errorlevel 1 (
    echo.
    echo Error al actualizar. Verifica tu conexion a internet.
    pause
    exit /b 1
)

echo.
echo [2/3] Actualizando dependencias...
pip install -q Flask Flask-Login Flask-SQLAlchemy pytesseract Pillow PyMuPDF
pip install -q reportlab werkzeug flask-cors requests python-dotenv
pip install -q PyQt6

echo.
echo [3/3] Actualizacion completada!
echo.
echo ==========================================
echo  LISTO - Reinicia la aplicacion
echo ==========================================
echo.
pause
