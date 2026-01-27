"""
Modelos de base de datos usando SQLAlchemy
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Usuario(db.Model):
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nombre_completo = db.Column(db.String(100))
    rol = db.Column(db.String(20), default='usuario')
    activo = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    ultimo_acceso = db.Column(db.DateTime)
    
    # Relaciones
    documentos = db.relationship('Documento', backref='usuario', lazy=True)
    auditorias = db.relationship('Auditoria', backref='usuario', lazy=True)
    
    def set_password(self, password):
        """Hashear contraseña"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verificar contraseña"""
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'nombre_completo': self.nombre_completo,
            'rol': self.rol,
            'activo': self.activo,
            'fecha_creacion': self.fecha_creacion.isoformat() if self.fecha_creacion else None
        }


class Documento(db.Model):
    __tablename__ = 'documentos'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), unique=True, nullable=False)
    nombre_archivo = db.Column(db.String(255), nullable=False)
    ruta_archivo = db.Column(db.String(500))
    fecha_procesamiento = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    estado = db.Column(db.String(20), default='procesado')
    tiempo_procesamiento = db.Column(db.Float)
    metodo_ocr = db.Column(db.String(50))
    
    # Datos extraídos
    numero_escritura = db.Column(db.String(50))
    fecha_escritura = db.Column(db.Date)
    tipo_acto = db.Column(db.String(100))
    otorgantes = db.Column(db.Text)
    identificaciones = db.Column(db.Text)
    cuantia = db.Column(db.Numeric(15, 2))
    
    # Metadatos
    total_paginas = db.Column(db.Integer)
    confianza_promedio = db.Column(db.Float)
    requiere_revision = db.Column(db.Boolean, default=False)
    notas = db.Column(db.Text)
    
    # Auditoría
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    auditorias = db.relationship('Auditoria', backref='documento', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'nombre_archivo': self.nombre_archivo,
            'fecha_procesamiento': self.fecha_procesamiento.isoformat() if self.fecha_procesamiento else None,
            'estado': self.estado,
            'tiempo_procesamiento': self.tiempo_procesamiento,
            'metodo_ocr': self.metodo_ocr,
            'numero_escritura': self.numero_escritura,
            'fecha_escritura': self.fecha_escritura.isoformat() if self.fecha_escritura else None,
            'tipo_acto': self.tipo_acto,
            'otorgantes': self.otorgantes,
            'identificaciones': self.identificaciones,
            'cuantia': float(self.cuantia) if self.cuantia else None,
            'total_paginas': self.total_paginas,
            'confianza_promedio': self.confianza_promedio,
            'requiere_revision': self.requiere_revision,
            'notas': self.notas
        }


class Auditoria(db.Model):
    __tablename__ = 'auditoria'
    
    id = db.Column(db.Integer, primary_key=True)
    documento_id = db.Column(db.Integer, db.ForeignKey('documentos.id', ondelete='CASCADE'))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    accion = db.Column(db.String(50), nullable=False)
    detalles = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'documento_id': self.documento_id,
            'usuario_id': self.usuario_id,
            'accion': self.accion,
            'detalles': self.detalles,
            'ip_address': self.ip_address,
            'fecha': self.fecha.isoformat() if self.fecha else None
        }


class Configuracion(db.Model):
    __tablename__ = 'configuracion'
    
    clave = db.Column(db.String(100), primary_key=True)
    valor = db.Column(db.Text)
    descripcion = db.Column(db.Text)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def get_valor(clave, default=None):
        """Obtener valor de configuración"""
        config = Configuracion.query.get(clave)
        return config.valor if config else default
    
    @staticmethod
    def set_valor(clave, valor, descripcion=None):
        """Establecer valor de configuración"""
        config = Configuracion.query.get(clave)
        if config:
            config.valor = valor
            if descripcion:
                config.descripcion = descripcion
        else:
            config = Configuracion(clave=clave, valor=valor, descripcion=descripcion)
            db.session.add(config)
        db.session.commit()
