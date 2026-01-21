#!/usr/bin/env python3
"""
Script de diagnóstico para verificar el procesamiento de PDFs
"""
import sys
import os

# Verificar Tesseract
print("=" * 60)
print("1. VERIFICANDO TESSERACT OCR")
print("=" * 60)

try:
    import pytesseract
    tesseract_version = pytesseract.get_tesseract_version()
    print(f"✅ Tesseract instalado: versión {tesseract_version}")
except Exception as e:
    print(f"❌ Error con Tesseract: {e}")
    sys.exit(1)

# Verificar PyMuPDF
print("\n" + "=" * 60)
print("2. VERIFICANDO PyMuPDF (fitz)")
print("=" * 60)

try:
    import fitz
    print(f"✅ PyMuPDF instalado: versión {fitz.version}")
except Exception as e:
    print(f"❌ Error con PyMuPDF: {e}")
    sys.exit(1)

# Verificar PIL
print("\n" + "=" * 60)
print("3. VERIFICANDO PIL/Pillow")
print("=" * 60)

try:
    from PIL import Image
    import PIL
    print(f"✅ Pillow instalado: versión {PIL.__version__}")
except Exception as e:
    print(f"❌ Error con Pillow: {e}")
    sys.exit(1)

# Verificar directorios
print("\n" + "=" * 60)
print("4. VERIFICANDO DIRECTORIOS")
print("=" * 60)

dirs_to_check = ['uploads/', 'processed/']
for dir_path in dirs_to_check:
    if os.path.exists(dir_path):
        print(f"✅ Directorio existe: {dir_path}")
    else:
        print(f"⚠️  Directorio no existe: {dir_path} (se creará automáticamente)")

# Probar OCR con un PDF de prueba si existe
print("\n" + "=" * 60)
print("5. PROBANDO OCR (si hay archivos en uploads/)")
print("=" * 60)

upload_files = []
if os.path.exists('uploads/'):
    upload_files = [f for f in os.listdir('uploads/') if f.endswith('.pdf')]

if upload_files:
    print(f"📁 Archivos PDF encontrados: {len(upload_files)}")
    test_file = os.path.join('uploads/', upload_files[0])
    print(f"🔍 Probando con: {upload_files[0]}")
    
    try:
        from utils.ocr_processor import ProcesadorOCR
        processor = ProcesadorOCR()
        
        print("   Extrayendo texto...")
        texto = processor.extraer_texto(test_file)
        print(f"   ✅ Texto extraído: {len(texto)} caracteres")
        print(f"   📝 Primeros 200 caracteres:")
        print(f"   {texto[:200]}")
        
        print("\n   Buscando códigos notariales (año 2024, tipo P)...")
        codigos = processor.buscar_codigos_notariales(texto, "2024", "P")
        print(f"   ✅ Códigos encontrados: {len(codigos)}")
        if codigos:
            print(f"   📋 Códigos: {codigos[:5]}")  # Mostrar primeros 5
        else:
            print("   ⚠️  No se encontraron códigos")
            
    except Exception as e:
        print(f"   ❌ Error durante prueba OCR: {e}")
        import traceback
        traceback.print_exc()
else:
    print("⚠️  No hay archivos PDF en uploads/ para probar")

print("\n" + "=" * 60)
print("DIAGNÓSTICO COMPLETADO")
print("=" * 60)
