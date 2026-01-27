-- Script de inicialización de la base de datos
-- Se ejecuta automáticamente al crear el contenedor de PostgreSQL

-- Crear extensiones útiles
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Tabla de usuarios
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(100),
    rol VARCHAR(20) DEFAULT 'usuario',
    activo BOOLEAN DEFAULT TRUE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ultimo_acceso TIMESTAMP
);

-- Tabla de documentos procesados
CREATE TABLE IF NOT EXISTS documentos (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) UNIQUE NOT NULL,
    nombre_archivo VARCHAR(255) NOT NULL,
    ruta_archivo VARCHAR(500),
    fecha_procesamiento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    usuario_id INTEGER REFERENCES usuarios(id),
    estado VARCHAR(20) DEFAULT 'procesado',
    tiempo_procesamiento FLOAT,
    metodo_ocr VARCHAR(50),
    
    -- Datos extraídos
    numero_escritura VARCHAR(50),
    fecha_escritura DATE,
    tipo_acto VARCHAR(100),
    otorgantes TEXT,
    identificaciones TEXT,
    cuantia DECIMAL(15, 2),
    
    -- Metadatos
    total_paginas INTEGER,
    confianza_promedio FLOAT,
    requiere_revision BOOLEAN DEFAULT FALSE,
    notas TEXT,
    
    -- Auditoría
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de auditoría/logs
CREATE TABLE IF NOT EXISTS auditoria (
    id SERIAL PRIMARY KEY,
    documento_id INTEGER REFERENCES documentos(id) ON DELETE CASCADE,
    usuario_id INTEGER REFERENCES usuarios(id),
    accion VARCHAR(50) NOT NULL,
    detalles JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de configuración del sistema
CREATE TABLE IF NOT EXISTS configuracion (
    clave VARCHAR(100) PRIMARY KEY,
    valor TEXT,
    descripcion TEXT,
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para mejorar rendimiento
CREATE INDEX IF NOT EXISTS idx_documentos_session ON documentos(session_id);
CREATE INDEX IF NOT EXISTS idx_documentos_fecha ON documentos(fecha_procesamiento);
CREATE INDEX IF NOT EXISTS idx_documentos_numero ON documentos(numero_escritura);
CREATE INDEX IF NOT EXISTS idx_auditoria_documento ON auditoria(documento_id);
CREATE INDEX IF NOT EXISTS idx_auditoria_fecha ON auditoria(fecha);

-- Trigger para actualizar timestamp
CREATE OR REPLACE FUNCTION actualizar_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.actualizado_en = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_actualizar_documentos
    BEFORE UPDATE ON documentos
    FOR EACH ROW
    EXECUTE FUNCTION actualizar_timestamp();

-- Insertar usuario admin por defecto
-- Password: admin123 (CAMBIAR EN PRODUCCIÓN)
INSERT INTO usuarios (username, password_hash, nombre_completo, rol)
VALUES ('admin', 'pbkdf2:sha256:260000$salt$hash', 'Administrador', 'admin')
ON CONFLICT (username) DO NOTHING;

-- Configuración inicial
INSERT INTO configuracion (clave, valor, descripcion) VALUES
    ('version_db', '1.0', 'Versión del esquema de base de datos'),
    ('ocr_method', 'hybrid', 'Método de OCR por defecto'),
    ('max_file_size_mb', '50', 'Tamaño máximo de archivo en MB')
ON CONFLICT (clave) DO NOTHING;
