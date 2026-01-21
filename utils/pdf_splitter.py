import fitz
import os

class PDFSplitter:
    def dividir_por_codigos(self, pdf_path, codigos, año, tipo, base_output_dir):
        """Divide el PDF en archivos individuales por rangos de páginas entre códigos"""
        
        print(f"\n📄 Dividiendo PDF: {pdf_path}")
        print(f"📋 Códigos a buscar: {len(codigos)}")
        
        # Crear directorio de salida
        tipo_nombre = self._mapear_tipo(tipo)
        output_dir = os.path.join(base_output_dir, str(año), tipo_nombre)
        os.makedirs(output_dir, exist_ok=True)
        print(f"📁 Directorio de salida: {output_dir}")
        
        pdf_document = fitz.open(pdf_path)
        total_paginas = len(pdf_document)
        print(f"📖 Total de páginas en PDF: {total_paginas}")
        
        # PASO 1: Mapear códigos a páginas (una sola pasada por el documento)
        print(f"\n🔍 Mapeando códigos a páginas...")
        codigo_a_pagina = {}
        
        for page_num in range(total_paginas):
            page = pdf_document[page_num]
            texto_pagina = page.get_text()
            
            # Aplicar las mismas correcciones OCR
            texto_corregido = texto_pagina
            correcciones = [
                ('O', '0'), ('o', '0'),
                ('l', '1'), ('I', '1'), ('|', '1'),
                (' ', ''), ('\n', ''), ('\t', '')
            ]
            for viejo, nuevo in correcciones:
                texto_corregido = texto_corregido.replace(viejo, nuevo)
            
            # Buscar códigos en esta página
            for codigo in codigos:
                if codigo in texto_corregido and codigo not in codigo_a_pagina:
                    codigo_a_pagina[codigo] = page_num
                    print(f"   ✅ {codigo} encontrado en página {page_num}")
                    break  # Pasar a la siguiente página
        
        print(f"\n📊 Total de códigos encontrados en el PDF: {len(codigo_a_pagina)}/{len(codigos)}")
        
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
    
    def dividir_por_codigos_con_manual(self, pdf_path, codigos, codigos_manuales, año, tipo, base_output_dir):
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
        output_dir = os.path.join(base_output_dir, str(año), tipo_nombre)
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
            
            # Aplicar las mismas correcciones OCR
            texto_corregido = texto_pagina
            correcciones = [
                ('O', '0'), ('o', '0'),
                ('l', '1'), ('I', '1'), ('|', '1'),
                (' ', ''), ('\n', ''), ('\t', '')
            ]
            for viejo, nuevo in correcciones:
                texto_corregido = texto_corregido.replace(viejo, nuevo)
            
            # Buscar códigos en esta página (solo si no están ya mapeados)
            for codigo in codigos:
                if codigo not in codigo_a_pagina and codigo in texto_corregido:
                    codigo_a_pagina[codigo] = page_num
                    print(f"   ✅ {codigo} encontrado en página {page_num}")
                    break  # Pasar a la siguiente página
        
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
        mapeo = {
            'P': 'PROTOCOLO',
            'D': 'DILIGENCIA',
            'C': 'CERTIFICACIONES',
            'O': 'OTROS',
            'A': 'ARRIENDOS'
        }
        return mapeo.get(tipo, 'OTROS')