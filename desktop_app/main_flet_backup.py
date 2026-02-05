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
            # 1. Obtener scanners ANTES de borrar UI para evitar pantalla blanca si tarda
            print("   🔍 Buscando escáneres...")
            devices = get_connected_scanners()
            print(f"   ✅ Escáneres encontrados: {len(devices)}")

            page.clean()
            page.vertical_alignment = "start"

            # Estado del UI
            session_images = []
            
            # Componentes UI
            scan_status = ft.Text("Listo para escanear", color="grey")
            
            dd_devices = ft.Dropdown(
                label="Seleccionar Escáner",
                options=[ft.dropdown.Option(d[0], f"{d[1]} {d[2]}") for d in devices],
                width=400,
            )
            if devices:
                dd_devices.value = devices[0][0]

            progress_bar = ft.ProgressBar(width=400, color="blue", bgcolor="#eeeeee", visible=False)
            
            # --- Galería de Imágenes ---
            gallery_grid = ft.GridView(
                expand=True,
                runs_count=3,
                max_extent=150,
                child_aspect_ratio=0.8,
                spacing=10,
                run_spacing=10,
            )
            
            gallery_area = ft.Container(
                content=gallery_grid,
                border=ft.border.all(1, "grey"),
                border_radius=10,
                padding=10, 
                expand=True
            )

            # --- Dialogos ---
            dlg_success = ft.AlertDialog(
                title=ft.Text("✅ Proceso Completado"),
                content=ft.Text(""),
                actions=[ft.TextButton("Aceptar", on_click=lambda e: close_dialog(dlg_success))],
            )
            def close_dialog(dlg):
                dlg.open = False
                page.update()
            page.dialog = dlg_success

            def show_success(message):
                dlg_success.content.value = message
                dlg_success.open = True
                page.update()

            def render_gallery():
                gallery_grid.controls.clear()
                for i, img_path in enumerate(session_images):
                    def delete_image(e, index=i):
                        try:
                            if os.path.exists(session_images[index]): os.remove(session_images[index])
                            session_images.pop(index)
                            render_gallery()
                        except: pass
                    
                    card = ft.Container(
                        content=ft.Stack([
                            ft.Image(src=img_path, fit=ft.ImageFit.COVER, width=150, height=150, border_radius=5),
                            ft.Container(
                                content=ft.IconButton(ft.icons.CLOSE, icon_color="white", bgcolor="red", icon_size=15, on_click=delete_image, width=25, height=25),
                                alignment=ft.alignment.top_right, padding=5
                            ),
                            ft.Container(
                                content=ft.Text(f"Pág {i+1}", size=10, color="white", weight="bold", bgcolor="black54"),
                                alignment=ft.alignment.bottom_center, padding=2
                            )
                        ]),
                        width=150, height=150, bgcolor="white", padding=5, border_radius=5, shadow=ft.BoxShadow(spread_radius=1, blur_radius=3, color="grey")
                    )
                    gallery_grid.controls.append(card)
                page.update()

            # --- Lógica de Escaneo ---
            def on_scan_click(e):
                if not dd_devices.value:
                    scan_status.value, scan_status.color = "⚠️ Seleccione un escáner", "red"
                    page.update(); return

                scan_status.value, scan_status.color = "⏳ Comiendo hojas...", "blue"
                progress_bar.visible = True; btn_scan.disabled = True; page.update()

                def run_scan_process():
                    import uuid
                    count = 0
                    try:
                        import sane
                        try: sane.exit()
                        except: pass
                        sane.init()
                        dev = sane.open(dd_devices.value)
                        
                        try:
                            dev.mode = 'Color'; dev.resolution = 300
                            # Intentar configurar ADF
                            try: dev.source = 'ADF Duplex'
                            except: 
                                try: dev.source = 'ADF'
                                except: pass
                        except: pass

                        try:
                            iter = dev.multi_scan()
                            while True:
                                try:
                                    img = next(iter)
                                    fname = f"scan_{uuid.uuid4().hex[:8]}.png"
                                    img.save(fname)
                                    session_images.append(fname)
                                    count += 1
                                    scan_status.value = f"📸 Capturada pág {count} (Lote)"
                                    page.update()
                                except StopIteration: break
                        except Exception as e:
                            print(f"Error multiscan: {e}")
                            # Fallback snap
                            try:
                                dev.start(); img = dev.snap()
                                fname = f"scan_{uuid.uuid4().hex[:8]}.png"
                                img.save(fname); session_images.append(fname); count+=1
                            except: pass
                        
                        dev.close()
                        if count > 0:
                            scan_status.value, scan_status.color = "✅ Lote agregado.", "green"
                        else:
                            scan_status.value = "⚠️ No se escanearon páginas."
                            
                    except Exception as ex:
                        print(f"Error Scan: {ex}")
                        scan_status.value = f"❌ Error: {str(ex)}"
                    finally:
                        progress_bar.visible = False; btn_scan.disabled = False
                        render_gallery() # Update UI wrapper

                import threading
                threading.Thread(target=run_scan_process).start()

            # --- Inputs Metadata ---
            txt_year = ft.TextField(label="Año", value="2024", width=100)
            dd_type = ft.Dropdown(
                label="Tipo de Libro", width=200,
                options=[ft.dropdown.Option(x, y) for x,y in [("P","Protocolos"),("D","Diligencias"),("C","Certificaciones"),("A","Arriendos"),("O","Otros")]],
                value="P"
            )

            # --- Subida ---
            def start_upload_flow(e):
                if not session_images:
                    scan_status.value = "⚠️ Galería vacía"; page.update(); return

                scan_status.value = "🔍 Procesando..."; progress_bar.visible = True; btn_process.disabled = True; page.update()

                def run_upload(force=False):
                    try:
                        # 1. Validar (solo si no es forzado)
                        if not force:
                            valid, _ = validate_scan(session_images[0], txt_year.value, dd_type.value)
                            if not valid:
                                dlg_confirm.open = True; page.update()
                                progress_bar.visible = False; btn_process.disabled = False
                                return

                        # 2. Generar PDF
                        scan_status.value = "⚙️ Generando PDF..."; page.update()
                        import pytesseract, fitz
                        doc = fitz.open()
                        for img in session_images:
                            pdf_bytes = pytesseract.image_to_pdf_or_hocr(img, extension='pdf', lang='spa')
                            with fitz.open("pdf", pdf_bytes) as layer: doc.insert_pdf(layer)
                        doc.save("scan_temp.pdf"); doc.close()

                        # 3. Subir
                        scan_status.value = "🚀 Subiendo..."; page.update()
                        upload_pdf(user, txt_year.value, dd_type.value, scan_status)
                        
                        # Limpiar
                        for img in session_images: 
                            if os.path.exists(img): os.remove(img)
                        session_images.clear()
                        show_success("Proceso Finalizado Correctamente")

                    except Exception as ex:
                        scan_status.value = f"Error: {ex}"; scan_status.color = "red"
                    finally:
                        progress_bar.visible = False; btn_process.disabled = False; render_gallery()

                import threading
                threading.Thread(target=run_upload).start()

            # Confirm Dialog Logic
            def confirm_u(e): dlg_confirm.open=False; page.update(); threading.Thread(target=lambda: run_upload(True)).start()
            def cancel_u(e): dlg_confirm.open=False; page.update()
            
            dlg_confirm = ft.AlertDialog(
                title=ft.Text("⚠️ Validación Fallida"),
                content=ft.Text("No se leyó el código. ¿Subir igual?"),
                actions=[ft.TextButton("Sí", on_click=confirm_u), ft.TextButton("No", on_click=cancel_u)]
            )

            btn_scan = ft.ElevatedButton("➕ Agregar Hojas", on_click=on_scan_click, icon=ft.icons.ADD_A_PHOTO)
            btn_process = ft.ElevatedButton("🚀 Procesar Todo", on_click=start_upload_flow, icon=ft.icons.CLOUD_UPLOAD)

            # Layout Final
            control_panel = ft.Column([
                ft.Text("Dispositivo:", weight="bold"), dd_devices,
                ft.ElevatedButton("🔄 Refrescar", on_click=lambda e: show_scanner_ui(user)), 
                ft.Divider(),
                ft.Text("Datos:", weight="bold"), ft.Row([txt_year, dd_type]),
                ft.Divider(),
                btn_scan,
                ft.Container(height=10),
                btn_process,
                ft.Container(height=10),
                progress_bar, scan_status
            ], width=300)

            page.add(
                ft.AppBar(title=ft.Text("Escáner Modular v2.0"), actions=[ft.TextButton("Salir", on_click=logout)]),
                ft.Row([control_panel, ft.VerticalDivider(width=1), gallery_area], expand=True)
            )
            page.update()

        except Exception as ex:
            print(f"Error UI: {ex}")

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
