"""Scanner service - WIA for Windows, SANE for Linux"""
import platform
import subprocess
import glob
import os
import uuid
import tempfile


class ScannerService:
    def __init__(self):
        self.system = platform.system()
        self.devices = []
        self.selected_device = None

    def detect_devices(self):
        if self.system == 'Windows':
            return self._detect_windows()
        else:
            return self._detect_sane()

    def _detect_windows(self):
        devices = []

        # Método 1: Buscar dispositivos WIA/USB de imagen
        try:
            ps_cmd = (
                "Get-PnpDevice | Where-Object { "
                "  $_.Class -eq 'Image' -or "
                "  $_.FriendlyName -match 'scanner|scan|kodak|canon|epson|hp|brother|xerox' "
                "} | ForEach-Object { "
                "  $status = if($_.Status -eq 'OK'){'[OK]'}else{'[' + $_.Status + ']'}; "
                "  Write-Output ($_.FriendlyName + '|' + $_.DeviceID + '|' + $status) "
                "}"
            )
            result = subprocess.run(
                ['powershell', '-Command', ps_cmd],
                capture_output=True, text=True, timeout=20
            )
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if '|' in line and line:
                    parts = line.split('|')
                    if len(parts) >= 2:
                        name = parts[0].strip()
                        device_id = parts[1].strip()
                        status = parts[2].strip() if len(parts) > 2 else ''
                        devices.append({
                            'name': f"{name} {status}",
                            'id': device_id
                        })
        except Exception:
            pass

        # Método 2: WMI class Image
        if not devices:
            try:
                ps_cmd = (
                    "Get-CimInstance Win32_PnPEntity | "
                    "Where-Object { $_.PNPClass -eq 'Image' } | "
                    "ForEach-Object { Write-Output ($_.Name + '|' + $_.DeviceID) }"
                )
                result = subprocess.run(
                    ['powershell', '-Command', ps_cmd],
                    capture_output=True, text=True, timeout=15
                )
                for line in result.stdout.strip().split('\n'):
                    line = line.strip()
                    if '|' in line and line:
                        parts = line.split('|', 1)
                        if len(parts) == 2:
                            devices.append({'name': parts[0].strip(), 'id': parts[1].strip()})
            except Exception:
                pass

        # Método 3: Service WIA
        if not devices:
            try:
                ps_cmd = (
                    "Get-CimInstance Win32_PnPEntity | "
                    "Where-Object { $_.Service -eq 'WIA' } | "
                    "ForEach-Object { Write-Output ($_.Name + '|' + $_.DeviceID) }"
                )
                result = subprocess.run(
                    ['powershell', '-Command', ps_cmd],
                    capture_output=True, text=True, timeout=15
                )
                for line in result.stdout.strip().split('\n'):
                    line = line.strip()
                    if '|' in line and line:
                        parts = line.split('|', 1)
                        if len(parts) == 2:
                            devices.append({'name': parts[0].strip(), 'id': parts[1].strip()})
            except Exception:
                pass

        # Método 4: WMIC como fallback
        if not devices:
            try:
                result = subprocess.run(
                    ['wmic', 'path', 'Win32_PnPEntity', 'where',
                     "PNPClass='Image'", 'get', 'Name,DeviceID', '/format:list'],
                    capture_output=True, text=True, timeout=15
                )
                current_name = None
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if line.startswith('DeviceID='):
                        current_id = line.split('=', 1)[1].strip()
                        if current_name and current_id:
                            devices.append({'name': current_name, 'id': current_id})
                    elif line.startswith('Name='):
                        current_name = line.split('=', 1)[1].strip()
            except Exception:
                pass

        # Siempre agregar escáner virtual
        devices.append({'name': 'Escaner Virtual (Simulacion)', 'id': 'simulated_scanner'})

        self.devices = devices
        return devices

    def _detect_sane(self):
        devices = []
        try:
            result = subprocess.run(
                ['scanimage', '-L'],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.split('\n'):
                if 'device' in line and 'is a' in line:
                    start = line.find("'") + 1
                    end = line.rfind("'")
                    if start > 0 and end > start:
                        device_id = line[start:end]
                        name_part = line[line.find('is a') + 5:].strip()
                        devices.append({'name': name_part, 'id': device_id})
        except FileNotFoundError:
            pass
        except Exception:
            pass

        if not devices:
            devices.append({'name': 'Escaner Virtual (Simulacion)', 'id': 'simulated_scanner'})

        self.devices = devices
        return devices

    def scan_single(self, device_id=None, output_dir=None):
        if device_id is None:
            device_id = self.selected_device
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix='scan_')

        if device_id == 'simulated_scanner':
            return self._simulate_scan(output_dir, pages=1)

        if self.system == 'Windows':
            return self._scan_wia(device_id, output_dir)
        else:
            return self._scan_sane(device_id, output_dir)

    def scan_batch(self, device_id=None, output_dir=None):
        if device_id is None:
            device_id = self.selected_device
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix='scan_')

        if device_id == 'simulated_scanner':
            return self._simulate_scan(output_dir, pages=3)

        if self.system == 'Windows':
            return self._scan_wia(device_id, output_dir)
        else:
            return self._scan_sane(device_id, output_dir)

    def _scan_wia(self, device_id, output_dir):
        """Escanear via WIA en Windows"""
        try:
            # Script WIA para escanear
            ps_script = f'''
Add-Type -AssemblyName System.Drawing

try {{
    $deviceManager = New-Object -ComObject WIA.DeviceManager
    $device = $null
    
    foreach ($d in $deviceManager.DeviceInfos) {{
        if ($d.DeviceID -eq "{device_id}") {{
            $device = $d
            break
        }}
    }}
    
    if (-not $device) {{
        Write-Output "ERROR: Dispositivo no encontrado"
        exit 1
    }}
    
    $item = $device.Items(1)
    
    # Configurar resolucion
    foreach ($prop in $item.Properties) {{
        if ($prop.Name -eq "Horizontal Resolution") {{
            $prop.Value = 300
        }}
        if ($prop.Name -eq "Vertical Resolution") {{
            $prop.Value = 300
        }}
        if ($prop.Name -eq "Color Mode") {{
            $prop.Value = 1
        }}
    }}
    
    $image = $item.Scan()
    $outputPath = "{output_dir.replace('\\', '\\\\')}"
    $fileName = "scan_" + [System.Guid]::NewGuid().ToString("N").Substring(0,8) + ".png"
    $fullPath = Join-Path $outputPath $fileName
    
    $image.SaveFile($fullPath)
    Write-Output "OK:" + $fullPath
    
}} catch {{
    Write-Output "ERROR:" + $_.Exception.Message
}}
'''
            ps_file = os.path.join(output_dir, 'scan.ps1')
            with open(ps_file, 'w', encoding='utf-8') as f:
                f.write(ps_script)

            result = subprocess.run(
                ['powershell', '-ExecutionPolicy', 'Bypass', '-File', ps_file],
                capture_output=True, text=True, timeout=60
            )

            try:
                os.remove(ps_file)
            except:
                pass

            if result.stdout.startswith('OK:'):
                path = result.stdout.split('OK:')[1].strip()
                if os.path.exists(path):
                    return [path], None

            return [], f'Error WIA: {result.stdout or result.stderr}'

        except subprocess.TimeoutExpired:
            return [], 'Tiempo de espera agotado'
        except Exception as e:
            return [], str(e)

    def _scan_sane(self, device_id, output_dir):
        images = []
        batch_prefix = os.path.join(output_dir, 'scan')
        cmd = [
            'scanimage', '-d', device_id,
            f'--batch={batch_prefix}_%d.png',
            '--format=png', '--resolution', '300', '--mode', 'Color'
        ]
        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            process.communicate(timeout=120)
            pattern = os.path.join(output_dir, 'scan_*.png')
            images = sorted(glob.glob(pattern))
            if not images:
                return [], 'No se generaron imagenes del escaner'
            return images, None
        except subprocess.TimeoutExpired:
            process.kill()
            return [], 'Tiempo de espera agotado'
        except FileNotFoundError:
            return [], 'Comando scanimage no encontrado. Instale SANE.'
        except Exception as e:
            return [], str(e)

    def _simulate_scan(self, output_dir, pages=3):
        from PIL import Image, ImageDraw, ImageFont
        images = []
        for i in range(pages):
            img = Image.new('RGB', (800, 1100), 'white')
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)
            except (OSError, IOError):
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
                except (OSError, IOError):
                    font = ImageFont.load_default()
            draw.text((50, 50), f"Pagina {i+1} - Escaneo Virtual", fill='black', font=font)
            draw.text((50, 100), f"Simulador del Sistema Notarial", fill='gray', font=font)
            draw.text((50, 150), f"20251101007P{i+1:05d}", fill='darkblue', font=font)
            path = os.path.join(output_dir, f'scan_sim_{uuid.uuid4().hex[:8]}_{i}.png')
            img.save(path)
            images.append(path)
        return images, None
