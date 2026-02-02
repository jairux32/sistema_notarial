# Guía Rápida de Despliegue - Sistema Notarial Docker

## 📋 Pre-requisitos

Antes de ejecutar `deploy.sh`, asegúrate de:

### 1. Docker Instalado

```bash
# Verificar Docker
docker --version
docker-compose --version

# Si no está instalado (Ubuntu/Debian):
sudo apt-get update
sudo apt-get install docker.io docker-compose
sudo usermod -aG docker $USER
# Cerrar sesión y volver a entrar
```

### 2. Disco Externo Montado

```bash
# Ver discos disponibles
lsblk

# Crear punto de montaje
sudo mkdir -p /mnt/external

# Montar disco (ejemplo con /dev/sdb1)
sudo mount /dev/sdb1 /mnt/external

# Verificar
ls -la /mnt/external

# Dar permisos
sudo chown -R $USER:$USER /mnt/external
sudo chmod -R 755 /mnt/external

# Hacer permanente (agregar a /etc/fstab)
echo "/dev/sdb1 /mnt/external ext4 defaults 0 2" | sudo tee -a /etc/fstab
```

### 3. Configurar .env

El archivo `.env` ya está creado con valores por defecto. **Edítalo antes de desplegar:**

```bash
nano .env
```

**Cambiar:**
- `EXTERNAL_DISK_PATH` → Ruta de tu disco externo
- `DB_PASSWORD` → Contraseña segura para PostgreSQL
- `SECRET_KEY` → Clave secreta para Flask

**Generar claves seguras:**
```bash
# Para SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"

# Para DB_PASSWORD
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

## 🚀 Despliegue

### Opción 1: Script Automatizado (Recomendado)

```bash
# Dar permisos de ejecución
chmod +x deploy.sh

# Ejecutar
./deploy.sh
```

El script hará:
1. ✅ Verificar Docker instalado
2. ✅ Verificar .env configurado
3. ✅ Verificar disco externo
4. ✅ Crear directorios necesarios
5. ✅ Construir imagen Docker
6. ✅ Iniciar servicios
7. ✅ Ofrecer migrar datos JSON

### Opción 2: Manual

```bash
# 1. Construir imagen
docker-compose build

# 2. Iniciar servicios
docker-compose up -d

# 3. Ver logs
docker-compose logs -f

# 4. Verificar estado
docker-compose ps
```

## ✅ Verificación

### 1. Verificar Contenedores

```bash
docker-compose ps

# Esperado:
# notarial_db    running (healthy)
# notarial_app   running (healthy)
```

### 2. Verificar Base de Datos

```bash
# Conectar a PostgreSQL
docker-compose exec db psql -U notarial_user -d sistema_notarial

# Ver tablas
\dt

# Ver usuarios
SELECT * FROM usuarios;

# Salir
\q
```

### 3. Acceder a la Aplicación

```bash
# Local
http://localhost:5000

# Desde red local (reemplazar con tu IP)
http://192.168.1.X:5000

# Credenciales por defecto
Usuario: admin
Password: admin123
```

## 🔄 Migración de Datos (Opcional)

Si tienes datos en `auditoria_notarial.json`:

```bash
docker-compose exec app python migrate_to_db.py
```

## 🔒 Seguridad Post-Despliegue

### 1. Cambiar Password del Admin

```bash
docker-compose exec app python -c "
from app import app, db
from models import Usuario
with app.app_context():
    admin = Usuario.query.filter_by(username='admin').first()
    admin.set_password('TU_NUEVO_PASSWORD_SEGURO')
    db.session.commit()
    print('✅ Password actualizado')
"
```

### 2. Configurar Firewall

```bash
# Permitir puerto 5000
sudo ufw allow 5000/tcp

# Verificar
sudo ufw status
```

## 📊 Comandos Útiles

```bash
# Ver logs en tiempo real
docker-compose logs -f

# Ver logs solo de la app
docker-compose logs -f app

# Reiniciar servicios
docker-compose restart

# Detener servicios
docker-compose down

# Backup de base de datos
docker-compose exec db pg_dump -U notarial_user sistema_notarial > backup_$(date +%Y%m%d).sql

# Restaurar backup
docker-compose exec -T db psql -U notarial_user sistema_notarial < backup.sql
```

## 🔍 Troubleshooting

### Contenedores no inician

```bash
# Ver logs de error
docker-compose logs

# Verificar .env
cat .env

# Verificar disco externo
ls -la $EXTERNAL_DISK_PATH
```

### Error de conexión a BD

```bash
# Reiniciar PostgreSQL
docker-compose restart db

# Ver logs
docker-compose logs db
```

### Error de permisos

```bash
# Dar permisos al disco externo
sudo chown -R 1000:1000 /mnt/external

# Reiniciar contenedores
docker-compose restart
```

## 📞 Soporte

Para más información, consulta:
- [DOCKER.md](DOCKER.md) - Documentación completa de Docker
- [README.md](README.md) - Documentación del sistema
- Walkthrough en `.gemini/antigravity/brain/.../walkthrough.md`

## 🎯 Checklist de Despliegue

- [ ] Docker y Docker Compose instalados
- [ ] Disco externo montado en `/mnt/external`
- [ ] Archivo `.env` configurado
- [ ] Claves seguras generadas
- [ ] `deploy.sh` ejecutado
- [ ] Contenedores corriendo (healthy)
- [ ] Base de datos inicializada
- [ ] Login funcional en http://localhost:5000
- [ ] Password del admin cambiado
- [ ] Firewall configurado
- [ ] Backup de BD configurado

¡Listo para producción! 🎉
