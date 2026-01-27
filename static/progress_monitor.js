// Sistema de notificaciones de progreso en tiempo real

class ProgressMonitor {
    constructor() {
        this.activeTask = null;
        this.pollInterval = null;
    }

    startMonitoring(taskId, onUpdate, onComplete) {
        this.activeTask = taskId;

        // Crear elemento de notificación si no existe
        if (!document.getElementById('progress-notification')) {
            this.createNotificationElement();
        }

        // Polling cada 500ms
        this.pollInterval = setInterval(async () => {
            try {
                const response = await fetch(`/escaneo/progress/${taskId}`);
                const data = await response.json();

                if (data.status === 'running') {
                    this.updateProgress(data);
                    if (onUpdate) onUpdate(data);
                } else {
                    // Tarea completada
                    this.stopMonitoring();
                    this.showCompletion(data);
                    if (onComplete) onComplete(data);
                }
            } catch (error) {
                console.error('Error monitoreando progreso:', error);
            }
        }, 500);
    }

    stopMonitoring() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
        this.activeTask = null;
    }

    createNotificationElement() {
        const notification = document.createElement('div');
        notification.id = 'progress-notification';
        notification.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #1a1a1a;
            color: white;
            padding: 1rem;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            min-width: 300px;
            max-width: 400px;
            z-index: 10000;
            display: none;
        `;

        notification.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                <strong id="progress-title">Procesando...</strong>
                <button onclick="progressMonitor.hide()" style="background: none; border: none; color: #999; cursor: pointer; font-size: 1.2rem;">×</button>
            </div>
            <div id="progress-message" style="font-size: 0.9rem; color: #ccc; margin-bottom: 0.5rem;"></div>
            <div style="background: #333; border-radius: 4px; height: 8px; overflow: hidden;">
                <div id="progress-bar" style="background: #4a90e2; height: 100%; width: 0%; transition: width 0.3s;"></div>
            </div>
            <div id="progress-percent" style="text-align: right; font-size: 0.8rem; color: #999; margin-top: 0.25rem;">0%</div>
            <div id="progress-messages" style="margin-top: 0.5rem; font-size: 0.8rem; color: #999; max-height: 100px; overflow-y: auto;"></div>
        `;

        document.body.appendChild(notification);
    }

    updateProgress(data) {
        const notification = document.getElementById('progress-notification');
        if (!notification) return;

        notification.style.display = 'block';

        document.getElementById('progress-title').textContent = data.description;
        document.getElementById('progress-bar').style.width = data.percent + '%';
        document.getElementById('progress-percent').textContent = data.percent + '%';

        // Mostrar últimos mensajes
        if (data.messages && data.messages.length > 0) {
            const messagesDiv = document.getElementById('progress-messages');
            messagesDiv.innerHTML = data.messages
                .map(m => `<div>• ${m.message}</div>`)
                .join('');
        }
    }

    showCompletion(data) {
        const notification = document.getElementById('progress-notification');
        if (!notification) return;

        const success = data.status === 'completed';
        const icon = success ? '✅' : '❌';
        const color = success ? '#28a745' : '#dc3545';

        document.getElementById('progress-title').textContent = `${icon} ${success ? 'Completado' : 'Error'}`;
        document.getElementById('progress-bar').style.background = color;
        document.getElementById('progress-bar').style.width = '100%';

        // Auto-ocultar después de 5 segundos si fue exitoso
        if (success) {
            setTimeout(() => this.hide(), 5000);
        }
    }

    hide() {
        const notification = document.getElementById('progress-notification');
        if (notification) {
            notification.style.display = 'none';
        }
        this.stopMonitoring();
    }
}

// Instancia global
const progressMonitor = new ProgressMonitor();

// Integrar con funciones existentes
const escanearMultipaginaOriginal = window.escanearMultipagina;
if (typeof escanearMultipaginaOriginal === 'function') {
    window.escanearMultipagina = async function () {
        const taskId = 'scan_' + Date.now();

        // Iniciar monitoreo
        progressMonitor.startMonitoring(taskId, null, (data) => {
            console.log('Escaneo completado:', data);
        });

        // Ejecutar función original
        return escanearMultipaginaOriginal.apply(this, arguments);
    };
}
