# Guía de Despliegue en Producción

Esta guía detalla los pasos para llevar el **Sistema Notarial** (Servidor + App de Escritorio) a un entorno de producción real.

## 1. Servidor (Backend + Base de Datos)
El servidor debe alojarse en una máquina estable (Servidor Linux dedicado o VPS en la nube).

### Requisitos
- **OS**: Ubuntu Linux 22.04 LTS (Recomendado).
- **Recursos**: Mínimo 2 CPU, 4 GB RAM.
- **Software**: Docker Engine y Docker Compose.

### Pasos de Instalación
1.  **Clonar Repositorio**:
    ```bash
    git clone https://github.com/tu-usuario/sistema_notarial.git
    cd sistema_notarial
    ```
2.  **Configurar Secretos**:
    - Copia `.env.example` a `.env` (si no existe, crea uno basado en `docker-compose.yml`).
    - **CRÍTICO**: Cambia `SECRET_KEY` y `DB_PASSWORD` por valores seguros.
    ```ini
    SECRET_KEY=prod_super_secret_key_999
    DB_PASSWORD=prod_db_password_XYZ
    ```
3.  **Configurar Dominio/SSL (Opcional pero Recomendado)**:
    - Si el servidor es remoto, usa Nginx como proxy inverso.
    - Configura certificados SSL (Let's Encrypt) para usar HTTPS (`https://tuservidor.com`).
4.  **Iniciar Docker**:
    ```bash
    docker compose up -d --build
    ```
5.  **Verificar**:
    - Accede a `http://IP_SERVIDOR:5000` (o tu dominio).
    - Asegúrate que el login funciona.

---

## 2. Aplicación de Escritorio (Clientes)
La aplicación debe instalarse en las computadoras de la notaría que tienen los escáneres físicos conectados.

### Preparación del Ejecutable
Antes de compilar, debes apuntar la app a la IP real del servidor de producción.

1.  **Modificar URL**:
    - Edita `desktop_app/main.py`:
    ```python
    # CAMBIAR localhost POR LA IP O DOMINIO DEL SERVIDOR REAL
    API_URL = "http://192.168.1.50:5000/api" 
    # O si usas dominio: "https://sistema.tu-notaria.com/api"
    ```
2.  **Generar Ejecutable**:
    - **Windows**: Ejecuta `build_windows.bat`. El archivo final estará en `dist/EscanerNotarial.exe`.
    - **Linux**: Ejecuta `build_desktop.sh`.

### Instalación en Clientes
1.  Lleva el archivo `.exe` (o la carpeta completa generada en `dist`) a cada PC.
2.  **Drivers**: Asegúrate de que los drivers del escáner (lía Kodak/Fujitsu/etc.) estén instalados en Windows.
3.  **Ejecución**:
    - Crea un acceso directo en el escritorio.
    - Al abrir, ingresa usuario y contraseña (creados en la base de datos del servidor).

---

## 3. Mantenimiento y Backups
### Base de Datos
- Docker usa un volumen para los datos (`postgres_data`).
- **Backup Diario**:
    ```bash
    docker exec notarial_db pg_dump -U notarial_user sistema_notarial > backup_$(date +%F).sql
    ```
### Archivos PDF
- Los archivos se guardan en la carpeta mapeada en `docker-compose.yml` (ej: `/mnt/external`).
- Asegúrate de tener copias de seguridad de esa carpeta física.

## 4. Consideraciones de Red
- **LAN**: Si todo está en la misma oficina, solo necesitas que el servidor tenga IP fija.
- **Remoto**: Si los escáneres están fuera de la red del servidor, necesitas:
    - VPN (ZeroTier/Tailscale) para conectar las PCs al servidor de forma segura.
    - O exponer el puero 5000 del servidor (¡Solo con HTTPS!).
