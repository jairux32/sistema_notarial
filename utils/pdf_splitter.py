import fitz
import os
import sys
import tempfile
import pytesseract
from PIL import Image
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import MAPEO_TIPOS

class PDFSplitter:
    def dividir_por_codigos(self, pdf_path, codigos, año, mes, tipo, numero_libro, base_output_dir, codigo_a_pagina=None):
        """Divide el PDF en archivos individuales por rangos de páginas entre códigos.
        
        Si codigo_a_pagina se prove, se usa directamente (evita re-buscar en el PDF).
        """
        
        print(f"\n📄 Dividiendo PDF: {pdf_path}")
        print(f"📋 Códigos a buscar: {len(codigos)}")
        
        # Crear directorio de salida
        tipo_nombre = self._mapear_tipo(tipo)
        output_dir = os.path.join(base_output_dir, str(año), str(mes), tipo_nombre, f"LIBRO_{numero_libro}")
        os.makedirs(output_dir, exist_ok=True)
        print(f"📁 Directorio de salida: {output_dir}")
        
        pdf_document = fitz.open(pdf_path)
        total_paginas = len(pdf_document)
        print(f"📖 Total de páginas en PDF: {total_paginas}")
        
        # Si ya tenemos el mapingo, usarlo directamente
        if codigo_a_pagina:
            print(f"\n📋 Usando mapeo pre-calculado ({len(codigo_a_pagina)} códigos)")
            # Filtrar solo códigos que están en el mapeo
            codigo_a_pagina_filtrado = {c: p for c, p in codigo_a_pagina.items() if c in codigos}
        else:
            # Mapear códigos a páginas
            print(f"\n🔍 Mapeando códigos a páginas...")
            codigo_a_pagina_filtrado = {}
            
            for page_num in range(total_paginas):
                page = pdf_document[page_num]
                texto_pagina = page.get_text()
                
                if texto_pagina.startswith('<image:'):
                    texto_pagina = ""
                
                for codigo in codigos:
                    if codigo in texto_pagina and codigo not in codigo_a_pagina_filtrado:
                        codigo_a_pagina_filtrado[codigo] = page_num
                        print(f"   ✅ {codigo} encontrado en página {page_num}")
                
                codigos_faltantes = [c for c in codigos if c not in codigo_a_pagina_filtrado]
                if codigos_faltantes:
                    blocks = page.get_text('blocks')
                    texto_superior = ""
                    for b in blocks:
                        x0, y0, x1, y1 = b[:4]
                        content = b[4]
                        if y0 < 200 and not content.startswith('<image:'):
                            texto_superior += content + "\n"
                    
                    if len(texto_superior.strip()) < 10:
                        rect = page.rect
                        top_rect = fitz.Rect(rect.x0, rect.y0, rect.x1, min(rect.y0 + 200, rect.y1))
                        pix = page.get_pixmap(clip=top_rect)
                        temp_img_path = tempfile.mktemp(suffix='.png')
                        pix.save(temp_img_path)
                        texto_superior = pytesseract.image_to_string(
                            Image.open(temp_img_path), lang='spa'
                        )
                        os.unlink(temp_img_path)
                    
                    for codigo in codigos_faltantes:
                        if codigo in texto_superior:
                            codigo_a_pagina_filtrado[codigo] = page_num
                            print(f"   ✅ {codigo} encontrado en página {page_num} (OCR)")
                    
                    codigos_faltantes_2 = [c for c in codigos_faltantes if c not in codigo_a_pagina_filtrado]
                    if codigos_faltantes_2:
                        texto_corregido = texto_superior
                        for viejo, nuevo in [('O','0'),('o','0'),('l','1'),('I','1'),('|','1'),(' ',''),('\n',''),('\t','')]:
                            texto_corregido = texto_corregido.replace(viejo, nuevo)
                        for codigo in codigos_faltantes_2:
                            if codigo in texto_corregido:
                                codigo_a_pagina_filtrado[codigo] = page_num
                                print(f"   ✅ {codigo} encontrado en página {page_num} (OCR+corrección)")
        
        print(f"\n📊 Total de códigos encontrados en el PDF: {len(codigo_a_pagina_filtrado)}/{len(codigos)}")
        
        # PASO 2: Ordenar códigos por posición en el documento
        codigos_ordenados = sorted(
            codigo_a_pagina_filtrado.items(),
            key=lambda x: x[1]
        )
        
        # PASO 3: Calcular rangos de páginas
        print(f"\n📐 Calculando rangos de páginas...")
        rangos = []
        
        for i, (codigo, pagina_inicio) in enumerate(codigos_ordenados):
            # Si hay un siguiente código, el rango termina antes de él
            if i + 1 < len(codigos_ordenados):
                siguiente_pagina = codigos_ordenados[i + 1][1]
                pagina_fin = siguiente_pagina - 1
            else:
                # Último código: incluir hasta el final del documento
                pagina_fin = total_paginas - 1
            
            total_pags = pagina_fin - pagina_inicio + 1
            rangos.append({
                'codigo': codigo,
                'inicio': pagina_inicio,
                'fin': pagina_fin,
                'total_paginas': total_pags
            })
            
            print(f"   {codigo}: páginas {pagina_inicio}-{pagina_fin} ({total_pags} páginas)")
        
        # PASO 4: Generar PDFs con rangos completos
        print(f"\n💾 Generando PDFs...")
        archivos_generados = []
        
        for rango in rangos:
            nuevo_pdf = fitz.open()
            
            # Insertar TODAS las páginas del rango
            nuevo_pdf.insert_pdf(
                pdf_document,
                from_page=rango['inicio'],
                to_page=rango['fin']
            )
            
            # Nombre del archivo según especificación
            nombre_archivo = f"{rango['codigo']}.pdf"
            output_path = os.path.join(output_dir, nombre_archivo)
            
            nuevo_pdf.save(output_path)
            nuevo_pdf.close()
            
            archivos_generados.append(output_path)
            print(f"   ✅ {nombre_archivo} guardado ({rango['total_paginas']} páginas)")
        
        pdf_document.close()
        print(f"\n✅ Total de archivos generados: {len(archivos_generados)}")
        return archivos_generados
    
    def dividir_por_codigos_con_manual(self, pdf_path, codigos, codigos_manuales, año, mes, tipo, numero_libro, base_output_dir):
        """Divide PDF incluyendo códigos agregados manualmente
        
        Args:
            codigos: Lista de códigos detectados por OCR
            codigos_manuales: Lista de tuplas (codigo, pagina_inicio)
        """
        
        print(f"\n📄 Dividiendo PDF con códigos manuales: {pdf_path}")
        print(f"📋 Códigos totales: {len(codigos)}")
        print(f"🔧 Códigos manuales: {len(codigos_manuales)}")
        
        # Crear directorio de salida
        tipo_nombre = self._mapear_tipo(tipo)
        # Estructura: AÑO / MES / TIPO / LIBRO_X
        output_dir = os.path.join(base_output_dir, str(año), str(mes), tipo_nombre, f"LIBRO_{numero_libro}")
        os.makedirs(output_dir, exist_ok=True)
        print(f"📁 Directorio de salida: {output_dir}")
        
        pdf_document = fitz.open(pdf_path)
        total_paginas = len(pdf_document)
        print(f"📖 Total de páginas en PDF: {total_paginas}")
        
        # PASO 1: Crear mapa de códigos a páginas
        print(f"\n🔍 Mapeando códigos a páginas...")
        codigo_a_pagina = {}
        
        # Agregar códigos manuales primero (tienen prioridad)
        for codigo, pagina in codigos_manuales:
            codigo_a_pagina[codigo] = pagina
            print(f"   🔧 {codigo} agregado manualmente en página {pagina}")
        
        # Luego mapear códigos detectados por OCR (si no están ya)
        for page_num in range(total_paginas):
            page = pdf_document[page_num]
            texto_pagina = page.get_text()
            
            # Buscar en texto original primero
            for codigo in codigos:
                if codigo not in codigo_a_pagina and codigo in texto_pagina:
                    codigo_a_pagina[codigo] = page_num
                    print(f"   ✅ {codigo} encontrado en página {page_num}")
                    break
            
            # Si no encontró, intentar con correcciones OCR
            if not any(c not in codigo_a_pagina for c in codigos):
                texto_corregido = texto_pagina
                correcciones = [
                    ('O', '0'), ('o', '0'),
                    ('l', '1'), ('I', '1'), ('|', '1'),
                    (' ', ''), ('\n', ''), ('\t', '')
                ]
                for viejo, nuevo in correcciones:
                    texto_corregido = texto_corregido.replace(viejo, nuevo)
                
                for codigo in codigos:
                    if codigo not in codigo_a_pagina and codigo in texto_corregido:
                        codigo_a_pagina[codigo] = page_num
                        print(f"   ✅ {codigo} encontrado en página {page_num} (OCR)")
                        break
        
        print(f"\n📊 Total de códigos mapeados: {len(codigo_a_pagina)}/{len(codigos)}")
        
        # PASO 2: Ordenar códigos por posición en el documento
        codigos_ordenados = sorted(
            codigo_a_pagina.items(),
            key=lambda x: x[1]  # Ordenar por número de página
        )
        
        # PASO 3: Calcular rangos de páginas
        print(f"\n📐 Calculando rangos de páginas...")
        rangos = []
        
        for i, (codigo, pagina_inicio) in enumerate(codigos_ordenados):
            # Si hay un siguiente código, el rango termina antes de él
            if i + 1 < len(codigos_ordenados):
                siguiente_pagina = codigos_ordenados[i + 1][1]
                pagina_fin = siguiente_pagina - 1
            else:
                # Último código: incluir hasta el final del documento
                pagina_fin = total_paginas - 1
            
            total_pags = pagina_fin - pagina_inicio + 1
            rangos.append({
                'codigo': codigo,
                'inicio': pagina_inicio,
                'fin': pagina_fin,
                'total_paginas': total_pags
            })
            
            print(f"   {codigo}: páginas {pagina_inicio}-{pagina_fin} ({total_pags} páginas)")
        
        # PASO 4: Generar PDFs con rangos completos
        print(f"\n💾 Generando PDFs...")
        archivos_generados = []
        
        for rango in rangos:
            nuevo_pdf = fitz.open()
            
            # Insertar TODAS las páginas del rango
            nuevo_pdf.insert_pdf(
                pdf_document,
                from_page=rango['inicio'],
                to_page=rango['fin']
            )
            
            # Nombre del archivo según especificación
            nombre_archivo = f"{rango['codigo']}.pdf"
            output_path = os.path.join(output_dir, nombre_archivo)
            
            nuevo_pdf.save(output_path)
            nuevo_pdf.close()
            
            archivos_generados.append(output_path)
            print(f"   ✅ {nombre_archivo} guardado ({rango['total_paginas']} páginas)")
        
        pdf_document.close()
        print(f"\n✅ Total de archivos generados: {len(archivos_generados)}")
        return archivos_generados
    
    def _mapear_tipo(self, tipo):
        """Mapea letra de tipo a nombre completo"""
        return MAPEO_TIPOS.get(tipo, 'OTROS')