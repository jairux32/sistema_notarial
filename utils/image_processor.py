"""
Procesador de Imágenes para Escaneo
Ajusta brillo, contraste, detecta bordes y recorta automáticamente
"""

from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import os

class ImageProcessor:
    """Procesa y mejora imágenes escaneadas"""
    
    def __init__(self):
        pass
    
    def ajustar_brillo(self, image, factor=1.0):
        """
        Ajusta el brillo de una imagen
        
        Args:
            image: PIL Image
            factor: Factor de brillo (0.5 = más oscuro, 1.0 = normal, 1.5 = más claro)
        
        Returns:
            PIL Image ajustada
        """
        enhancer = ImageEnhance.Brightness(image)
        return enhancer.enhance(factor)
    
    def ajustar_contraste(self, image, factor=1.0):
        """
        Ajusta el contraste de una imagen
        
        Args:
            image: PIL Image
            factor: Factor de contraste (0.5 = menos contraste, 1.0 = normal, 1.5 = más contraste)
        
        Returns:
            PIL Image ajustada
        """
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(factor)
    
    def ajustar_nitidez(self, image, factor=1.0):
        """
        Ajusta la nitidez de una imagen
        
        Args:
            image: PIL Image
            factor: Factor de nitidez (0.5 = más suave, 1.0 = normal, 2.0 = más nítido)
        
        Returns:
            PIL Image ajustada
        """
        enhancer = ImageEnhance.Sharpness(image)
        return enhancer.enhance(factor)
    
    def detectar_y_recortar_bordes(self, image, threshold=240, margin=10):
        """
        Detecta los bordes del documento y recorta automáticamente
        
        Args:
            image: PIL Image
            threshold: Umbral para detectar contenido (0-255)
            margin: Margen adicional en píxeles
        
        Returns:
            PIL Image recortada
        """
        # Convertir a escala de grises
        gray = image.convert('L')
        img_array = np.array(gray)
        
        # Detectar contenido (píxeles más oscuros que el umbral)
        content = img_array < threshold
        
        # Encontrar límites del contenido
        rows = np.any(content, axis=1)
        cols = np.any(content, axis=0)
        
        if rows.any() and cols.any():
            ymin, ymax = np.where(rows)[0][[0, -1]]
            xmin, xmax = np.where(cols)[0][[0, -1]]
            
            # Aplicar margen
            height, width = img_array.shape
            ymin = max(0, ymin - margin)
            ymax = min(height, ymax + margin)
            xmin = max(0, xmin - margin)
            xmax = min(width, xmax + margin)
            
            # Recortar imagen original
            return image.crop((xmin, ymin, xmax, ymax))
        
        # Si no se detecta contenido, devolver original
        return image
    
    def enderezar_imagen(self, image, angle=0):
        """
        Rota la imagen para enderezarla
        
        Args:
            image: PIL Image
            angle: Ángulo de rotación en grados
        
        Returns:
            PIL Image rotada
        """
        return image.rotate(angle, expand=True, fillcolor='white')
    
    def aplicar_filtro_bordes(self, image):
        """
        Aplica un filtro de detección de bordes
        
        Args:
            image: PIL Image
        
        Returns:
            PIL Image con bordes detectados
        """
        return image.filter(ImageFilter.FIND_EDGES)
    
    def mejorar_documento(self, image, auto_crop=True, brightness=1.0, 
                         contrast=1.0, sharpness=1.0):
        """
        Mejora automática de documento escaneado
        
        Args:
            image: PIL Image
            auto_crop: Recortar automáticamente
            brightness: Factor de brillo
            contrast: Factor de contraste
            sharpness: Factor de nitidez
        
        Returns:
            PIL Image mejorada
        """
        # Recortar automáticamente si está habilitado
        if auto_crop:
            image = self.detectar_y_recortar_bordes(image)
        
        # Ajustar brillo
        if brightness != 1.0:
            image = self.ajustar_brillo(image, brightness)
        
        # Ajustar contraste
        if contrast != 1.0:
            image = self.ajustar_contraste(image, contrast)
        
        # Ajustar nitidez
        if sharpness != 1.0:
            image = self.ajustar_nitidez(image, sharpness)
        
        return image
    
    def procesar_archivo(self, input_path, output_path=None, **kwargs):
        """
        Procesa un archivo de imagen
        
        Args:
            input_path: Ruta del archivo de entrada
            output_path: Ruta del archivo de salida (opcional)
            **kwargs: Parámetros para mejorar_documento
        
        Returns:
            Ruta del archivo procesado
        """
        if output_path is None:
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_processed{ext}"
        
        # Abrir imagen
        image = Image.open(input_path)
        
        # Procesar
        processed = self.mejorar_documento(image, **kwargs)
        
        # Guardar
        processed.save(output_path)
        
        return output_path
    
    def procesar_pdf_paginas(self, pdf_path, output_dir=None, **kwargs):
        """
        Procesa todas las páginas de un PDF
        
        Args:
            pdf_path: Ruta del PDF
            output_dir: Directorio de salida (opcional)
            **kwargs: Parámetros para mejorar_documento
        
        Returns:
            Lista de rutas de imágenes procesadas
        """
        import fitz  # PyMuPDF
        
        if output_dir is None:
            output_dir = os.path.dirname(pdf_path)
        
        os.makedirs(output_dir, exist_ok=True)
        
        doc = fitz.open(pdf_path)
        processed_images = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Renderizar página como imagen
            pix = page.get_pixmap(dpi=300)
            img_data = pix.tobytes("png")
            
            # Convertir a PIL Image
            from io import BytesIO
            image = Image.open(BytesIO(img_data))
            
            # Procesar
            processed = self.mejorar_documento(image, **kwargs)
            
            # Guardar
            output_path = os.path.join(output_dir, f"page_{page_num + 1}_processed.png")
            processed.save(output_path)
            processed_images.append(output_path)
        
        doc.close()
        
        return processed_images

if __name__ == '__main__':
    # Prueba del procesador
    processor = ImageProcessor()
    
    # Ejemplo de uso
    # processor.procesar_archivo('scan.tiff', brightness=1.2, contrast=1.1, auto_crop=True)
