import customtkinter as ctk
import os
import json
import requests
import shutil
import uuid
import threading
from PIL import Image, ImageDraw
import platform
import time

# Configuration
ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

API_URL = "http://localhost:5000/api"
SESSION_FILE = "session.json"

class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, login_callback):
        super().__init__(master)
        self.login_callback = login_callback

        self.place(relx=0.5, rely=0.5, anchor="center")

        self.label_title = ctk.CTkLabel(self, text="Sistema Notarial", font=("Roboto", 24, "bold"))
        self.label_title.pack(pady=20, padx=50)

        self.entry_user = ctk.CTkEntry(self, placeholder_text="Usuario", width=200)
        self.entry_user.pack(pady=10)

        self.entry_pass = ctk.CTkEntry(self, placeholder_text="Contraseña", show="*", width=200)
        self.entry_pass.pack(pady=10)

        self.btn_login = ctk.CTkButton(self, text="Iniciar Sesión", command=self.login_event, width=200)
        self.btn_login.pack(pady=20)
        
        self.lbl_status = ctk.CTkLabel(self, text="", text_color="red")
        self.lbl_status.pack(pady=5)

    def login_event(self):
        username = self.entry_user.get()
        password = self.entry_pass.get()

        if not username or not password:
            self.lbl_status.configure(text="Complete todos los campos", text_color="red")
            return

        self.btn_login.configure(state="disabled", text="Conectando...")
        self.lbl_status.configure(text="")
        
        # Run in thread to avoid freezing UI
        threading.Thread(target=self.perform_login, args=(username, password)).start()

    def perform_login(self, username, password):
        try:
            response = requests.post(f"{API_URL}/login", json={"username": username, "password": password})
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    # Success
                    self.master.after(0, lambda: self.login_callback(data))
                else:
                    self.master.after(0, lambda: self.show_error("Credenciales incorrectas"))
            else:
                 self.master.after(0, lambda: self.show_error(f"Error servidor: {response.status_code}"))
        except Exception as e:
            self.master.after(0, lambda: self.show_error(f"Error conexión: {e}"))

    def show_error(self, message):
        self.lbl_status.configure(text=message, text_color="red")
        self.btn_login.configure(state="normal", text="Iniciar Sesión")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Sistema Notarial - Escáner (v2.0)")
        self.geometry("1000x700")

        # Session State
        self.user_token = None
        self.current_user = None

        # Check existing session
        if self.load_session():
            self.show_scanner()
        else:
            self.show_login()

    def load_session(self):
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, "r") as f:
                    data = json.load(f)
                    self.user_token = data.get("token")
                    self.current_user = data.get("user")
                    return True
            except:
                return False
        return False

    def save_session(self, token, user):
        with open(SESSION_FILE, "w") as f:
            json.dump({"token": token, "user": user}, f)
        self.user_token = token
        self.current_user = user

    def show_login(self):
        # Clear current frame
        for widget in self.winfo_children():
            widget.destroy()

        self.login_frame = LoginFrame(self, self.on_login_success)

    def on_login_success(self, data):
        token = data.get("token")
        user = data.get("user")
        self.save_session(token, user)
        self.show_scanner()

    def logout_event(self):
        if os.path.exists(SESSION_FILE): os.remove(SESSION_FILE)
        self.user_token = None; self.current_user = None
        self.show_login()

    def show_scanner(self):
        for widget in self.winfo_children(): widget.destroy()
        self.scanner_frame = ScannerFrame(self, self.logout_event, self.current_user)

if __name__ == "__main__":
    app = App()
    app.mainloop()

