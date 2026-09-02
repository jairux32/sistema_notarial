@echo off
chcp 65001 >nul
echo ==========================================
echo  Detectando Escaneres...
echo ==========================================
echo.

echo [1] Buscando dispositivos WIA...
powershell -Command "Get-WmiObject -Query 'SELECT * FROM Win32_PnPEntity' | Where-Object { $_.Service -eq 'WIA' -or $_.PNPClass -eq 'Image' -or $_.Name -match 'scanner|scan|image|kodak' } | ForEach-Object { Write-Output ('  - ' + $_.Name + ' [' + $_.DeviceID + ']') }"
echo.

echo [2] Verificando Kodak S2000W en red (192.168.1.28)...
powershell -Command "Test-NetConnection -ComputerName 192.168.1.28 -Port 9100 -WarningAction SilentlyContinue | ForEach-Object { if ($_.TcpTestSucceeded) { Write-Output '  [OK] Kodak S2000W detectado en red' } else { Write-Output '  [NO] No se encontro Kodak en 192.168.1.28' } }"
echo.

echo [3] Listando todos los dispositivos de imagen...
powershell -Command "Get-WmiObject -Query 'SELECT * FROM Win32_PnPEntity' | Where-Object { $_.Name -match 'scanner|scan|image|kodak|canon|epson|hp|brother' } | ForEach-Object { Write-Output ('  - ' + $_.Name) }"
echo.

echo ==========================================
echo Fin de la deteccion
echo ==========================================
pause
