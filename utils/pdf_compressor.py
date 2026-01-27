"""
Compresor de PDFs
Reduce el tamaño de archivos PDF optimizando imágenes
"""

import fitz  # PyMuPDF
import os
from PIL import Image
import io

class PDFCompressor:
    """Comprime PDFs reduciendo tamaño de imágenes"""
    
    def __init__(self):
        self.compression_levels = {
            'low': 95,      # Calidad alta, compresión baja (~10-20% reducción)
            'medium': 75,   # Balance (~30-50% reducción)
            'high': 50,     # Calidad media, compresión alta (~50-70% reducción)
            'maximum': 25   # Máxima compresión (~70-85% reducción)
        }
    
    def get_file_size_mb(self, file_path):
        """Obtiene el tamaño del archivo en MB"""
        size_bytes = os.path.getsize(file_path)
        return size_bytes / (1024 * 1024)
    
    def comprimir_pdf(self, input_path, output_path=None, level='medium'):
        """
        Comprime un PDF optimizando imágenes
        
        Args:
            input_path: Ruta del PDF original
            output_path: Ruta del PDF comprimido (opcional)
            level: Nivel de compresión ('low', 'medium', 'high', 'maximum')
        
        Returns:
            dict con información de compresión
        """
        if output_path is None:
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_compressed{ext}"
        
        quality = self.compression_levels.get(level, 75)
        
        print(f"\n📦 Comprimiendo PDF...")
        print(f"   Nivel: {level} (calidad JPEG: {quality})")
        
        # Abrir PDF original
        doc = fitz.open(input_path)
        original_size = self.get_file_size_mb(input_path)
        
        # Crear nuevo PDF
        writer = fitz.open()
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Obtener lista de imágenes en la página
            image_list = page.get_images()
            
            if image_list:
                print(f"   Página {page_num + 1}: {len(image_list)} imagen(es)")
                
                # Procesar cada imagen
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    
                    try:
                        # Extraer imagen
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        
                        # Abrir con PIL
                        img_pil = Image.open(io.BytesIO(image_bytes))
                        
                        # Convertir a RGB si es necesario
                        if img_pil.mode not in ('RGB', 'L'):
                            img_pil = img_pil.convert('RGB')
                        
                        # Comprimir imagen
                        output_buffer = io.BytesIO()
                        img_pil.save(
                            output_buffer, 
                            format='JPEG', 
                            quality=quality, 
                            optimize=True
                        )
                        compressed_bytes = output_buffer.getvalue()
                        
                        # Calcular reducción de esta imagen
                        original_img_size = len(image_bytes)
                        compressed_img_size = len(compressed_bytes)
                        reduction = ((original_img_size - compressed_img_size) / original_img_size) * 100
                        
                        if reduction > 0:
                            # Reemplazar imagen en el documento
                            # Crear un nuevo rectángulo de imagen
                            pix = fitz.Pixmap(compressed_bytes)
                            
                            # Obtener el rectángulo de la imagen original
                            img_rects = page.get_image_rects(xref)
                            if img_rects:
                                rect = img_rects[0]
                                # Insertar imagen comprimida
                                page.insert_image(rect, pixmap=pix)
                    
                    except Exception as e:
                        print(f"      ⚠️  Error procesando imagen {img_index}: {e}")
                        continue
            
            # Agregar página al nuevo documento
            writer.insert_pdf(doc, from_page=page_num, to_page=page_num)
        
        # Guardar con opciones de compresión adicionales
        writer.save(
            output_path,
            garbage=4,      # Máxima limpieza de objetos no usados
            deflate=True,   # Comprimir streams
            clean=True      # Limpiar sintaxis
        )
        
        writer.close()
        doc.close()
        
        # Calcular estadísticas
        compressed_size = self.get_file_size_mb(output_path)
        reduction_percent = ((original_size - compressed_size) / original_size) * 100
        
        result = {
            'original_size_mb': round(original_size, 2),
            'compressed_size_mb': round(compressed_size, 2),
            'reduction_mb': round(original_size - compressed_size, 2),
            'reduction_percent': round(reduction_percent, 2),
            'output_path': output_path,
            'level': level,
            'quality': quality
        }
        
        print(f"\n✅ Compresión completada:")
        print(f"   Original: {result['original_size_mb']} MB")
        print(f"   Comprimido: {result['compressed_size_mb']} MB")
        print(f"   Reducción: {result['reduction_percent']}% ({result['reduction_mb']} MB)")
        
        return result
    
    def comprimir_pdf_simple(self, input_path, output_path=None, level='medium'):
        """
        Versión simplificada de compresión usando solo opciones de guardado
        Más rápida pero menos efectiva
        """
        if output_path is None:
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_compressed{ext}"
        
        doc = fitz.open(input_path)
        original_size = self.get_file_size_mb(input_path)
        
        # Guardar con compresión
        doc.save(
            output_path,
            garbage=4,
            deflate=True,
            clean=True,
            linear=True  # Optimizar para web
        )
        
        doc.close()
        
        compressed_size = self.get_file_size_mb(output_path)
        reduction_percent = ((original_size - compressed_size) / original_size) * 100
        
        return {
            'original_size_mb': round(original_size, 2),
            'compressed_size_mb': round(compressed_size, 2),
            'reduction_mb': round(original_size - compressed_size, 2),
            'reduction_percent': round(reduction_percent, 2),
            'output_path': output_path,
            'level': level
        }

if __name__ == '__main__':
    # Prueba del compresor
    compressor = PDFCompressor()
    
    # Ejemplo de uso
    # result = compressor.comprimir_pdf('documento.pdf', level='medium')
    # print(result)