class ScannerFrame(ctk.CTkFrame):
    def __init__(self, master, logout_callback, user_data):
        super().__init__(master)
        self.logout_callback = logout_callback
        self.user_data = user_data
        self.session_images = []
        self.scan_thread = None

        self.pack(fill="both", expand=True)

        # --- Layout ---
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        
        self.main_area = ctk.CTkFrame(self, corner_radius=0)
        self.main_area.pack(side="right", fill="both", expand=True)

        # --- Sidebar Content ---
        ctk.CTkLabel(self.sidebar, text="Configuración", font=("Roboto", 18, "bold")).pack(pady=20)

        # Device Selection
        ctk.CTkLabel(self.sidebar, text="Dispositivo:").pack(padx=20, anchor="w")
        self.device_var = ctk.StringVar(value="Buscando...")
        self.cb_devices = ctk.CTkComboBox(self.sidebar, variable=self.device_var, width=200)
        self.cb_devices.pack(padx=20, pady=(0, 10))
        
        self.btn_refresh = ctk.CTkButton(self.sidebar, text="🔄 Refrescar", command=self.refresh_scanners, width=200)
        self.btn_refresh.pack(padx=20, pady=(0, 20))

        # Metadata
        ctk.CTkLabel(self.sidebar, text="Año:").pack(padx=20, anchor="w")
        self.entry_year = ctk.CTkEntry(self.sidebar, width=200)
        self.entry_year.insert(0, "2024")
        self.entry_year.pack(padx=20, pady=(0, 10))

        ctk.CTkLabel(self.sidebar, text="Tipo de Libro:").pack(padx=20, anchor="w")
        self.cb_type = ctk.CTkComboBox(self.sidebar, values=["Protocolos", "Diligencias", "Certificaciones", "Arriendos", "Otros"], width=200)
        self.cb_type.set("Protocolos")
        self.cb_type.pack(padx=20, pady=(0, 20))

        # Actions
        self.btn_scan = ctk.CTkButton(self.sidebar, text="➕ Escanear Hojas", command=self.start_scan_thread, fg_color="green", width=200)
        self.btn_scan.pack(padx=20, pady=10)

        self.btn_process = ctk.CTkButton(self.sidebar, text="🚀 Procesar y Subir", command=self.start_upload, state="disabled", width=200)
        self.btn_process.pack(padx=20, pady=10)

        ctk.CTkButton(self.sidebar, text="Cerrar Sesión", command=self.logout_callback, fg_color="transparent", border_width=1, text_color=("gray10", "#DCE4EE")).pack(side="bottom", pady=20)
        
        # Status
        self.progress = ctk.CTkProgressBar(self.sidebar, width=200)
        self.progress.set(0)
        self.progress.pack(side="bottom", padx=20, pady=10)
        self.progress.pack_forget() # Hidden initially

        self.lbl_status = ctk.CTkLabel(self.sidebar, text="Listo", wraplength=180)
        self.lbl_status.pack(side="bottom", padx=20, pady=20)

        # --- Main Area Content (Gallery) ---
        ctk.CTkLabel(self.main_area, text=f"Galería de Escaneo - Usuario: {user_data.get('username')}", font=("Roboto", 16)).pack(pady=10)
        
        self.scrollable_gallery = ctk.CTkScrollableFrame(self.main_area, label_text="Páginas Capturadas")
        self.scrollable_gallery.pack(fill="both", expand=True, padx=20, pady=20)

        # Initial Load
        self.refresh_scanners()

    def set_status(self, text, is_error=False, show_progress=False):
        self.lbl_status.configure(text=text, text_color="red" if is_error else ("black", "white"))
        if show_progress:
            self.progress.pack(side="bottom", padx=20, pady=10)
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.pack_forget()

    def refresh_scanners(self):
        self.set_status("Buscando escáneres...", show_progress=True)
        self.cb_devices.configure(state="disabled")
        threading.Thread(target=self._thread_get_scanners).start()

    def _thread_get_scanners(self):
        devices = []
        try:
            # Method 1: Try CLI 'scanimage -L' (Safer, no segfault)
            max_retries = 3
            result = None
            for attempt in range(max_retries):
                try:
                    import subprocess
                    cmd = ['scanimage', '-L']
                    print(f"Executing (Attempt {attempt+1}/{max_retries}): {' '.join(cmd)}")
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    
                    print(f"STDOUT: {result.stdout}")
                    if result.stdout.strip():
                        # Found something, break retry loop to parse
                        break
                    else:
                        print("Empty stdout from scanimage. Retrying...")
                        time.sleep(1)
                except Exception as e:
                    print(f"Attempt {attempt+1} failed: {e}")
                    time.sleep(1)

            # Output format: device `kodak_s2000w:libusb:001:005' is a Kodak Alaris s2000w USB scanner
            if result and result.stdout:
                for line in result.stdout.splitlines():
                    if "device" in line:
                        # Try backtick first (standard SANE)
                        if "`" in line:
                            sep = "`"
                        elif "'" in line: # Some versions/distros might use single quote
                            sep = "'"
                        else:
                            continue 
                            
                        parts = line.split(sep)
                        if len(parts) > 1:
                            # taking the part after the separator
                            # e.g. kodak_s2000w:libusb:001:005' is a ...
                            dev_part = parts[1]
                            # Now split by single quote to end the ID
                            dev_str = dev_part.split("'")[0]
                            
                            # Clean up name for display
                            name = dev_str
                            if "is a" in line:
                                name = line.split("is a")[1].strip()
                            
                            print(f"FOUND DEVICE: ID={dev_str} NAME={name}")
                            devices.append(f"{dev_str}|{name}")
                print(f"CLI Scanimage found: {len(devices)} devices")
        except Exception as cli_e:
            print(f"CLI Scanimage Error: {cli_e}")

        # Simulation Fallback

        # Simulation Fallback
        if not devices:
            devices.append("simulated_scanner|Escáner Virtual (Simulación)")

        # Update UI in main thread
        self.after(0, lambda: self._update_devices_ui(devices))

    def _update_devices_ui(self, devices):
        clean_values = [d.split("|")[1] for d in devices]
        self.device_ids = {d.split("|")[1]: d.split("|")[0] for d in devices} # Map Name -> ID
        
        self.cb_devices.configure(values=clean_values, state="normal")
        if clean_values:
            self.cb_devices.set(clean_values[0])
        
        self.set_status(f"Encontrados: {len(devices)}")

    def start_scan_thread(self):
        selected_name = self.cb_devices.get()
        if not selected_name:
            self.set_status("Seleccione un dispositivo", True)
            return

        device_id = self.device_ids.get(selected_name)
        self.set_status("Escaneando...", show_progress=True)
        self.btn_scan.configure(state="disabled")
        
        threading.Thread(target=self._scan_logic, args=(device_id,)).start()

    def _scan_logic(self, device_id):
        new_images = []
        try:
            # --- SIMULATION MODE ---
            if "simulated_scanner" in device_id:
                time.sleep(0.5) # Fake init
                for i in range(3):
                    time.sleep(0.5) # Fake scan time
                    img = Image.new('RGB', (800, 1100), color='white')
                    d = ImageDraw.Draw(img)
                    
                    # Draw text to simulate a real document
                    d.text((50, 50), f"Documento Simulado Página {i+1}", fill='black')
                    d.text((50, 80), f"ID Único: {uuid.uuid4()}", fill='black')
                    
                    # VALID CODE FOR BACKEND: Year + Notaria + Type + 5 Digits
                    # Default: 2024 + 1101007 + P + 12345
                    valid_code = f"{self.entry_year.get()}1101007{self.cb_type.get()[0]}12345" 
                    d.text((50, 200), f"CODE: {valid_code}", fill='black')
                    
                    fname = f"scan_{uuid.uuid4().hex[:8]}.png"
                    img.save(fname)
                    new_images.append(fname)
                    self.after(0, lambda m=f"Simulando pág {i+1}...": self.lbl_status.configure(text=m))
                
                self.after(0, lambda: self._on_scan_complete(new_images, "Simulación completada"))
                return
            # -----------------------

            # Fallback to CLI scanning for stability
            import subprocess
            import uuid
            
            # Using --batch to scan everything in the ADF
            # Format: scan_UUID_%04d.png
            batch_prefix = f"scan_{uuid.uuid4().hex[:8]}_"
            batch_format = batch_prefix + "%d.png"
            
            # Construct command: scanimage -d "DEVICE" --batch="FORMAT" --format=png --source "ADF Duplex" --resolution 300 --mode Color
            cmd = [
                'scanimage',
                '-d', device_id,
                f'--batch={batch_format}',
                '--format=png',
                '--resolution', '300',
                '--mode', 'Color'
            ]
            
            print(f"Executing Scan Command: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for completion
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                 # Check if it was just "out of paper" or standard exit
                 if "scanning" not in stdout and "scanning" not in stderr:
                     print(f"Scan CLI Error: {stderr}")
                     # Don't raise immediately, check if files were created (maybe partial scan)
                     # raise Exception(f"Error escaneando: {stderr[:100]}")
            
            print("CLI Scan process finished.")
            
            # Find generated files
            import glob
            # Scanimage batch numbering starts at 1, usually.
            generated_files = sorted(glob.glob(f"{batch_prefix}*.png"))
            
            if not generated_files:
                 # If no files, maybe it failed completely
                 if process.returncode != 0:
                     raise Exception(f"Fallo el escaneo: {stderr[:100]}")
                 else:
                     raise Exception("No se generaron imágenes. ¿Hay papel en el ADF?")

            new_images.extend(generated_files)
            
            self.after(0, lambda: self._on_scan_complete(new_images, f"Escaneadas {len(new_images)} páginas"))

        except Exception as e:
            self.after(0, lambda: self.set_status(f"Error: {e}", True))
            self.after(0, lambda: self.btn_scan.configure(state="normal"))

    def _on_scan_complete(self, new_paths, msg):
        self.session_images.extend(new_paths)
        self.refresh_gallery()
        self.set_status(msg)
        self.btn_scan.configure(state="normal")
        if self.session_images:
            self.btn_process.configure(state="normal")

    def refresh_gallery(self):
        # Clear existing
        for w in self.scrollable_gallery.winfo_children():
            w.destroy()

        # Re-draw
        for i, img_path in enumerate(self.session_images):
            # Frame for each image
            fr = ctk.CTkFrame(self.scrollable_gallery)
            fr.pack(pady=5, padx=5, fill="x")
            
            # Thumbnail
            try:
                pil_img = Image.open(img_path)
                ctk_img = ctk.CTkImage(light_image=pil_img, size=(100, 130))
                lbl_img = ctk.CTkLabel(fr, image=ctk_img, text="")
                lbl_img.pack(side="left", padx=10, pady=5)
            except: pass

            # Info
            ctk.CTkLabel(fr, text=f"Página {i+1}", font=("Roboto", 14, "bold")).pack(side="left", padx=10)
            
            # Delete Button
            cmd = lambda idx=i: self.delete_image(idx)
            ctk.CTkButton(fr, text="🗑️", width=40, height=40, fg_color="red", command=cmd).pack(side="right", padx=10)

    def delete_image(self, index):
        try:
            f = self.session_images[index]
            if os.path.exists(f): os.remove(f)
            self.session_images.pop(index)
            self.refresh_gallery()
            if not self.session_images:
                self.btn_process.configure(state="disabled")
        except Exception as e:
            print(f"Error deleting: {e}")

    def start_upload(self):
        self.set_status("Generando PDF y subiendo...", show_progress=True)
        self.btn_process.configure(state="disabled")
        threading.Thread(target=self._upload_logic).start()

    def _upload_logic(self):
        try:
            year = self.entry_year.get()
            # Map friendly name to code using index logic or a map
            type_map = {"Protocolos":"P", "Diligencias":"D", "Certificaciones":"C", "Arriendos":"A", "Otros":"O"}
            book_type = type_map.get(self.cb_type.get(), "P")

            # 1. Generate PDF
            self.after(0, lambda: self.set_status("Generando PDF...", show_progress=True))
            
            import pytesseract
            import fitz # PyMuPDF
            
            doc = fitz.open()
            for img_path in self.session_images:
                try:
                    pdf_bytes = pytesseract.image_to_pdf_or_hocr(img_path, extension='pdf', lang='spa')
                    with fitz.open("pdf", pdf_bytes) as layer:
                        doc.insert_pdf(layer)
                except Exception as e:
                    print(f"OCR Error on {img_path}: {e}")
            
            pdf_path = "scan_temp_ctk.pdf"
            doc.save(pdf_path)
            doc.close()

            # 2. Upload to API
            self.after(0, lambda: self.set_status("Subiendo al servidor...", show_progress=True))
            
            with open(pdf_path, 'rb') as f:
                files = {'pdf_file': (f'scan_{year}_{book_type}.pdf', f, 'application/pdf')}
                data = {
                    'username': self.user_data.get('username'),
                    'año': year,
                    'tipo_libro': book_type
                }
                response = requests.post(f"{API_URL}/upload_scan", files=files, data=data)

            if response.status_code == 200:
                res = response.json()
                if res.get('success'):
                    self.after(0, lambda: self._on_upload_success(res.get('message', 'OK')))
                else:
                    self.after(0, lambda: self.set_status(f"Error Backend: {res.get('error')}", True))
            else:
                self.after(0, lambda: self.set_status(f"Error HTTP {response.status_code}", True))

        except Exception as e:
            self.after(0, lambda: self.set_status(f"Error: {e}", True))
        finally:
             self.after(0, lambda: self.btn_process.configure(state="normal"))

    def _on_upload_success(self, msg):
        self.set_status(f"✅ Éxito: {msg}")
        self.progress.stop()
        self.progress.pack_forget()
        
        # Cleanup images
        for f in self.session_images:
            if os.path.exists(f): os.remove(f)
        self.session_images.clear()
        self.refresh_gallery()
        
        # Move PDF to Output Folder
        output_dir = os.path.join(os.getcwd(), "scanned_docs")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        final_pdf_name = f"scan_{uuid.uuid4().hex[:8]}.pdf"
        final_pdf_path = os.path.join(output_dir, final_pdf_name)
        
        if os.path.exists("scan_temp_ctk.pdf"):
            shutil.move("scan_temp_ctk.pdf", final_pdf_path)
            
        # Open Output Folder
        try:
            subprocess.Popen(['xdg-open', output_dir])
        except Exception as e:
            print(f"Error opening output folder: {e}")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Sistema Notarial - Escáner (v2.0 CTK)")
        self.geometry("1100x700")

        # Session State
        self.user_token = None
        self.current_user = None

        # Check existing session
        if self.load_session():
            self.show_scanner()
        else:
            self.show_login()

    def load_session(self):
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, "r") as f:
                    data = json.load(f)
                    self.user_token = data.get("token")
                    self.current_user = data.get("user")
                    return True
            except:
                return False
        return False

    def save_session(self, token, user):
        with open(SESSION_FILE, "w") as f:
            json.dump({"token": token, "user": user}, f)
        self.user_token = token
        self.current_user = user

    def show_login(self):
        for widget in self.winfo_children(): widget.destroy()
        self.login_frame = LoginFrame(self, self.on_login_success)

    def on_login_success(self, data):
        token = data.get("token")
        user = data.get("user")
        self.save_session(token, user)
        self.show_scanner()

    def logout_event(self):
        if os.path.exists(SESSION_FILE): os.remove(SESSION_FILE)
        self.user_token = None; self.current_user = None
        self.show_login()

    def show_scanner(self):
        for widget in self.winfo_children(): widget.destroy()
        self.scanner_frame = ScannerFrame(self, self.logout_event, self.current_user)

if __name__ == "__main__":
    app = App()
    app.mainloop()
