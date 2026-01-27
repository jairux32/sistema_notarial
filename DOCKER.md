# Despliegue con Docker - Sistema Notarial

Guía rápida para desplegar el Sistema Notarial usando Docker.

## 🚀 Inicio Rápido

```bash
# 1. Configurar entorno
cp .env.example .env
nano .env  # Editar EXTERNAL_DISK_PATH, DB_PASSWORD, SECRET_KEY

# 2. Desplegar
./deploy.sh

# 3. Acceder
# http://localhost:5000
# Usuario: admin | Password: admin123
```

## ⚙️ Configuración Requerida

### 1. Disco Externo

```bash
# Montar disco
sudo mkdir -p /mnt/external
sudo mount /dev/sdb1 /mnt/external
sudo chown -R $USER:$USER /mnt/external

# Permanente (agregar a /etc/fstab)
echo "/dev/sdb1 /mnt/external ext4 defaults 0 2" | sudo tee -a /etc/fstab
```

### 2. Variables de Entorno (.env)

```bash
EXTERNAL_DISK_PATH=/mnt/external
DB_PASSWORD=tu_password_seguro
SECRET_KEY=tu_clave_secreta
```

## 📦 Comandos Útiles

```bash
# Ver logs
docker-compose logs -f

# Reiniciar
docker-compose restart

# Detener
docker-compose down

# Estado
docker-compose ps

# Backup BD
docker-compose exec db pg_dump -U notarial_user sistema_notarial > backup.sql

# Migrar datos JSON → PostgreSQL
docker-compose exec app python migrate_to_db.py
```

## 🌐 Acceso Red Local

```bash
# Permitir puerto 5000
sudo ufw allow 5000/tcp

# Obtener IP
ip addr show | grep inet

# Acceder desde otros equipos
# http://IP_DEL_SERVIDOR:5000
```

## 🔒 Seguridad

```bash
# Generar claves seguras
python3 -c "import secrets; print(secrets.token_hex(32))"

# Cambiar en .env:
# - DB_PASSWORD
# - SECRET_KEY
# - Password del usuario admin (en la BD)
```

## 📊 Base de Datos

```bash
# Conectar
docker-compose exec db psql -U notarial_user -d sistema_notarial

# Ver documentos
SELECT * FROM documentos ORDER BY id DESC LIMIT 10;

# Ver usuarios
SELECT * FROM usuarios;
```

## 🔧 Troubleshooting

```bash
# Error de conexión BD
docker-compose restart db

# Error de permisos
sudo chown -R 1000:1000 $EXTERNAL_DISK_PATH

# Ver logs de error
docker-compose logs app
docker-compose logs db
```

## 📝 Más Información

Ver [README.md](README.md) para documentación completa del sistema.
