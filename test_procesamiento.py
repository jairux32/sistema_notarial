#!/usr/bin/env python3
"""
Script de prueba para verificar el procesamiento completo
"""
import sys
import os

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.ocr_processor import ProcesadorOCR
from utils.pdf_splitter import PDFSplitter
from utils.validator import ValidadorNotarial

print("="*60)
print("PRUEBA DE PROCESAMIENTO COMPLETO")
print("="*60)

# Buscar archivos PDF en uploads/
upload_files = []
if os.path.exists('uploads/'):
    upload_files = [f for f in os.listdir('uploads/') if f.endswith('.pdf')]

if not upload_files:
    print("❌ No hay archivos PDF en uploads/ para probar")
    sys.exit(1)

test_file = os.path.join('uploads/', upload_files[0])
print(f"\n📁 Archivo de prueba: {upload_files[0]}")

# Configuración
año = "2025"
tipo = "A"  # Arriendos

print(f"📅 Año: {año}")
print(f"📚 Tipo: {tipo}")

try:
    # 1. OCR
    print("\n" + "="*60)
    print("PASO 1: EXTRACCIÓN OCR")
    print("="*60)
    processor = ProcesadorOCR()
    texto = processor.extraer_texto(test_file)
    print(f"✅ Extraídos {len(texto)} caracteres")
    
    # 2. Buscar códigos
    print("\n" + "="*60)
    print("PASO 2: BÚSQUEDA DE CÓDIGOS")
    print("="*60)
    codigos = processor.buscar_codigos_notariales(texto, año, tipo)
    
    if not codigos:
        print("❌ No se encontraron códigos")
        print("\n📝 Muestra del texto extraído (primeros 500 caracteres):")
        print(texto[:500])
        sys.exit(1)
    
    print(f"\n✅ Total de códigos encontrados: {len(codigos)}")
    print(f"📋 Códigos: {codigos[:10]}")  # Mostrar primeros 10
    
    # 3. Validar
    print("\n" + "="*60)
    print("PASO 3: VALIDACIÓN")
    print("="*60)
    validador = ValidadorNotarial()
    validacion = validador.validar_secuenciales(codigos)
    print(f"✅ Validación completada")
    print(f"   Primer secuencial: {validacion.get('primer_secuencial')}")
    print(f"   Último secuencial: {validacion.get('ultimo_secuencial')}")
    print(f"   Es continuo: {validacion.get('es_continuo')}")
    
    # 4. Dividir
    print("\n" + "="*60)
    print("PASO 4: DIVISIÓN DE PDF")
    print("="*60)
    splitter = PDFSplitter()
    archivos = splitter.dividir_por_codigos(
        test_file,
        codigos,
        año,
        tipo,
        'processed/'
    )
    
    print(f"\n✅ Archivos generados: {len(archivos)}")
    if archivos:
        print(f"📁 Ubicación: processed/{año}/ARRIENDOS/")
        print(f"📄 Primeros 5 archivos:")
        for archivo in archivos[:5]:
            print(f"   - {os.path.basename(archivo)}")
    
    print("\n" + "="*60)
    print("✅ PRUEBA COMPLETADA EXITOSAMENTE")
    print("="*60)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
