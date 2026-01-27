#!/usr/bin/env python3
"""
Servicio de Escaneo Multiplataforma
Controla escáneres en Windows, Linux y Mac
Puerto: 5001
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import platform
import subprocess
import os
from datetime import datetime
import logging

app = Flask(__name__)
CORS(app)  # Permitir peticiones desde localhost:5000

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ScannerServiceMultiplatform:
    """Servicio de escaneo que funciona en Windows, Linux y Mac"""
    
    def __init__(self):
        self.os_type = platform.system()
        logger.info(f"🖨️  Servicio iniciado en {self.os_type}")
    
    def escanear_windows(self, output_path, resolution=300, mode='Color'):
        """Escaneo en Windows usando scanimage o WIA"""
        try:
            logger.info(f"Escaneando en Windows: {output_path}")
            
            # Opción 1: Usar scanimage si está instalado (NAPS2, etc.)
            try:
                cmd = [
                    'scanimage',
                    f'--resolution={resolution}',
                    '--format=tiff',
                    f'--output-file={output_path}'
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0 and os.path.exists(output_path):
                    logger.info("✅ Escaneo exitoso con scanimage")
                    return True
            except FileNotFoundError:
                logger.warning("scanimage no encontrado, intentando con PowerShell...")
            
            # Opción 2: PowerShell con WIA (Windows nativo)
            ps_script = f'''
            try {{
                $deviceManager = New-Object -ComObject WIA.DeviceManager
                if ($deviceManager.DeviceInfos.Count -eq 0) {{
                    Write-Error "No se encontraron escáneres"
                    exit 1
                }}
                
                $device = $deviceManager.DeviceInfos.Item(1).Connect()
                $item = $device.Items.Item(1)
                
                # Configurar resolución
                $item.Properties("6147").Value = {resolution}
                $item.Properties("6148").Value = {resolution}
                
                # Escanear
                $image = $item.Transfer()
                
                # Guardar
                $image.SaveFile("{output_path}")
                
                Write-Output "Escaneo exitoso"
                exit 0
            }} catch {{
                Write-Error $_.Exception.Message
                exit 1
            }}
            '''
            
            result = subprocess.run(
                ['powershell', '-Command', ps_script],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info("✅ Escaneo exitoso con PowerShell/WIA")
                return True
            else:
                logger.error(f"Error PowerShell: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Timeout en escaneo")
            return False
        except Exception as e:
            logger.error(f"Error Windows: {e}")
            return False
    
    def escanear_linux(self, output_path, resolution=300, mode='Color'):
        """Escaneo en Linux usando SANE (scanimage)"""
        try:
            logger.info(f"Escaneando en Linux: {output_path}")
            
            # Usar scanimage (SANE)
            cmd = [
                'scanimage',
                f'--resolution={resolution}',
                '--format=tiff',
                f'--mode={mode}',
                f'--output-file={output_path}'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info("✅ Escaneo exitoso")
                return True
            else:
                logger.error(f"Error scanimage: {result.stderr}")
                return False
                
        except FileNotFoundError:
            logger.error("scanimage no encontrado. Instala SANE: sudo apt-get install sane sane-utils")
            return False
        except subprocess.TimeoutExpired:
            logger.error("Timeout en escaneo")
            return False
        except Exception as e:
            logger.error(f"Error Linux: {e}")
            return False
    
    def escanear_mac(self, output_path, resolution=300, mode='Color'):
        """Escaneo en Mac usando scanline o imagesnap"""
        try:
            logger.info(f"Escaneando en Mac: {output_path}")
            
            # Opción 1: scanline (más común)
            try:
                cmd = ['scanline', 'scan', '--output', output_path]
                result = subprocess.run(cmd, capture_output=True, timeout=60)
                
                if result.returncode == 0 and os.path.exists(output_path):
                    logger.info("✅ Escaneo exitoso con scanline")
                    return True
            except FileNotFoundError:
                logger.warning("scanline no encontrado")
            
            # Opción 2: Usar sane si está instalado (Homebrew)
            try:
                cmd = [
                    'scanimage',
                    f'--resolution={resolution}',
                    '--format=tiff',
                    f'--output-file={output_path}'
                ]
                result = subprocess.run(cmd, capture_output=True, timeout=60)
                
                if result.returncode == 0 and os.path.exists(output_path):
                    logger.info("✅ Escaneo exitoso con scanimage")
                    return True
            except FileNotFoundError:
                pass
            
            logger.error("No se encontró software de escaneo. Instala scanline o SANE")
            return False
            
        except subprocess.TimeoutExpired:
            logger.error("Timeout en escaneo")
            return False
        except Exception as e:
            logger.error(f"Error Mac: {e}")
            return False
    
    def escanear(self, output_path, resolution=300, mode='Color'):
        """Escanea según el sistema operativo"""
        # Asegurar que el directorio existe
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        if self.os_type == 'Windows':
            return self.escanear_windows(output_path, resolution, mode)
        elif self.os_type == 'Linux':
            return self.escanear_linux(output_path, resolution, mode)
        elif self.os_type == 'Darwin':  # Mac
            return self.escanear_mac(output_path, resolution, mode)
        else:
            raise Exception(f"Sistema operativo no soportado: {self.os_type}")
    
    def convertir_a_pdf(self, tiff_path, pdf_path):
        """Convierte TIFF a PDF"""
        try:
            from PIL import Image
            
            img = Image.open(tiff_path)
            img.save(pdf_path, 'PDF', resolution=100.0)
            
            # Eliminar TIFF temporal
            if os.path.exists(tiff_path):
                os.remove(tiff_path)
            
            return True
        except Exception as e:
            logger.error(f"Error convirtiendo a PDF: {e}")
            return False
    
    def combinar_paginas_pdf(self, tiff_files, output_pdf):
        """Combina múltiples TIFFs en un solo PDF"""
        try:
            from PIL import Image
            
            images = []
            for tiff_file in tiff_files:
                if os.path.exists(tiff_file):
                    img = Image.open(tiff_file)
                    # Convertir a RGB si es necesario
                    if img.mode not in ('RGB', 'L'):
                        img = img.convert('RGB')
                    images.append(img)
            
            if images:
                # Guardar primer imagen con las demás como páginas adicionales
                images[0].save(
                    output_pdf, 
                    'PDF', 
                    resolution=100.0,
                    save_all=True,
                    append_images=images[1:] if len(images) > 1 else []
                )
                logger.info(f"✅ PDF combinado creado: {len(images)} páginas")
                return True
            return False
        except Exception as e:
            logger.error(f"Error combinando PDFs: {e}")
            return False
    
    def escanear_multipagina(self, output_dir='scanned/', resolution=300, 
                            mode='Color', duplex=False, max_pages=100):
        """Escanea múltiples páginas usando ADF (Alimentador Automático de Documentos)"""
        paginas = []
        pagina_num = 1
        
        logger.info(f"\n📄 Iniciando escaneo multipágina (duplex={duplex}, max={max_pages})...")
        
        # Asegurar que el directorio existe
        os.makedirs(output_dir, exist_ok=True)
        
        while pagina_num <= max_pages:
            try:
                logger.info(f"   Escaneando página {pagina_num}...")
                
                temp_file = os.path.join('/tmp' if self.os_type != 'Windows' else output_dir, 
                                        f'scan_page_{pagina_num}.tiff')
                
                if self.os_type == 'Linux':
                    # SANE con ADF
                    cmd = [
                        'scanimage',
                        f'--resolution={resolution}',
                        '--format=tiff',
                        f'--mode={mode}',
                        '--source=ADF',  # Alimentador automático
                        f'--output-file={temp_file}'
                    ]
                    
                    # Agregar duplex si está soportado
                    if duplex:
                        cmd.append('--adf-mode=Duplex')
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    
                    if result.returncode == 0 and os.path.exists(temp_file):
                        paginas.append(temp_file)
                        pagina_num += 1
                    else:
                        # No hay más páginas o error
                        if "out of documents" in result.stderr.lower() or "feeder empty" in result.stderr.lower():
                            logger.info(f"✅ Alimentador vacío. Total páginas: {len(paginas)}")
                        else:
                            logger.warning(f"Fin de escaneo: {result.stderr}")
                        break
                        
                elif self.os_type == 'Windows':
                    # WIA con ADF - escaneo página por página
                    ps_script = f'''
                    try {{
                        $deviceManager = New-Object -ComObject WIA.DeviceManager
                        if ($deviceManager.DeviceInfos.Count -eq 0) {{
                            Write-Error "No se encontraron escáneres"
                            exit 1
                        }}
                        
                        $device = $deviceManager.DeviceInfos.Item(1).Connect()
                        $item = $device.Items.Item(1)
                        
                        # Configurar para ADF
                        $item.Properties("3088").Value = 1  # Usar ADF
                        $item.Properties("6147").Value = {resolution}
                        $item.Properties("6148").Value = {resolution}
                        
                        # Escanear
                        $image = $item.Transfer()
                        $image.SaveFile("{temp_file}")
                        
                        Write-Output "Página escaneada"
                        exit 0
                    }} catch {{
                        Write-Error $_.Exception.Message
                        exit 1
                    }}
                    '''
                    
                    result = subprocess.run(
                        ['powershell', '-Command', ps_script],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if result.returncode == 0 and os.path.exists(temp_file):
                        paginas.append(temp_file)
                        pagina_num += 1
                    else:
                        logger.info(f"✅ Fin de escaneo. Total páginas: {len(paginas)}")
                        break
                
                elif self.os_type == 'Darwin':  # Mac
                    # Usar SANE si está disponible
                    cmd = [
                        'scanimage',
                        f'--resolution={resolution}',
                        '--format=tiff',
                        '--source=ADF',
                        f'--output-file={temp_file}'
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, timeout=30)
                    
                    if result.returncode == 0 and os.path.exists(temp_file):
                        paginas.append(temp_file)
                        pagina_num += 1
                    else:
                        break
                    
            except subprocess.TimeoutExpired:
                logger.warning(f"⚠️  Timeout en página {pagina_num}")
                break
            except Exception as e:
                error_msg = str(e).lower()
                if "out of documents" in error_msg or "feeder empty" in error_msg or "no documents" in error_msg:
                    logger.info(f"✅ Escaneo completado: {len(paginas)} página(s)")
                    break
                else:
                    logger.error(f"❌ Error en página {pagina_num}: {e}")
                    break
        
        if paginas:
            # Combinar todas las páginas en un solo PDF
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = os.path.join(output_dir, f'scan_multi_{timestamp}.pdf')
            
            if self.combinar_paginas_pdf(paginas, output_path):
                # Limpiar archivos temporales
                for temp_file in paginas:
                    if os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                
                logger.info(f"💾 Guardado: {output_path} ({len(paginas)} páginas)")
                return output_path
            else:
                logger.error("Error al combinar páginas")
                return None
        else:
            logger.warning("No se escanearon páginas")
            return None

# Instancia global del servicio
scanner_service = ScannerServiceMultiplatform()

@app.route('/scan', methods=['POST'])
def scan():
    """Endpoint para escanear documento"""
    try:
        data = request.json or {}
        resolution = int(data.get('resolution', 300))
        mode = data.get('mode', 'Color')
        output_dir = data.get('output_dir', 'scanned')
        
        logger.info(f"📥 Petición de escaneo: {resolution}dpi, {mode}")
        
        # Crear nombre de archivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_path = os.path.join(output_dir, f'scan_{timestamp}.tiff')
        output_path = os.path.join(output_dir, f'scan_{timestamp}.pdf')
        
        # Escanear
        success = scanner_service.escanear(temp_path, resolution, mode)
        
        if success:
            # Convertir a PDF
            if scanner_service.convertir_a_pdf(temp_path, output_path):
                logger.info(f"✅ Escaneo completado: {output_path}")
                return jsonify({
                    'success': True,
                    'archivo': output_path,
                    'mensaje': 'Documento escaneado exitosamente'
                })
            else:
                # Si falla conversión, usar TIFF
                logger.warning("No se pudo convertir a PDF, usando TIFF")
                return jsonify({
                    'success': True,
                    'archivo': temp_path,
                    'mensaje': 'Documento escaneado (formato TIFF)'
                })
        else:
            return jsonify({
                'success': False,
                'error': 'Error al escanear el documento'
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/status', methods=['GET'])
def status():
    """Estado del servicio"""
    return jsonify({
        'status': 'running',
        'os': scanner_service.os_type,
        'version': '1.0.0'
    })

@app.route('/scan_with_ocr', methods=['POST'])
def scan_with_ocr():
    """Escanea documento y ejecuta OCR inmediatamente"""
    try:
        data = request.json or {}
        resolution = int(data.get('resolution', 300))
        mode = data.get('mode', 'Color')
        output_dir = data.get('output_dir', 'scanned')
        año = data.get('año')
        tipo = data.get('tipo')
        
        logger.info(f"📥 Petición de escaneo con OCR: {resolution}dpi, {mode}, {año}-{tipo}")
        
        # Crear nombre de archivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_path = os.path.join(output_dir, f'scan_{timestamp}.tiff')
        output_path = os.path.join(output_dir, f'scan_{timestamp}.pdf')
        
        # Escanear
        success = scanner_service.escanear(temp_path, resolution, mode)
        
        if success:
            # Convertir a PDF
            if scanner_service.convertir_a_pdf(temp_path, output_path):
                logger.info(f"✅ Escaneo completado: {output_path}")
                
                # Ejecutar OCR inmediatamente
                try:
                    # Importar módulos de OCR del sistema principal
                    import sys
                    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                    
                    from utils.ocr_processor import ProcesadorOCR
                    
                    logger.info("🔍 Ejecutando OCR...")
                    ocr = ProcesadorOCR()
                    texto = ocr.extraer_texto(output_path)
                    codigos = ocr.buscar_codigos_notariales(texto, año, tipo)
                    
                    logger.info(f"✅ OCR completado: {len(codigos)} códigos detectados")
                    
                    return jsonify({
                        'success': True,
                        'archivo': output_path,
                        'codigos': codigos,
                        'total_codigos': len(codigos),
                        'caracteres_extraidos': len(texto),
                        'mensaje': f'Documento escaneado. {len(codigos)} códigos detectados.'
                    })
                    
                except ImportError as e:
                    logger.warning(f"No se pudo importar OCR: {e}")
                    # Retornar sin OCR
                    return jsonify({
                        'success': True,
                        'archivo': output_path,
                        'mensaje': 'Documento escaneado exitosamente (OCR no disponible)',
                        'ocr_available': False
                    })
                except Exception as e:
                    logger.error(f"Error en OCR: {e}")
                    # Retornar sin OCR pero con éxito en escaneo
                    return jsonify({
                        'success': True,
                        'archivo': output_path,
                        'mensaje': f'Documento escaneado. Error en OCR: {str(e)}',
                        'ocr_error': str(e)
                    })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Error al convertir a PDF'
                }), 500
        else:
            return jsonify({
                'success': False,
                'error': 'Error al escanear el documento'
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/scan_multiple', methods=['POST'])
def scan_multiple():
    """Escanea múltiples páginas con ADF"""
    try:
        data = request.json or {}
        resolution = int(data.get('resolution', 300))
        mode = data.get('mode', 'Color')
        duplex = data.get('duplex', False)
        max_pages = int(data.get('max_pages', 100))
        output_dir = data.get('output_dir', 'scanned')
        
        logger.info(f"📥 Petición de escaneo multipágina: {resolution}dpi, {mode}, duplex={duplex}, max={max_pages}")
        
        # Escanear múltiples páginas
        output_path = scanner_service.escanear_multipagina(
            output_dir=output_dir,
            resolution=resolution,
            mode=mode,
            duplex=duplex,
            max_pages=max_pages
        )
        
        if output_path:
            # Contar páginas del PDF
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(output_path)
                num_pages = len(doc)
                doc.close()
            except:
                num_pages = 0
            
            logger.info(f"✅ Escaneo multipágina completado: {output_path}")
            return jsonify({
                'success': True,
                'archivo': output_path,
                'num_paginas': num_pages,
                'mensaje': f'Documento escaneado exitosamente ({num_pages} páginas)'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudieron escanear páginas'
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/test', methods=['GET'])
def test():
    """Endpoint de prueba"""
    return jsonify({
        'message': 'Servicio de escaneo funcionando correctamente',
        'os': scanner_service.os_type
    })

@app.route('/scan_multiple_with_ocr', methods=['POST'])
def scan_multiple_with_ocr():
    """Escanea múltiples páginas con ADF y ejecuta OCR automáticamente"""
    try:
        data = request.json or {}
        resolution = int(data.get('resolution', 300))
        mode = data.get('mode', 'Color')
        duplex = data.get('duplex', False)
        max_pages = int(data.get('max_pages', 100))
        output_dir = data.get('output_dir', 'scanned')
        año = data.get('año')
        tipo = data.get('tipo')
        
        logger.info(f"📥 Petición de escaneo multipágina + OCR: {resolution}dpi, {mode}, duplex={duplex}, max={max_pages}")
        
        # Escanear múltiples páginas
        output_path = scanner_service.escanear_multipagina(
            output_dir=output_dir,
            resolution=resolution,
            mode=mode,
            duplex=duplex,
            max_pages=max_pages
        )
        
        if output_path:
            # Contar páginas del PDF
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(output_path)
                num_pages = len(doc)
                doc.close()
            except:
                num_pages = 0
            
            logger.info(f"✅ Escaneo multipágina completado: {output_path} ({num_pages} páginas)")
            
            # Ejecutar OCR sobre el PDF completo
            try:
                import sys
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from utils.ocr_processor import ProcesadorOCR
                
                logger.info("🔍 Ejecutando OCR sobre documento multipágina...")
                ocr = ProcesadorOCR()
                texto = ocr.extraer_texto(output_path)
                codigos = ocr.buscar_codigos_notariales(texto, año, tipo)
                
                logger.info(f"✅ OCR completado: {len(codigos)} códigos detectados en {num_pages} páginas")
                
                return jsonify({
                    'success': True,
                    'archivo': output_path,
                    'num_paginas': num_pages,
                    'codigos': codigos,
                    'total_codigos': len(codigos),
                    'caracteres_extraidos': len(texto),
                    'mensaje': f'Documento multipágina escaneado. {len(codigos)} códigos detectados en {num_pages} páginas.'
                })
                
            except ImportError as e:
                logger.warning(f"No se pudo importar OCR: {e}")
                # Retornar sin OCR
                return jsonify({
                    'success': True,
                    'archivo': output_path,
                    'num_paginas': num_pages,
                    'mensaje': f'Documento multipágina escaneado ({num_pages} páginas). OCR no disponible.',
                    'ocr_available': False
                })
            except Exception as e:
                logger.error(f"Error en OCR: {e}")
                # Retornar sin OCR pero con éxito en escaneo
                return jsonify({
                    'success': True,
                    'archivo': output_path,
                    'num_paginas': num_pages,
                    'mensaje': f'Documento multipágina escaneado ({num_pages} páginas). Error en OCR: {str(e)}',
                    'ocr_error': str(e)
                })
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudieron escanear páginas'
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/process_image', methods=['POST'])
def process_image():
    """Procesa una imagen con ajustes de brillo, contraste, etc."""
    try:
        data = request.json or {}
        input_file = data.get('input_file')
        brightness = float(data.get('brightness', 1.0))
        contrast = float(data.get('contrast', 1.0))
        sharpness = float(data.get('sharpness', 1.0))
        auto_crop = data.get('auto_crop', False)
        output_file = data.get('output_file')
        
        if not input_file or not os.path.exists(input_file):
            return jsonify({
                'success': False,
                'error': 'Archivo no encontrado'
            }), 404
        
        logger.info(f"⚙️ Petición de procesamiento: {input_file}")
        logger.info(f"   Brillo: {brightness}, Contraste: {contrast}, Nitidez: {sharpness}, Recorte: {auto_crop}")
        
        # Importar procesador
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from utils.image_processor import ImageProcessor
        
        processor = ImageProcessor()
        processed_path = processor.procesar_archivo(
            input_path=input_file,
            output_path=output_file,
            brightness=brightness,
            contrast=contrast,
            sharpness=sharpness,
            auto_crop=auto_crop
        )
        
        logger.info(f"✅ Procesamiento completado: {processed_path}")
        
        return jsonify({
            'success': True,
            'output_file': processed_path,
            'mensaje': 'Imagen procesada exitosamente'
        })
        
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/compress_pdf', methods=['POST'])
def compress_pdf():
    """Comprime un PDF existente"""
    try:
        data = request.json or {}
        input_file = data.get('input_file')
        level = data.get('level', 'medium')  # low, medium, high, maximum
        output_file = data.get('output_file')
        
        if not input_file or not os.path.exists(input_file):
            return jsonify({
                'success': False,
                'error': 'Archivo no encontrado'
            }), 404
        
        logger.info(f"📦 Petición de compresión: {input_file}, nivel={level}")
        
        # Importar compresor
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from utils.pdf_compressor import PDFCompressor
        
        compressor = PDFCompressor()
        result = compressor.comprimir_pdf(
            input_path=input_file,
            output_path=output_file,
            level=level
        )
        
        logger.info(f"✅ Compresión completada: {result['reduction_percent']}% reducido")
        
        return jsonify({
            'success': True,
            'original_size_mb': result['original_size_mb'],
            'compressed_size_mb': result['compressed_size_mb'],
            'reduction_mb': result['reduction_mb'],
            'reduction_percent': result['reduction_percent'],
            'output_file': result['output_path'],
            'level': result['level'],
            'mensaje': f'PDF comprimido exitosamente ({result["reduction_percent"]}% reducido)'
        })
        
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("🖨️  SERVICIO DE ESCANEO MULTIPLATAFORMA")
    print("=" * 60)
    print(f"📡 Sistema operativo: {scanner_service.os_type}")
    print(f"📡 Escuchando en: http://localhost:5001")
    print(f"📡 Endpoints disponibles:")
    print(f"   - POST /scan       (Escanear documento)")
    print(f"   - GET  /status     (Estado del servicio)")
    print(f"   - GET  /test       (Prueba de conexión)")
    print("=" * 60)
    print("✅ Servicio iniciado. Presiona Ctrl+C para detener.")
    print()
    
    app.run(host='localhost', port=5001, debug=False)
