from __future__ import annotations
from typing import Tuple, List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import re
import tempfile
import os
import multiprocessing

def _ocr_page(args) -> Tuple[int, str]:
    """Worker function for parallel OCR. Receives (page_num, pix_data, temp_dir).
    Returns (page_num, texto_ocr). Runs in a separate thread."""
    page_num, pix_data, temp_dir = args
    temp_img_path = os.path.join(temp_dir, f'page_{page_num}.png')
    try:
        with open(temp_img_path, 'wb') as f:
            f.write(pix_data)
        texto = pytesseract.image_to_string(
            Image.open(temp_img_path), lang='spa'
        )
        return page_num, texto
    finally:
        try:
            os.unlink(temp_img_path)
        except OSError:
            pass


class ProcesadorOCR:
    def __init__(self) -> None:
        self.codigo_notaria = "1101007"
        from config import TESSERACT_CMD
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

    def extraer_texto(self, pdf_path: str, solo_zona_superior: bool = False) -> str:
        """Extrae texto del PDF usando texto nativo cuando está disponible, OCR como fallback."""
        texto_completo = ""
        paginas_texto_nativo = 0
        paginas_ocr = 0

        with fitz.open(pdf_path) as pdf_document:
            total_paginas = len(pdf_document)
            print(f"📄 Extrayendo texto de {total_paginas} páginas...")

            for page_num in range(total_paginas):
                page = pdf_document[page_num]

                if solo_zona_superior:
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
                        rect = page.rect
                        top_rect = fitz.Rect(rect.x0, rect.y0, rect.x1, min(rect.y0 + 200, rect.y1))
                        pix = page.get_pixmap(clip=top_rect)
                    else:
                        pix = page.get_pixmap()

                    temp_img_path = tempfile.mktemp(suffix='.png')
                    pix.save(temp_img_path)
                    texto_pagina = pytesseract.image_to_string(
                        Image.open(temp_img_path), lang='spa'
                    )
                    texto_completo += texto_pagina + "\n"
                    paginas_ocr += 1
                    os.unlink(temp_img_path)

                if (page_num + 1) % 100 == 0:
                    print(f"   Procesadas {page_num + 1}/{total_paginas} páginas")

        print(f"✅ Extracción completada: nativo={paginas_texto_nativo}, OCR={paginas_ocr}")
        return texto_completo

    def _normalizar_texto(self, texto: str) -> str:
        """Normaliza texto OCR para mejorar coincidencias"""
        texto = re.sub(r'\s+', ' ', texto)
        correcciones = {
            'O': '0', 'o': '0',
            'I': '1', 'l': '1', '|': '1',
            'S': '5', 'B': '8', 'G': '6',
            'Z': '2', 'T': '7',
        }
        return ''.join(correcciones.get(c, c) for c in texto)

    def _extraer_secuencial_despues_tipo(self, texto: str, tipo_config: str) -> Optional[str]:
        """Extrae el secuencial después de la letra tipo en un código notarial."""
        tipo_match = re.search(rf'[{tipo_config}]', texto)
        if not tipo_match:
            return None

        after_tipo = texto[tipo_match.end():]
        lineas = after_tipo.split('\n')
        for linea in lineas[:5]:
            linea = linea.strip()
            if not linea:
                continue
            todos_digitos = re.findall(r'\d', linea)
            if not todos_digitos:
                continue
            sec_raw = ''.join(todos_digitos[:5])
            sec = sec_raw.zfill(5)
            if 1 <= int(sec) <= 999:
                return sec
        return None

    def _buscar_en_pagina(self, texto_pagina: str, año_config: str, tipo_config: str, blocks=None) -> List[str]:
        """Busca códigos notariales en el texto de una página"""
        codigos = []

        patron_exacto = rf'{año_config}{self.codigo_notaria}[{tipo_config}]\d{{5}}'
        codigos.extend(re.findall(patron_exacto, texto_pagina))

        patron_tipo = rf'{año_config}{self.codigo_notaria}[{tipo_config}A-Z0]\d{{5}}'
        for match in re.findall(patron_tipo, texto_pagina):
            if match not in codigos:
                codigos.append(match)

        patron_base = rf'{self.codigo_notaria}[{tipo_config}A-Z]\d{{5}}'
        for match in re.findall(patron_base, texto_pagina):
            codigo_completo = f"{año_config}{match}"
            if codigo_completo not in codigos:
                codigos.append(codigo_completo)

        texto_norm = self._normalizar_texto(texto_pagina)
        patron_norm = rf'{año_config}{self.codigo_notaria}[{tipo_config}0]\d{{5}}'
        for match in re.findall(patron_norm, texto_norm):
            if match[15] == '0' and tipo_config != '0':
                match = match[:15] + tipo_config + match[16:]
            if match not in codigos:
                codigos.append(match)

        patron_partido = rf'{año_config}{self.codigo_notaria}[{tipo_config}]\s*\d{{5}}'
        for match in re.findall(patron_partido, texto_pagina):
            limpio = re.sub(r'\s+', '', match)
            if limpio not in codigos:
                codigos.append(limpio)

        for match in re.finditer(r'1101007', texto_pagina):
            idx = match.start()
            contexto = texto_pagina[idx+7:idx+30]
            sec = self._extraer_secuencial_despues_tipo(contexto, tipo_config)
            if sec:
                codigo = f"{año_config}{self.codigo_notaria}{tipo_config}{sec}"
                if codigo not in codigos:
                    codigos.append(codigo)

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

        patron_ruido_tipo = rf'{self.codigo_notaria}[A-Z][IiLl|OoQqGgCcSsZzTt]*[{tipo_config}]\d{{1,5}}'
        for match in re.findall(patron_ruido_tipo, texto_pagina):
            tipo_idx = match.rfind(tipo_config)
            if tipo_idx >= 0:
                limpio = match[tipo_idx:]
                codigo_completo = f"{año_config}{self.codigo_notaria}{limpio}"
                if len(codigo_completo) == 17 and codigo_completo not in codigos:
                    codigos.append(codigo_completo)

        codigos_filtrados = []
        for c in codigos:
            sec_str = c[-5:]
            if len(c) == 17 and sec_str.isdigit():
                sec = int(sec_str)
                if sec <= 999:
                    codigos_filtrados.append(c)

        return list(set(codigos_filtrados))

    def buscar_codigos_notariales(
        self, texto: str, año_config: str, tipo_config: str,
        pdf_path: Optional[str] = None,
        pdf_document: Optional[fitz.Document] = None,
    ) -> Tuple[List[str], Dict[str, int]]:
        """Busca códigos notariales. Si se prove pdf_path o pdf_document, busca página por página."""
        print(f"🔍 Buscando códigos para año={año_config}, tipo={tipo_config}")

        if pdf_document is not None:
            codigos, codigo_a_pagina = self._buscar_en_pdf(
                pdf_path or '', año_config, tipo_config, pdf_document=pdf_document
            )
            return codigos, codigo_a_pagina

        if pdf_path:
            codigos, codigo_a_pagina = self._buscar_en_pdf(pdf_path, año_config, tipo_config)
            return codigos, codigo_a_pagina

        print(f"📝 Texto total: {len(texto)} caracteres")
        paginas = texto.split('\n\n')
        todos_los_codigos = []
        paginas_con_codigo = 0

        for pagina in paginas:
            if len(pagina.strip()) < 10:
                continue
            codigos_pagina = self._buscar_en_pagina(pagina, año_config, tipo_config)
            if codigos_pagina:
                paginas_con_codigo += 1
                todos_los_codigos.extend(codigos_pagina)

        print(f"📊 Páginas: {len(paginas)}, Con código: {paginas_con_codigo}")
        return self._filtrar_codigos(todos_los_codigos, año_config, tipo_config), {}

    def _buscar_en_pdf(
        self, pdf_path: str, año_config: str, tipo_config: str,
        pdf_document: Optional[fitz.Document] = None,
    ) -> Tuple[List[str], Dict[str, int]]:
        """Busca códigos directamente en el PDF, página por página, zona superior.
        Si se prove pdf_document, lo reutiliza en vez de abrir uno nuevo.
        Retorna (codigos, codigo_a_pagina)"""

        owns_doc = False
        if pdf_document is None:
            pdf_document = fitz.open(pdf_path)
            owns_doc = True

        try:
            total_paginas = len(pdf_document)
            print(f"📄 Analizando {total_paginas} páginas del PDF...")

            # Phase 1: Extract text from all pages serially (fast)
            pages_needing_ocr = []
            pages_text = {}
            for page_num in range(total_paginas):
                page = pdf_document[page_num]
                blocks = page.get_text('blocks')
                texto_superior = ""
                for b in blocks:
                    x0, y0, x1, y1 = b[:4]
                    content = b[4]
                    if y0 < 150 and not content.startswith('<image:'):
                        texto_superior += content + "\n"

                if len(texto_superior.strip()) < 10:
                    # Need OCR — serialize page to PNG for parallel processing
                    rect = page.rect
                    top_rect = fitz.Rect(rect.x0, rect.y0, rect.x1, min(rect.y0 + 200, rect.y1))
                    pix = page.get_pixmap(clip=top_rect)
                    png_data = pix.tobytes("png")
                    pages_needing_ocr.append((page_num, png_data))
                else:
                    pages_text[page_num] = texto_superior

            # Phase 2: Parallel OCR on pages that need it (CPU-bound, uses threads)
            if pages_needing_ocr:
                max_workers = min(len(pages_needing_ocr), multiprocessing.cpu_count(), 4)
                print(f"🔍 OCR paralelo: {len(pages_needing_ocr)} páginas con {max_workers} workers...")

                temp_dir = tempfile.mkdtemp(prefix='ocr_')
                try:
                    ocr_args = [(pn, data, temp_dir) for pn, data in pages_needing_ocr]
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        futures = {executor.submit(_ocr_page, args): args[0] for args in ocr_args}
                        for future in as_completed(futures):
                            page_num, texto = future.result()
                            pages_text[page_num] = texto
                finally:
                    try:
                        os.rmdir(temp_dir)
                    except OSError:
                        pass

            # Phase 3: Search for codes in extracted text (serial, fast regex)
            todos_los_codigos = []
            codigo_a_pagina = {}
            paginas_con_codigo = 0

            for page_num in range(total_paginas):
                texto_superior = pages_text.get(page_num, "")
                codigos_pagina = self._buscar_en_pagina(texto_superior, año_config, tipo_config)

                if codigos_pagina:
                    paginas_con_codigo += 1
                    for c in codigos_pagina:
                        if c not in codigo_a_pagina:
                            codigo_a_pagina[c] = page_num
                    todos_los_codigos.extend(codigos_pagina)

                if (page_num + 1) % 200 == 0:
                    print(f"   {page_num + 1}/{total_paginas} páginas...")

            print(f"📊 Páginas: {total_paginas}, Con código: {paginas_con_codigo}")

            codigos_filtrados = self._filtrar_codigos(todos_los_codigos, año_config, tipo_config)
            return codigos_filtrados, codigo_a_pagina

        finally:
            if owns_doc:
                pdf_document.close()

    def _filtrar_codigos(self, todos_los_codigos: List[str], año_config: str, tipo_config: str) -> List[str]:
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

        faltantes = self.detectar_codigos_faltantes(codigos_unicos, año_config, tipo_config)
        if faltantes:
            print(f"⚠️  Faltantes: {len(faltantes)}")

        return codigos_unicos

    def detectar_codigos_faltantes(self, codigos_encontrados: List[str], año: str, tipo: str) -> List[str]:
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
