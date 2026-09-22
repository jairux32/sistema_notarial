import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import fitz  # PyMuPDF
import re
import tempfile
import os
import sys

class ProcesadorOCR:
    def __init__(self):
        self.codigo_notaria = "1101007"
        from config import TESSERACT_CMD
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    
    def extraer_texto(self, pdf_path, solo_zona_superior=False):
        """Extrae texto del PDF usando texto nativo cuando está disponible, OCR como fallback.
        
        Si solo_zona_superior=True, solo extrae OCR de los primeros ~150px (más rápido).
        """
        texto_completo = ""
        
        pdf_document = fitz.open(pdf_path)
        total_paginas = len(pdf_document)
        
        paginas_texto_nativo = 0
        paginas_ocr = 0
        
        print(f"📄 Extrayendo texto de {total_paginas} páginas...")
        
        for page_num in range(total_paginas):
            page = pdf_document[page_num]
            
            if solo_zona_superior:
                # Solo extraer bloques de la zona superior (y < 150)
                blocks = page.get_text('blocks')
                texto_nativo = ""
                for b in blocks:
                    x0, y0, x1, y1 = b[:4]
                    content = b[4]
                    if y0 < 150 and not content.startswith('<image:'):
                        texto_nativo += content + "\n"
            else:
                texto_nativo = page.get_text()
            
            if len(texto_nativo.strip()) > 20:
                texto_completo += texto_nativo + "\n"
                paginas_texto_nativo += 1
            else:
                if solo_zona_superior:
                    # Cropear solo la zona superior para OCR (mucho más rápido)
                    rect = page.rect
                    top_rect = fitz.Rect(rect.x0, rect.y0, rect.x1, min(rect.y0 + 200, rect.y1))
                    pix = page.get_pixmap(clip=top_rect)
                else:
                    pix = page.get_pixmap()
                
                temp_img_path = tempfile.mktemp(suffix='.png')
                pix.save(temp_img_path)
                
                texto_pagina = pytesseract.image_to_string(
                    Image.open(temp_img_path),
                    lang='spa'
                )
                texto_completo += texto_pagina + "\n"
                paginas_ocr += 1
                
                os.unlink(temp_img_path)
            
            if (page_num + 1) % 100 == 0:
                print(f"   Procesadas {page_num + 1}/{total_paginas} páginas (nativo: {paginas_texto_nativo}, OCR: {paginas_ocr})")
        
        pdf_document.close()
        
        print(f"\n✅ Extracción completada:")
        print(f"   📄 Texto nativo: {paginas_texto_nativo} páginas ({paginas_texto_nativo/total_paginas*100:.1f}%)")
        print(f"   🔍 OCR: {paginas_ocr} páginas ({paginas_ocr/total_paginas*100:.1f}%)")
        
        return texto_completo
    
    def _normalizar_texto(self, texto):
        """Normaliza texto OCR para mejorar coincidencias"""
        # Eliminar espacios y saltos de línea múltiples
        texto = re.sub(r'\s+', ' ', texto)
        # Correcciones OCR comunes
        correcciones = {
            'O': '0', 'o': '0',
            'I': '1', 'l': '1', '|': '1',
            'S': '5', 'B': '8', 'G': '6',
            'Z': '2', 'T': '7',
        }
        resultado = []
        for char in texto:
            resultado.append(correcciones.get(char, char))
        return ''.join(resultado)
    
    def _extraer_secuencial_despues_tipo(self, texto, tipo_config):
        """Extrae el secuencial después de la letra tipo en un código notarial.
        
        Maneja corrupciones OCR como:
        - P\n1\n94696 → secuencial es 1
        - PI\n9 → secuencial es 9
        - P0G041 → secuencial es 41
        - PQ0073 → secuencial es 73
        - PO(}035 → secuencial es 35
        """
        tipo_match = re.search(rf'[{tipo_config}]', texto)
        if not tipo_match:
            return None
        
        after_tipo = texto[tipo_match.end():]
        
        # Buscar en las primeras 5 líneas después del tipo
        lineas = after_tipo.split('\n')
        for linea in lineas[:5]:
            linea = linea.strip()
            if not linea:
                continue
            
            # Extraer todos los dígitos de la línea, ignorando caracteres no-dígito
            # Esto maneja corrupciones como P0G041 → extrae [0,0,4,1] → 00041
            # y PO(}035 → extrae [0,3,5] → 00035
            todos_digitos = re.findall(r'\d', linea)
            if not todos_digitos:
                continue
            
            # Tomar los primeros 5 dígitos como secuencial
            sec_raw = ''.join(todos_digitos[:5])
            sec = sec_raw.zfill(5)
            if 1 <= int(sec) <= 999:
                return sec
        
        return None
    
    def _buscar_en_pagina(self, texto_pagina, año_config, tipo_config, blocks=None):
        """Busca códigos notariales en el texto de una página"""
        codigos = []
        
        # Estrategia 1: Patrón exacto en texto original
        patron_exacto = rf'{año_config}{self.codigo_notaria}[{tipo_config}]\d{{5}}'
        codigos.extend(re.findall(patron_exacto, texto_pagina))
        
        # Estrategia 2: Patrón con flexibilidad en tipo
        patron_tipo = rf'{año_config}{self.codigo_notaria}[{tipo_config}A-Z0]\d{{5}}'
        for match in re.findall(patron_tipo, texto_pagina):
            if match not in codigos:
                codigos.append(match)
        
        # Estrategia 3: "1101007" + tipo + 5 dígitos (sin año)
        patron_base = rf'{self.codigo_notaria}[{tipo_config}A-Z]\d{{5}}'
        for match in re.findall(patron_base, texto_pagina):
            codigo_completo = f"{año_config}{match}"
            if codigo_completo not in codigos:
                codigos.append(codigo_completo)
        
        # Estrategia 4: Texto normalizado
        texto_norm = self._normalizar_texto(texto_pagina)
        patron_norm = rf'{año_config}{self.codigo_notaria}[{tipo_config}0]\d{{5}}'
        for match in re.findall(patron_norm, texto_norm):
            if match[15] == '0' and tipo_config != '0':
                match = match[:15] + tipo_config + match[16:]
            if match not in codigos:
                codigos.append(match)
        
        # Estrategia 5: Código partido con salto de línea
        patron_partido = rf'{año_config}{self.codigo_notaria}[{tipo_config}]\s*\d{{5}}'
        for match in re.findall(patron_partido, texto_pagina):
            limpio = re.sub(r'\s+', '', match)
            if limpio not in codigos:
                codigos.append(limpio)
        
        # Estrategia 6: ANCHOR mejororado - "1101007" + tipo + secuencial
        # Usa _extraer_secuencial_despues_tipo para manejar corrupciones OCR
        for match in re.finditer(r'1101007', texto_pagina):
            idx = match.start()
            contexto = texto_pagina[idx+7:idx+30]
            sec = self._extraer_secuencial_despues_tipo(contexto, tipo_config)
            if sec:
                codigo = f"{año_config}{self.codigo_notaria}{tipo_config}{sec}"
                if codigo not in codigos:
                    codigos.append(codigo)
        
        # Estrategia 7: Búsqueda agresiva con normalización extendida
        # Solo normaliza caracteres ambiguos en contexto de código (cerca del patrón)
        # Buscar la región del código notarial primero, luego normalizar solo esa región
        patron_region = rf'{self.codigo_notaria}[A-Z0-9]{{10}}'
        for region_match in re.finditer(patron_region, texto_pagina):
            region = region_match.group()
            region_norm = re.sub(r'[OoQqGgCc]', '0', region)
            region_norm = re.sub(r'[IiLl|]', '1', region_norm)
            patron_agresivo = rf'{año_config}{tipo_config}\d{{1,5}}'
            for match in re.findall(patron_agresivo, region_norm):
                codigo_completo = f"{año_config}{self.codigo_notaria}{match}"
                if len(codigo_completo) == 17 and codigo_completo not in codigos:
                    codigos.append(codigo_completo)
        
        # Estrategia 8: Búsqueda con notaria_code + ruido antes del tipo + tipo + dígitos
        # Maneja casos como: 1101007PO(}035, 1101007P0G041, 1101007PG0043
        patron_ruido_tipo = rf'{self.codigo_notaria}[A-Z][IiLl|OoQqGgCcSsZzTt]*[{tipo_config}]\d{{1,5}}'
        for match in re.findall(patron_ruido_tipo, texto_pagina):
            tipo_idx = match.rfind(tipo_config)
            if tipo_idx >= 0:
                limpio = match[tipo_idx:]
                codigo_completo = f"{año_config}{self.codigo_notaria}{limpio}"
                if len(codigo_completo) == 17 and codigo_completo not in codigos:
                    codigos.append(codigo_completo)
        
        # Filtrar códigos inválidos
        codigos_filtrados = []
        for c in codigos:
            sec_str = c[-5:]
            if len(c) == 17 and sec_str.isdigit():
                sec = int(sec_str)
                if sec <= 999:
                    codigos_filtrados.append(c)
        
        return list(set(codigos_filtrados))
    
    def buscar_codigos_notariales(self, texto, año_config, tipo_config, pdf_path=None):
        """Busca códigos notariales. Si se prove pdf_path, busca página por página (más preciso)"""
        
        print(f"🔍 Buscando códigos para año={año_config}, tipo={tipo_config}")
        
        # Si se prove el path del PDF, buscar página por página
        if pdf_path:
            codigos, _ = self._buscar_en_pdf(pdf_path, año_config, tipo_config)
            return codigos
        
        # Fallback: buscar en texto concatenado
        print(f"📝 Texto total: {len(texto)} caracteres")
        paginas = texto.split('\n\n')
        
        todos_los_codigos = []
        paginas_con_codigo = 0
        
        for i, pagina in enumerate(paginas):
            if len(pagina.strip()) < 10:
                continue
            codigos_pagina = self._buscar_en_pagina(pagina, año_config, tipo_config)
            if codigos_pagina:
                paginas_con_codigo += 1
                todos_los_codigos.extend(codigos_pagina)
        
        print(f"\n📊 Resumen:")
        print(f"   Páginas: {len(paginas)}, Con código: {paginas_con_codigo}")
        
        return self._filtrar_codigos(todos_los_codigos, año_config, tipo_config)
    
    def _buscar_en_pdf(self, pdf_path, año_config, tipo_config):
        """Busca códigos directamente en el PDF, página por página, zona superior.
        Retorna (codigos, codigo_a_pagina)"""
        import fitz
        from PIL import Image
        
        pdf_document = fitz.open(pdf_path)
        total_paginas = len(pdf_document)
        print(f"📄 Analizando {total_paginas} páginas del PDF...")
        
        todos_los_codigos = []
        codigo_a_pagina = {}
        paginas_con_codigo = 0
        
        for page_num in range(total_paginas):
            page = pdf_document[page_num]
            
            # Extraer bloques de la zona superior (y < 150)
            blocks = page.get_text('blocks')
            texto_superior = ""
            for b in blocks:
                x0, y0, x1, y1 = b[:4]
                content = b[4]
                if y0 < 150 and not content.startswith('<image:'):
                    texto_superior += content + "\n"
            
            # Si no hay texto nativo en zona superior, usar OCR
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
            
            codigos_pagina = self._buscar_en_pagina(texto_superior, año_config, tipo_config)
            
            if codigos_pagina:
                paginas_con_codigo += 1
                for c in codigos_pagina:
                    if c not in codigo_a_pagina:
                        codigo_a_pagina[c] = page_num
                todos_los_codigos.extend(codigos_pagina)
            
            if (page_num + 1) % 200 == 0:
                print(f"   {page_num + 1}/{total_paginas} páginas...")
        
        pdf_document.close()
        
        print(f"\n📊 Resumen:")
        print(f"   Páginas: {total_paginas}, Con código: {paginas_con_codigo}")
        
        codigos_filtrados = self._filtrar_codigos(todos_los_codigos, año_config, tipo_config)
        return codigos_filtrados, codigo_a_pagina
    
    def _filtrar_codigos(self, todos_los_codigos, año_config, tipo_config):
        """Filtra y deduplica códigos"""
        codigos_raw = list(dict.fromkeys(todos_los_codigos))
        
        codigos_unicos = []
        for c in codigos_raw:
            sec_str = c[-5:]
            tipo_letra = c[11] if len(c) >= 12 else None
            if len(c) == 17 and sec_str.isdigit() and tipo_letra == tipo_config:
                sec = int(sec_str)
                if sec <= 999:
                    codigos_unicos.append(c)
        
        print(f"   Códigos válidos: {len(codigos_unicos)}")
        if codigos_unicos:
            sorted_codes = sorted(codigos_unicos)
            print(f"   Rango: {sorted_codes[0]} - {sorted_codes[-1]}")
            print(f"   Primeros 10: {sorted_codes[:10]}")
        
        faltantes = self.detectar_codigos_faltantes(codigos_unicos, año_config, tipo_config)
        if faltantes:
            print(f"\n⚠️  Faltantes: {len(faltantes)}")
            print(f"   {faltantes[:15]}...")
        
        return codigos_unicos
    
    def detectar_codigos_faltantes(self, codigos_encontrados, año, tipo):
        """Detecta códigos que deberían existir pero no se encontraron"""
        if not codigos_encontrados:
            return []
        
        secuenciales = sorted([int(c[-5:]) for c in codigos_encontrados])
        min_sec = secuenciales[0]
        max_sec = secuenciales[-1]
        
        faltantes = []
        for sec in range(min_sec, max_sec + 1):
            codigo_esperado = f"{año}{self.codigo_notaria}{tipo}{sec:05d}"
            if codigo_esperado not in codigos_encontrados:
                faltantes.append(codigo_esperado)
        
        return faltantes
