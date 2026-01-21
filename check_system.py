#!/usr/bin/env python3
"""
Script de verificación del sistema notarial
"""

import sys
import os
import subprocess

def verificar_python():
    print("1. Verificando Python...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 7:
        print(f"   ✓ Python {version.major}.{version.minor}.{version.micro} OK")
        return True
    else:
        print(f"   ✗ Python {version.major}.{version.minor} - Se requiere 3.7+")
        return False

def verificar_tesseract():
    print("2. Verificando Tesseract OCR...")
    try:
        result = subprocess.run(['tesseract', '--version'], 
                              capture_output=True, text=True)
        if 'tesseract' in result.stdout.lower():
            print(f"   ✓ Tesseract instalado: {result.stdout.split()[1]}")
            return True
    except FileNotFoundError:
        print("   ✗ Tesseract no encontrado")
        return False

def verificar_dependencias():
    print("3. Verificando dependencias Python...")
    requeridas = ['flask', 'pytesseract', 'pillow', 'fitz', 'reportlab']
    
    for dep in requeridas:
        try:
            __import__(dep.replace('-', '_'))
            print(f"   ✓ {dep} OK")
        except ImportError:
            print(f"   ✗ {dep} NO instalado")
            return False
    
    return True

def verificar_directorios():
    print("4. Verificando directorios...")
    directorios = ['uploads', 'processed', 'templates', 'static', 'utils']
    
    for dir in directorios:
        if os.path.exists(dir):
            print(f"   ✓ {dir}/ OK")
        else:
            print(f"   ✗ {dir}/ NO existe")
            return False
    
    return True

def main():
    print("=" * 50)
    print("VERIFICACIÓN DEL SISTEMA NOTARIAL")
    print("Resolución 202-2021 - Consejo de la Judicatura")
    print("=" * 50)
    
    checks = [
        verificar_python(),
        verificar_tesseract(),
        verificar_dependencias(),
        verificar_directorios()
    ]
    
    print("\n" + "=" * 50)
    if all(checks):
        print("✅ SISTEMA LISTO PARA EJECUTAR")
        print("\nPara iniciar:")
        print("  source venv/bin/activate")
        print("  python app.py")
        print("\nAccede en: http://localhost:5000")
    else:
        print("❌ PROBLEMAS DETECTADOS")
        print("\nEjecuta: ./setup.sh para configurar automáticamente")
    
    print("=" * 50)

if __name__ == "__main__":
    main()