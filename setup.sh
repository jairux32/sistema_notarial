#!/bin/bash

# Script de configuración automática para Sistema Notarial en Ubuntu

echo "========================================="
echo "  CONFIGURACIÓN SISTEMA NOTARIAL 2024"
echo "  Resolución 202-2021 - Consejo Judicatura"
echo "========================================="

# 1. Verificar Ubuntu
echo "[1/8] Verificando sistema..."
if [[ $(lsb_release -i -s) != "Ubuntu" ]]; then
    echo "ERROR: Este script es para Ubuntu"
    exit 1
fi

# 2. Actualizar sistema
echo "[2/8] Actualizando sistema..."
sudo apt update
sudo apt upgrade -y

# 3. Instalar dependencias del sistema
echo "[3/8] Instalando dependencias del sistema..."
sudo apt install -y python3 python3-pip python3-venv git
sudo apt install -y tesseract-ocr tesseract-ocr-spa libtesseract-dev
sudo apt install -y libjpeg-dev zlib1g-dev libpng-dev

# 4. Crear entorno virtual
echo "[4/8] Creando entorno virtual..."
python3 -m venv venv
source venv/bin/activate

# 5. Instalar dependencias Python
echo "[5/8] Instalando dependencias Python..."
pip install --upgrade pip
pip install flask flask-login pytesseract pillow pymupdf reportlab werkzeug

# 6. Crear estructura de directorios
echo "[6/8] Creando estructura de directorios..."
mkdir -p templates static uploads processed logs
mkdir -p utils

# 7. Crear archivos de configuración
echo "[7/8] Creando archivos de configuración..."
cat > requirements.txt << 'EOF'
Flask==2.3.3
Flask-Login==0.6.2
pytesseract==0.3.10
Pillow==10.0.0
PyMuPDF==1.23.8
reportlab==4.0.4
werkzeug==2.3.7
EOF

# 8. Dar permisos
echo "[8/8] Configurando permisos..."
chmod +x setup.sh
chmod 755 -R .

echo "========================================="
echo "  CONFIGURACIÓN COMPLETADA!"
echo "========================================="
echo ""
echo "Para iniciar el sistema:"
echo "1. source venv/bin/activate"
echo "2. python app.py"
echo "3. Acceder a: http://localhost:5000"
echo ""
echo "Credenciales:"
echo "  Usuario: admin"
echo "  Contraseña: PabloPunin1970@"
echo "========================================="