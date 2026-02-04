# Dockerfile para Sistema Notarial
# Optimizado para: escáner local, disco externo, multi-usuario

FROM python:3.11-slim

# Metadatos
LABEL maintainer="Sistema Notarial"
LABEL description="Sistema de procesamiento de documentos notariales con OCR"

# Variables de entorno
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=America/Bogota

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    # Tesseract OCR
    tesseract-ocr \
    tesseract-ocr-spa \
    # Poppler para PDF
    poppler-utils \
    # SANE para escáner
    sane-utils \
    libsane-dev \
    # Herramientas de imagen
    imagemagick \
    # Utilidades
    curl \
    wget \
    git \
    # Limpieza
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root para seguridad
RUN useradd -m -u 1000 notarial && \
    usermod -aG scanner notarial

# Directorio de trabajo
WORKDIR /app

# Copiar requirements primero (para cache de Docker)
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación
COPY . .

# Crear directorios necesarios
RUN mkdir -p \
    uploads \
    processed \
    scanned \
    scanned_archive \
    scanned_preview \
    escaneo_separado \
    logs \
    && chown -R notarial:notarial /app

# Cambiar a usuario no-root
USER notarial

# Exponer puerto
# ========== CONFIGURACIÓN DE ESCÁNER (RED) ==========
USER root

# 1. Instalar SANE y utilidades
RUN apt-get update && apt-get install -y \
    sane-utils \
    libsane1 \
    libsane-common \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# 2. Copiar drivers Kodak desde la carpeta local
COPY drivers/libsane-kds_s2000w.so.1.0.24 /usr/lib/x86_64-linux-gnu/sane/
RUN ln -s /usr/lib/x86_64-linux-gnu/sane/libsane-kds_s2000w.so.1.0.24 /usr/lib/x86_64-linux-gnu/sane/libsane-kds_s2000w.so.1 && \
    ln -s /usr/lib/x86_64-linux-gnu/sane/libsane-kds_s2000w.so.1 /usr/lib/x86_64-linux-gnu/sane/libsane-kds_s2000w.so

# 3. Copiar archivo de configuración
COPY drivers/kds_s2000w.conf /etc/sane.d/

# 4. Registrar driver en SANE
RUN echo "kds_s2000w" >> /etc/sane.d/dll.conf

# Permitir que el usuario 'notarial' edite la configuración (para IP dinámica)
RUN chown notarial:notarial /etc/sane.d/kds_s2000w.conf && chmod 644 /etc/sane.d/kds_s2000w.conf

# Volver a usuario no privilegiado
USER notarial

# 5. Exponer puertos (El 5001 será interno ahora, pero lo dejamos por si acaso)
EXPOSE 5000 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Comando de inicio
CMD ["./start.sh"]
