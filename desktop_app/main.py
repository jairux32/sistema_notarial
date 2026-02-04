import flet as ft
import requests
import json
import os

API_URL = "http://localhost:5000/api"
SESSION_FILE = "session.json"

def main(page: ft.Page):
    page.title = "Sistema Notarial - Escáner"
    page.theme_mode = "light"
    page.vertical_alignment = "center"
    page.horizontal_alignment = "center"

    # Estado de la sesión
    user_token = None
    current_user = None

    def load_session():
        nonlocal user_token, current_user
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, "r") as f:
                    data = json.load(f)
                    user_token = data.get("token")
                    current_user = data.get("user")
                    return True
            except:
                return False
        return False

    def save_session(token, user):
        with open(SESSION_FILE, "w") as f:
            json.dump({"token": token, "user": user}, f)

    # UI Elements
    username_field = ft.TextField(label="Usuario", width=300)
    password_field = ft.TextField(label="Contraseña", password=True, can_reveal_password=True, width=300)
    
    def login(e):
        if not username_field.value or not password_field.value:
            username_field.error_text = "Campo requerido" if not username_field.value else None
            password_field.error_text = "Campo requerido" if not password_field.value else None
            page.update()
            return

        login_button.disabled = True
        page.update()

        try:
            print(f"Intentando login en {API_URL}/login...")
            response = requests.post(
                f"{API_URL}/login",
                json={
                    "username": username_field.value,
                    "password": password_field.value
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    token = data.get("token")
                    user = data.get("user")
                    print("Login exitoso")
                    save_session(token, user)
                    show_scanner_ui(user)
                else:
                    page.snack_bar = ft.SnackBar(ft.Text("Credenciales incorrectas"))
                    page.snack_bar.open = True
            else:
                page.snack_bar = ft.SnackBar(ft.Text(f"Error servidor: {response.status_code}"))
                page.snack_bar.open = True
                
        except Exception as ex:
            print(f"Error login: {ex}")
            page.snack_bar = ft.SnackBar(ft.Text(f"Error de conexión: {str(ex)}"))
            page.snack_bar.open = True
        
        login_button.disabled = False
        page.update()

    login_button = ft.ElevatedButton("Iniciar Sesión", on_click=login, width=300)

    def logout(e):
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
        show_login_ui()

    def show_login_ui():
        print("   ➡️ show_login_ui inicio")
        try:
            page.clean()
            page.vertical_alignment = "center"
            
            col = ft.Column(
                [
                    ft.Text("🖨️", size=64), # Emoji safe replacement for Icon
                    ft.Text("Sistema Notarial", size=30, weight="bold"),
                    ft.Text("Módulo de Escaneado", size=16, color="grey"),
                    ft.Container(height=20),
                    username_field,
                    password_field,
                    ft.Container(height=10),
                    login_button
                ],
                alignment="center",
                horizontal_alignment="center"
            )
            
            page.add(col)
            page.update()
            print("   ✅ Login UI updated")
        except Exception as ex:
            print(f"   ❌ ERROR en show_login_ui: {ex}")
            import traceback
            traceback.print_exc()

    # --- Lógica de Escaneo ---
    selected_device = None
    
    # Constante de notaría
    CODIGO_NOTARIA = "1101007"

    def validate_scan(image_path, year, type_code):
        """Valida localmente si la imagen tiene el código de barras esperado"""
        print(f"🔍 Validando OCR local: A={year} T={type_code}")
        try:
            import pytesseract
            from PIL import Image
            import re
            
            # 1. Extraer texto
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img)
            
            # 2. Limpiar texto
            correcciones = [('O', '0'), ('o', '0'), ('l', '1'), ('I', '1')]
            for old, new in correcciones:
                text = text.replace(old, new)
                
            # 3. Validar Regex
            # Patrón: Año + Notaría + Tipo + 5 dígitos
            pattern = rf'{year}{CODIGO_NOTARIA}[{type_code}]\d{{5}}'
            match = re.search(pattern, text)
            
            if match:
                print(f"✅ Código encontrado localmente: {match.group(0)}")
                return True, match.group(0)
            else:
                print(f"⚠️ Código no encontrado. Texto extraído: {text[:50]}...")
                return False, None
                
        except Exception as e:
            print(f"❌ Error en validación local: {e}")
            return False, None # Fallar seguro (dejar pasar o advertir)

    def get_connected_scanners():
        devices = []
        try:
            import sane
            try:
                sane.exit()
            except:
                pass
            sane.init()
            devices = sane.get_devices()
            try:
                sane.exit()
            except:
                pass
        except Exception as e:
            print(f"Error SANE: {e}")
            
        return devices

    # --- Upload Logic ---
    def upload_pdf(user, year, book_type, status_text):
        if not os.path.exists("scan_preview.png"):
             status_text.value = "⚠️ No hay imagen escaneada"
             status_text.color = "red"
             status_text.update()
             return

        status_text.value = "⏳ Procesando y subiendo..."
        status_text.color = "blue"
        status_text.update()

        try:
            # El PDF ya fue generado en el paso de escaneo
            if not os.path.exists("scan_temp.pdf"):
                 # Fallback por si acaso
                 import pytesseract
                 pdf_bytes = pytesseract.image_to_pdf_or_hocr("scan_preview.png", extension='pdf', lang='spa')
                 with open("scan_temp.pdf", "wb") as f:
                     f.write(pdf_bytes)

            pdf_path = "scan_temp.pdf"

            # 2. Subir a API
            with open(pdf_path, 'rb') as f:
                files = {'pdf_file': (f'scan_{year}_{book_type}.pdf', f, 'application/pdf')}
                data = {
                    'username': user.get('username'),
                    'año': year,
                    'tipo_libro': book_type
                }
                response = requests.post(f"{API_URL}/upload_scan", files=files, data=data)
            
            if response.status_code == 200:
                res_json = response.json()
                if res_json.get('success'):
                    status_text.value = "✅ Subida Exitosa: " + res_json.get('message', 'OK')
                    status_text.color = "green"
                else:
                     status_text.value = "❌ Error Backend: " + str(res_json.get('error'))
                     status_text.color = "red"
            else:
                status_text.value = f"❌ Error HTTP {response.status_code}"
                status_text.color = "red"

        except Exception as e:
            status_text.value = f"❌ Error Upload: {str(e)}"
            status_text.color = "red"
            print(f"Upload Error: {e}")
        
        status_text.update()

    def show_scanner_ui(user):
        print("   ➡️ show_scanner_ui inicio")
        try:
            page.clean()
            page.vertical_alignment = "start"

            # Estado del UI
            scan_status = ft.Text("Listo para escanear", color="grey")
            devices = get_connected_scanners()
            
            # Dropdown de dispositivos
            dd_devices = ft.Dropdown(
                label="Seleccionar Escáner",
                options=[ft.dropdown.Option(d[0], f"{d[1]} {d[2]}") for d in devices],
                width=400,
            )
            if devices:
                dd_devices.value = devices[0][0]

            # UI Feedback Elements
            progress_bar = ft.ProgressBar(width=400, color="blue", bgcolor="#eeeeee", visible=False)
            
            dlg_success = ft.AlertDialog(
                title=ft.Text("✅ Proceso Completado"),
                content=ft.Text(""),
                actions=[
                    ft.TextButton("Aceptar", on_click=lambda e: close_dialog(dlg_success))
                ],
            )

            def close_dialog(dlg):
                dlg.open = False
                page.update()

            page.dialog = dlg_success # Set default dialog

            def show_success(message):
                dlg_success.content.value = message
                dlg_success.open = True
                page.update()

            def on_scan_click(e):
                if not dd_devices.value:
                    scan_status.value = "⚠️ Seleccione un escáner"
                    scan_status.color = "red"
                    page.update()
                    return

                # Deshabilitar UI
                scan_status.value = "⏳ Iniciando proceso..."
                scan_status.color = "blue"
                progress_bar.visible = True
                btn_scan.disabled = True
                page.update()

                def run_scan_process():
                    try:
                        import sane
                        # Forzar reinicio de SANE
                        try:
                            sane.exit()
                        except:
                            pass
                        sane.init()
                        
                        dev = sane.open(dd_devices.value)
                        
                        # Configuración básica
                        try:
                            opt = dev.get_options()
                            try:
                                dev.duplex = 'both'
                            except:
                                pass

                            if 'source' in opt:
                                if 'ADF Duplex' in opt['source'].constraint:
                                    dev.source = 'ADF Duplex'
                                else:
                                    dev.source = 'ADF'

                            dev.mode = 'Color'
                            dev.resolution = 300
                        except:
                            pass 

                        # Escaneo Multi-página
                        images = []
                        try:
                            print("   🎬 Iniciando multi_scan()...")
                            scan_status.value = "⏳ Alimentando hojas... (Esto puede tardar)"
                            page.update()
                            
                            iter = dev.multi_scan()
                            page_count = 0
                            while True:
                                try:
                                    print(f"   📸 Esperando página {page_count + 1}...")
                                    img = next(iter)
                                    print(f"   ✅ Página {page_count + 1} capturada.")
                                    images.append(img)
                                    page_count += 1
                                    scan_status.value = f"📄 Escaneando página {page_count}..."
                                    page.update()
                                except StopIteration:
                                    print("   🏁 Fin de documentos (StopIteration).")
                                    break
                                except Exception as e_next:
                                    print(f"   ❌ Error al obtener siguiente página: {e_next}")
                                    break
                        except Exception as e:
                            print(f"   ⚠️ Fallo crítico en multi_scan: {e}")
                            try:
                                dev.start()
                                images.append(dev.snap())
                            except:
                                pass

                        dev.close()

                        if not images:
                            raise Exception("No se obtuvieron imágenes")
                        
                        # Guardar Preview (Primera página)
                        images[0].save("scan_preview.png")
                        img_preview.src = "scan_preview.png"
                        img_preview.visible = True
                        img_preview.update()
                        
                        # OCR
                        try:
                            import pytesseract
                            import fitz
                            
                            final_pdf = fitz.open()

                            for i, img in enumerate(images):
                                scan_status.value = f"⚙️ Procesando OCR página {i+1} de {len(images)}..."
                                page.update()
                                
                                fname = f"temp_page_{i}.png"
                                img.save(fname)
                                pdf_bytes = pytesseract.image_to_pdf_or_hocr(fname, extension='pdf', lang='spa')
                                
                                page_doc = fitz.open("pdf", pdf_bytes)
                                final_pdf.insert_pdf(page_doc)
                                page_doc.close()
                                
                                try:
                                    os.remove(fname)
                                except:
                                    pass

                            final_pdf.save("scan_temp.pdf")
                            final_pdf.close()
                            
                            scan_status.value = f"✅ Escaneo Finalizado ({len(images)} páginas)."
                            scan_status.color = "green"
                            show_success(f"Se han escaneado {len(images)} páginas correctamente.")

                        except Exception as pdf_err:
                            raise pdf_err
                        
                    except Exception as ex:
                        print(f"Error Scanning: {ex}")
                        scan_status.value = f"❌ Error: {str(ex)}"
                        scan_status.color = "red"
                    
                    finally:
                        # Restaurar UI
                        progress_bar.visible = False
                        btn_scan.disabled = False
                        page.update()

                import threading
                threading.Thread(target=run_scan_process).start()

            img_preview = ft.Image(
                src="",
                width=400,
                height=500,
                fit="contain",
                visible=False
            )

            # Metadata Inputs
            txt_year = ft.TextField(label="Año", value="2024", width=100)
            dd_type = ft.Dropdown(
                label="Tipo de Libro",
                width=200,
                options=[
                    ft.dropdown.Option("P", "Protocolos"),
                    ft.dropdown.Option("D", "Diligencias"),
                    ft.dropdown.Option("C", "Certificaciones"),
                    ft.dropdown.Option("A", "Arriendos"),
                    ft.dropdown.Option("O", "Otros")
                ],
                value="P"
            )
            def start_upload_flow(e):
                # 1. Validar inputs
                if not os.path.exists("scan_preview.png"):
                    scan_status.value, scan_status.color = "⚠️ No hay imagen", "red"
                    scan_status.update()
                    return

                # Deshabilitar UI
                scan_status.value = "🔍 Verificando código... (Esto puede tardar)"
                scan_status.color = "blue"
                progress_bar.visible = True
                btn_upload.disabled = True
                page.update()

                def run_upload_process(force_upload=False):
                    try:
                         # Si no es forzado, validar primero
                        if not force_upload:
                            print("   🔍 Iniciando validación OCR local...")
                            is_valid, code = validate_scan("scan_preview.png", txt_year.value, dd_type.value)
                            
                            if not is_valid:
                                print("   ⚠️ Validación falló. Pidiendo confirmación.")
                                # Restaurar UI para dialogo
                                progress_bar.visible = False
                                btn_upload.disabled = False
                                page.update()
                                
                                # Disparar dialogo en hilo principal (necesario para Flet?)
                                # Flet es thread-safe para actualizaciones simples, pero abrir dialogos mejor hacerlo con cuidado
                                dlg_confirm.open = True
                                page.update()
                                return
                        
                        # Si es válido o forzado, subir
                        print("   🚀 Iniciando carga al servidor...")
                        scan_status.value = "🚀 Subiendo archivo al servidor... (No cierre la ventana)"
                        scan_status.color = "blue"
                        progress_bar.visible = True
                        page.update()
                        
                        upload_pdf(user, txt_year.value, dd_type.value, scan_status)
                        
                        # Si upload_pdf termina sin excepción, asumimos éxito (el status se actualiza dentro)
                        progress_bar.visible = False
                        btn_upload.disabled = False
                        show_success("El archivo se ha subido correctamente.")
                        
                    except Exception as ex:
                        print(f"❌ Error en flujo de subida: {ex}")
                        scan_status.value = f"❌ Error: {str(ex)}"
                        scan_status.color = "red"
                        progress_bar.visible = False
                        btn_upload.disabled = False
                        page.update()

                import threading
                threading.Thread(target=run_upload_process).start()

            # Dialogo de confirmación forzada
            def confirm_upload(e):
                dlg_confirm.open = False
                page.update()
                
                # Relanzar proceso en modo forzado
                scan_status.value = "🚀 Iniciando subida forzada..."
                progress_bar.visible = True
                btn_upload.disabled = True
                page.update()
                
                def run_force_upload():
                    try:
                        scan_status.value = "🚀 Subiendo archivo... (Espere por favor)"
                        page.update()
                        upload_pdf(user, txt_year.value, dd_type.value, scan_status)
                        show_success("Archivo subido (Forzado).")
                    except Exception as ex:
                         scan_status.value = f"❌ Error: {str(ex)}"
                         scan_status.color = "red"
                    finally:
                        progress_bar.visible = False
                        btn_upload.disabled = False
                        page.update()

                import threading
                threading.Thread(target=run_force_upload).start()

            def cancel_upload(e):
                dlg_confirm.open = False
                scan_status.value, scan_status.color = "❌ Subida cancelada", "red"
                scan_status.update()

            dlg_confirm = ft.AlertDialog(
                modal=True,
                title=ft.Text("⚠️ Código no detectado"),
                content=ft.Text("No pude leer el código de barras en la imagen.\n¿Quieres subir el archivo de todos modos?"),
                actions=[
                    ft.TextButton("Sí, Subir", on_click=confirm_upload),
                    ft.TextButton("Cancelar", on_click=cancel_upload),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            
            btn_scan = ft.ElevatedButton("Escanear", on_click=on_scan_click)
            btn_upload = ft.ElevatedButton(
                "Subir PDF",
                on_click=start_upload_flow
            )

            # Panel de Control
            control_panel = ft.Column([
                ft.Text("Selección de Dispositivo:", weight="bold"),
                dd_devices,
                ft.ElevatedButton("🔄 Refrescar Dispositivos", on_click=lambda e: show_scanner_ui(user)), 
                ft.Divider(),
                ft.Text("Metadatos:", weight="bold"),
                ft.Row([txt_year, dd_type]),
                ft.Container(height=10),
                ft.Row([btn_scan, btn_upload]),
                ft.Container(height=10),
                progress_bar, # Barra de progreso
                scan_status
            ])

            page.add(
                ft.AppBar(
                    leading=ft.Text(" 🖨️", size=24), 
                    leading_width=40,
                    title=ft.Text("Escáner de Documentos"),
                    center_title=False,
                    bgcolor="surface_variant",
                    actions=[
                        ft.Text(f"Usuario: {user.get('username')}", size=14, weight="bold"),
                        ft.TextButton("Salir", on_click=logout)
                    ]
                ),
                ft.Row(
                    [
                        control_panel,
                        ft.Container(
                            content=img_preview,
                            border=ft.border.all(1, "grey"),
                            border_radius=10,
                            padding=10
                        )
                    ],
                    alignment="center", 
                    vertical_alignment="start"
                )
            )
            page.update()
            print("   ✅ Scanner UI updated")
        except Exception as ex:
            print(f"   ❌ ERROR en show_scanner_ui: {ex}")
            import traceback
            traceback.print_exc()

    print("🚀 Iniciando aplicación...")
    if load_session():
        print("✅ Sesión encontrada")
        show_scanner_ui(current_user)
    else:
        print("ℹ️  Mostrando login UI")
        show_login_ui()

if __name__ == "__main__":
    print("🚀 Iniciando servidor Flet en http://localhost:8550")
    try:
        ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=8550)
    except Exception as e:
        print(f"Error al iniciar: {e}")
