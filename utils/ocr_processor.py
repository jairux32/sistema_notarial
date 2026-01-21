import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import fitz  # PyMuPDF
import re
import tempfile
import os
import sys

# Añadir esto al inicio de la clase
class ProcesadorOCR:
    def __init__(self):
        self.codigo_notaria = "1101007"
        # Configurar ruta de Tesseract para Ubuntu
        pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
    
    def extraer_texto(self, pdf_path):
        """Extrae texto del PDF usando texto nativo cuando está disponible, OCR como fallback"""
        texto_completo = ""
        
        # Abrir PDF
        pdf_document = fitz.open(pdf_path)
        total_paginas = len(pdf_document)
        
        paginas_texto_nativo = 0
        paginas_ocr = 0
        
        print(f"📄 Extrayendo texto de {total_paginas} páginas...")
        
        for page_num in range(total_paginas):
            page = pdf_document[page_num]
            
            # ESTRATEGIA HÍBRIDA: Intentar texto nativo primero
            texto_nativo = page.get_text()
            
            # Si tiene contenido útil (>50 caracteres), usar texto nativo
            if len(texto_nativo.strip()) > 50:
                texto_completo += texto_nativo + "\n"
                paginas_texto_nativo += 1
                
                # Mostrar progreso cada 50 páginas
                if (page_num + 1) % 50 == 0:
                    print(f"   Procesadas {page_num + 1}/{total_paginas} páginas (nativo: {paginas_texto_nativo}, OCR: {paginas_ocr})")
            else:
                # Si no tiene texto nativo, usar OCR
                pix = page.get_pixmap()
                temp_img_path = tempfile.mktemp(suffix='.png')
                pix.save(temp_img_path)
                
                # Aplicar OCR
                texto_pagina = pytesseract.image_to_string(
                    Image.open(temp_img_path),
                    lang='spa'
                )
                texto_completo += texto_pagina + "\n"
                paginas_ocr += 1
                
                # Limpiar archivo temporal
                os.unlink(temp_img_path)
                
                # Mostrar progreso cada 50 páginas
                if (page_num + 1) % 50 == 0:
                    print(f"   Procesadas {page_num + 1}/{total_paginas} páginas (nativo: {paginas_texto_nativo}, OCR: {paginas_ocr})")
        
        pdf_document.close()
        
        print(f"\n✅ Extracción completada:")
        print(f"   📄 Texto nativo: {paginas_texto_nativo} páginas ({paginas_texto_nativo/total_paginas*100:.1f}%)")
        print(f"   🔍 OCR: {paginas_ocr} páginas ({paginas_ocr/total_paginas*100:.1f}%)")
        
        return texto_completo
    
    def buscar_codigos_notariales(self, texto, año_config, tipo_config):
        """Busca y corrige códigos notariales según el patrón"""
        
        print(f"🔍 Buscando códigos para año={año_config}, tipo={tipo_config}")
        print(f"📝 Texto original: {len(texto)} caracteres")
        
        # Correcciones OCR comunes
        correcciones = [
            ('O', '0'), ('o', '0'),  # O mayúscula/minúscula → 0
            ('l', '1'), ('I', '1'), ('|', '1'),  # l, I, | → 1
            (' ', ''), ('\n', ''), ('\t', '')  # Eliminar espacios
        ]
        
        texto_corregido = texto
        for viejo, nuevo in correcciones:
            texto_corregido = texto_corregido.replace(viejo, nuevo)
        
        print(f"📝 Texto corregido: {len(texto_corregido)} caracteres")
        
        # Patrón regex para códigos notariales - CORREGIDO: usar año completo
        patron = rf'{año_config}{self.codigo_notaria}[{tipo_config}]\d{{5}}'
        print(f"🔎 Patrón regex: {patron}")
        
        # Buscar todos los códigos
        codigos_encontrados = re.findall(patron, texto_corregido)
        print(f"✅ Códigos encontrados (con regex): {len(codigos_encontrados)}")
        
        # Eliminar duplicados manteniendo orden
        codigos_unicos = []
        for codigo in codigos_encontrados:
            if codigo not in codigos_unicos:
                codigos_unicos.append(codigo)
        
        print(f"📋 Códigos únicos: {len(codigos_unicos)}")
        if codigos_unicos:
            print(f"   Primeros 5: {codigos_unicos[:5]}")
        
        # Detectar códigos faltantes en el rango
        faltantes = self.detectar_codigos_faltantes(codigos_unicos, año_config, tipo_config)
        if faltantes:
            print(f"\n⚠️  Códigos faltantes detectados: {len(faltantes)}")
            print(f"   Faltantes: {faltantes[:10]}")
        
        return codigos_unicos
    
    def detectar_codigos_faltantes(self, codigos_encontrados, año, tipo):
        """Detecta códigos que deberían existir pero no se encontraron"""
        if not codigos_encontrados:
            return []
        
        # Extraer secuenciales
        secuenciales = sorted([int(c[-5:]) for c in codigos_encontrados])
        min_sec = secuenciales[0]
        max_sec = secuenciales[-1]
        
        # Detectar faltantes en el rango
        faltantes = []
        for sec in range(min_sec, max_sec + 1):
            codigo_esperado = f"{año}{self.codigo_notaria}{tipo}{sec:05d}"
            if codigo_esperado not in codigos_encontrados:
                faltantes.append(codigo_esperado)
        
        return faltantes