@echo off
echo ====================================
echo  Escaner Notarial - Build Windows
echo ====================================

echo.
echo [1/3] Instalando dependencias...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo [2/3] Generando ejecutable...
pyinstaller --name "EscanerNotarial" ^
    --windowed ^
    --onedir ^
    --icon=NONE ^
    --add-data "ui;ui" ^
    --add-data "services;services" ^
    --hidden-import=PyQt6 ^
    --hidden-import=PyQt6.QtWidgets ^
    --hidden-import=PyQt6.QtCore ^
    --hidden-import=PyQt6.QtGui ^
    main.py

echo.
echo [3/3] Build completado!
echo Ejecutable en: dist\EscanerNotarial\EscanerNotarial.exe
echo.
pause
