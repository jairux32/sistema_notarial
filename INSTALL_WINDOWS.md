# Guía de Instalación en Windows

Para ejecutar esta aplicación en Windows y tener tu propio `.exe`, sigue estos pasos:

## Requisitos Previos
1.  **Python Instalado**: Descarga e instala Python 3 (versión 3.10 o superior) desde [python.org](https://www.python.org/downloads/). Asegúrate de marcar la casilla "Add Python to PATH" durante la instalación.

## Pasos de Instalación

1.  **Copiar la Carpeta**:
    Copia toda la carpeta del proyecto (`sistema_notarial`) a tu ordenador con Windows.

2.  **Preparar el entorno**:
    Abre una consola (CMD o PowerShell), navega hasta la carpeta del proyecto y ejecuta:
    ```cmd
    python -m venv desktop_app\venv
    ```

3.  **Generar el Ejecutable (.exe)**:
    En la carpeta del proyecto, verás un archivo llamado **`build_windows.bat`**.
    *   Haz **doble clic** sobre él.
    *   Esto instalará automáticamente las librerías necesarias y creará el ejecutable.

4.  **Encontrar tu App**:
    Cuando termine, entra en la carpeta `dist` -> `EscanerNotarial`.
    Ahí encontrarás el archivo **`EscanerNotarial.exe`**.

    ¡Puedes crear un acceso directo a este archivo en tu escritorio!

## Notas Importantes
- Asegúrate de que tu escáner tenga los drivers instalados en Windows y sea detectado por el sistema antes de abrir la app.
- Si usas un antivirus, añade una excepción si bloquea el programa (al ser un .exe nuevo no está firmado).
