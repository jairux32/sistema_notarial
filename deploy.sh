#!/bin/bash
# Script de despliegue del Sistema Notarial con Docker

set -e  # Salir si hay errores

echo "🚀 Sistema Notarial - Script de Despliegue"
echo "=========================================="

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para imprimir mensajes
print_info() {
    echo -e "${GREEN}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 1. Verificar que Docker está instalado
print_info "Verificando Docker..."
if ! command -v docker &> /dev/null; then
    print_error "Docker no está instalado. Por favor instala Docker primero."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose no está instalado. Por favor instala Docker Compose primero."
    exit 1
fi

print_info "✅ Docker y Docker Compose encontrados"

# 2. Verificar archivo .env
if [ ! -f .env ]; then
    print_warning "Archivo .env no encontrado. Creando desde .env.example..."
    
    if [ -f .env.example ]; then
        cp .env.example .env
        print_info "Archivo .env creado. Por favor edita .env con tus configuraciones:"
        print_warning "  - EXTERNAL_DISK_PATH: Ruta al disco externo"
        print_warning "  - DB_PASSWORD: Contraseña de PostgreSQL"
        print_warning "  - SECRET_KEY: Clave secreta de Flask"
        echo ""
        read -p "¿Has configurado el archivo .env? (s/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Ss]$ ]]; then
            print_error "Por favor configura .env antes de continuar"
            exit 1
        fi
    else
        print_error "Archivo .env.example no encontrado"
        exit 1
    fi
fi

# 3. Verificar disco externo
source .env
if [ ! -d "$EXTERNAL_DISK_PATH" ]; then
    print_error "Disco externo no encontrado en: $EXTERNAL_DISK_PATH"
    read -p "¿Quieres crear el directorio? (s/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        mkdir -p "$EXTERNAL_DISK_PATH"
        print_info "Directorio creado: $EXTERNAL_DISK_PATH"
    else
        exit 1
    fi
fi

# 4. Crear directorios necesarios en disco externo
print_info "Creando estructura de directorios..."
mkdir -p "$EXTERNAL_DISK_PATH"/{uploads,processed,scanned,scanned_archive,scanned_preview,escaneo_separado,logs,postgres_data}
print_info "✅ Directorios creados"

# 5. Verificar permisos del escáner
print_info "Verificando acceso al escáner..."
if [ -d "/dev/bus/usb" ]; then
    print_info "✅ USB devices encontrados"
else
    print_warning "No se encontraron dispositivos USB. El escáner podría no funcionar."
fi

# 6. Construir imagen Docker
print_info "Construyendo imagen Docker..."
docker-compose build

# 7. Iniciar servicios
print_info "Iniciando servicios..."
docker-compose up -d

# 8. Esperar a que PostgreSQL esté listo
print_info "Esperando a que PostgreSQL esté listo..."
sleep 10

# 9. Verificar estado de los servicios
print_info "Verificando estado de servicios..."
docker-compose ps

# 10. Migrar datos si existe archivo JSON
if [ -f "auditoria_notarial.json" ]; then
    print_info "Archivo JSON encontrado. ¿Quieres migrar los datos a PostgreSQL?"
    read -p "(s/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        print_info "Migrando datos..."
        docker-compose exec app python migrate_to_db.py
    fi
fi

# 11. Mostrar información final
echo ""
echo "=========================================="
print_info "✅ Despliegue completado exitosamente!"
echo "=========================================="
echo ""
echo "📊 Información del sistema:"
echo "  - Aplicación: http://localhost:5000"
echo "  - Base de datos: PostgreSQL en puerto 5432"
echo "  - Datos almacenados en: $EXTERNAL_DISK_PATH"
echo ""
echo "🔧 Comandos útiles:"
echo "  - Ver logs: docker-compose logs -f"
echo "  - Detener: docker-compose down"
echo "  - Reiniciar: docker-compose restart"
echo "  - Ver estado: docker-compose ps"
echo ""
echo "👤 Usuario por defecto:"
echo "  - Username: admin"
echo "  - Password: admin123 (CAMBIAR EN PRODUCCIÓN)"
echo ""
print_warning "IMPORTANTE: Cambia las contraseñas por defecto en producción"
