# 🔐 Credenciales del Sistema Notarial

## Acceso al Sistema

**URL de acceso:** http://localhost:5000

### Credenciales de Administrador

```
Usuario: admin
Contraseña: PabloPunin1970@
```

## ⚠️ Problemas Comunes de Login

### 1. **Credenciales Incorrectas**
- Verifica que estés escribiendo exactamente: `admin` (todo en minúsculas)
- La contraseña es: `PabloPunin1970@` (con mayúscula en P, @ al final)
- **Importante:** La contraseña distingue entre mayúsculas y minúsculas

### 2. **Servidor No Iniciado**
Si no puedes acceder a http://localhost:5000:
```bash
cd /home/jairoguillen/sistema_notarial
source venv/bin/activate
python app.py
```

### 3. **Verificar que el Servidor Está Corriendo**
```bash
ps aux | grep "python app.py"
```

## 🔧 Solución de Problemas

### Reiniciar el Servidor
```bash
# Detener el servidor actual
pkill -f "python app.py"

# Iniciar nuevamente
cd /home/jairoguillen/sistema_notarial
source venv/bin/activate
python app.py
```

### Verificar Dependencias
```bash
cd /home/jairoguillen/sistema_notarial
python check_system.py
```

## 📝 Notas Importantes

1. **Ahora el sistema muestra mensajes de error** cuando las credenciales son incorrectas
2. Si ves un mensaje rojo en la pantalla de login, verifica que estés usando las credenciales exactas
3. El sistema está configurado para el puerto 5000
4. El modo debug está activado para facilitar el desarrollo

## 🚀 Estado Actual del Sistema

✅ Servidor Flask corriendo en http://127.0.0.1:5000
✅ Pillow instalado correctamente
✅ Tesseract OCR configurado
✅ Mensajes de error de login implementados
