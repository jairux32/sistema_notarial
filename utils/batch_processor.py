import os
import fitz  # PyMuPDF
from PIL import Image
from datetime import datetime
from utils.ocr_processor import ProcesadorOCR
from utils.pdf_splitter import PDFSplitter
from utils.validator import ValidadorNotarial

class BatchProcessor:
    """Procesador de lotes de documentos escaneados"""
    
    def __init__(self):
        self.ocr = ProcesadorOCR()
        self.splitter = PDFSplitter()
        self.validator = ValidadorNotarial()
    
    def procesar_lote(self, archivos, año, tipo):
        """Procesa múltiples archivos escaneados
        
        Args:
            archivos: Lista de rutas de archivos PDF
            año: Año de los documentos
            tipo: Tipo de libro (A, P, D, etc.)
        
        Returns:
            Lista de resultados con códigos detectados
        """
        resultados = []
        
        print(f"\n📄 Procesando lote de {len(archivos)} archivo(s)...")
        
        for i, archivo in enumerate(archivos, 1):
            print(f"\n[{i}/{len(archivos)}] Procesando: {os.path.basename(archivo)}")
            
            try:
                # Extraer texto con método híbrido
                texto = self.ocr.extraer_texto(archivo)
                
                # Buscar códigos notariales
                codigos = self.ocr.buscar_codigos_notariales(texto, año, tipo)
                
                # Validar secuenciales
                validacion = self.validator.validar_secuenciales(codigos)
                
                # Generar vista previa (primera página)
                preview_path = self.generar_preview(archivo)
                
                resultado = {
                    'archivo': archivo,
                    'nombre': os.path.basename(archivo),
                    'codigos': codigos,
                    'total_codigos': len(codigos),
                    'validacion': validacion,
                    'preview': preview_path,
                    'estado': 'listo',
                    'caracteres_extraidos': len(texto)
                }
                
                print(f"✅ Códigos detectados: {len(codigos)}")
                if validacion.get('faltantes'):
                    print(f"⚠️  Códigos faltantes: {len(validacion['faltantes'])}")
                
                resultados.append(resultado)
                
            except Exception as e:
                print(f"❌ Error procesando {archivo}: {str(e)}")
                resultados.append({
                    'archivo': archivo,
                    'nombre': os.path.basename(archivo),
                    'estado': 'error',
                    'error': str(e)
                })
        
        return resultados
    
    def generar_preview(self, pdf_path, output_dir='scanned_preview/'):
        """Genera vista previa (miniatura) de la primera página del PDF
        
        Args:
            pdf_path: Ruta del PDF
            output_dir: Directorio para guardar preview
        
        Returns:
            Ruta de la imagen de preview
        """
        try:
            # Crear directorio si no existe
            os.makedirs(output_dir, exist_ok=True)
            
            # Abrir PDF
            pdf = fitz.open(pdf_path)
            
            # Obtener primera página
            page = pdf[0]
            
            # Convertir a imagen (resolución media para preview)
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            
            # Nombre del archivo de preview
            nombre_base = os.path.splitext(os.path.basename(pdf_path))[0]
            preview_filename = f"preview_{nombre_base}.png"
            preview_path = os.path.join(output_dir, preview_filename)
            
            # Guardar imagen
            pix.save(preview_path)
            
            pdf.close()
            
            return preview_path
            
        except Exception as e:
            print(f"⚠️  Error generando preview: {str(e)}")
            return None
    
    def dividir_y_guardar(self, archivo, codigos, año, tipo, base_output_dir='escaneo_separado/'):
        """Divide PDF por códigos y guarda en carpeta de escaneo separado
        
        Args:
            archivo: Ruta del PDF a dividir
            codigos: Lista de códigos detectados
            año: Año de los documentos
            tipo: Tipo de libro
            base_output_dir: Directorio base de salida
        
        Returns:
            Lista de archivos generados
        """
        print(f"\n📄 Dividiendo PDF: {os.path.basename(archivo)}")
        print(f"📋 Códigos a procesar: {len(codigos)}")
        
        # Usar el splitter existente
        archivos_generados = self.splitter.dividir_por_codigos(
            archivo, codigos, año, tipo, base_output_dir
        )
        
        print(f"✅ Archivos generados: {len(archivos_generados)}")
        
        return archivos_generados
    
    def dividir_con_codigos_manuales(self, archivo, codigos, codigos_manuales, año, tipo, base_output_dir='escaneo_separado/'):
        """Divide PDF incluyendo códigos agregados manualmente
        
        Args:
            archivo: Ruta del PDF
            codigos: Lista de códigos detectados automáticamente
            codigos_manuales: Lista de tuplas (codigo, pagina_inicio)
            año: Año
            tipo: Tipo de libro
            base_output_dir: Directorio base de salida
        
        Returns:
            Lista de archivos generados
        """
        print(f"\n📄 Dividiendo PDF con códigos manuales: {os.path.basename(archivo)}")
        print(f"📋 Códigos automáticos: {len(codigos)}")
        print(f"🔧 Códigos manuales: {len(codigos_manuales)}")
        
        # Combinar códigos
        todos_codigos = codigos + [c[0] for c in codigos_manuales]
        
        # Usar el splitter con códigos manuales
        archivos_generados = self.splitter.dividir_por_codigos_con_manual(
            archivo, todos_codigos, codigos_manuales, año, tipo, base_output_dir
        )
        
        print(f"✅ Archivos generados: {len(archivos_generados)}")
        
        return archivos_generados
