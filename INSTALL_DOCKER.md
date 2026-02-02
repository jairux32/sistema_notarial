# Guía de Instalación de Docker

## Para Ubuntu/Debian

```bash
# 1. Actualizar paquetes
sudo apt-get update

# 2. Instalar Docker
sudo apt-get install -y docker.io docker-compose

# 3. Agregar usuario al grupo docker
sudo usermod -aG docker $USER

# 4. Aplicar cambios (elegir una opción):
# Opción A: Reiniciar sesión
# Opción B: Ejecutar
newgrp docker

# 5. Verificar instalación
docker --version
docker-compose --version

# 6. Probar Docker
docker run hello-world
```

## Después de Instalar

```bash
# Volver al directorio del proyecto
cd /home/jairoguillen/sistema_notarial

# Ejecutar despliegue
./deploy.sh
```

## Alternativa: Instalación con Snap

```bash
sudo snap install docker
```

## Verificar que Docker funciona

```bash
docker ps
# Debería mostrar una lista vacía (sin errores)
```
