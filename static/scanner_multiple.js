// Función para escaneo multipágina con ADF

async function escanearMultipagina() {
    if (!servicioDisponible) {
        mostrarMensaje('⚠️ Por favor inicia el servicio de escaneo primero', 'warning');
        return;
    }

    const resolution = document.getElementById('scanResolution').value;
    const mode = document.getElementById('scanMode').value;
    const duplex = document.getElementById('duplexMode').checked;
    const maxPages = document.getElementById('maxPages').value;
    const btnScanMultiple = document.getElementById('btnScanMultiple');
    const resultDiv = document.getElementById('scanMultipleResult');

    btnScanMultiple.disabled = true;
    btnScanMultiple.innerHTML = '<span class="pulse">📄 Escaneando múltiples páginas...</span>';
    resultDiv.innerHTML = '<div class="alert alert-info">⏳ Escaneando documento. Coloca las páginas en el alimentador automático (ADF)...</div>';

    try {
        const response = await fetch('/escaneo/scan_multiple', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                resolution: parseInt(resolution),
                mode: mode,
                duplex: duplex,
                max_pages: parseInt(maxPages)
            })
        });

        const data = await response.json();

        if (data.success) {
            resultDiv.innerHTML = `
                <div class="alert alert-success">
                    <strong>✅ ${data.mensaje}</strong><br>
                    Archivo: <code>${data.archivo}</code><br>
                    Páginas escaneadas: <strong>${data.num_paginas}</strong><br>
                    Modo: ${duplex ? 'Duplex (ambos lados)' : 'Simple'}<br><br>
                    <button onclick="location.reload()" class="btn btn-primary">
                        🔄 Actualizar y Procesar Documento
                    </button>
                </div>
            `;
        } else {
            resultDiv.innerHTML = `<div class="alert alert-error">❌ ${data.error}</div>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `<div class="alert alert-error">❌ Error: ${error.message}</div>`;
    } finally {
        btnScanMultiple.disabled = false;
        btnScanMultiple.innerHTML = '📄 Escanear Múltiples Páginas (ADF)';
    }
}

// Actualizar verificarServicio para habilitar botón multipágina
const verificarServicioOriginal2 = window.verificarServicio;
window.verificarServicio = async function () {
    const statusDiv = document.getElementById('serviceStatus');
    const btnScan = document.getElementById('btnScan');
    const btnScanOCR = document.getElementById('btnScanOCR');
    const btnScanMultiple = document.getElementById('btnScanMultiple');

    try {
        const response = await fetch('/escaneo/check_service');
        const data = await response.json();

        if (data.available) {
            servicioDisponible = true;
            statusDiv.className = 'alert alert-success';
            statusDiv.innerHTML = `
                <strong>✅ Servicio de escaneo activo</strong><br>
                Sistema operativo: ${data.data.os}
            `;
            btnScan.disabled = false;
            if (btnScanOCR) btnScanOCR.disabled = false;
            if (btnScanMultiple) btnScanMultiple.disabled = false;
        } else {
            servicioDisponible = false;
            statusDiv.className = 'alert alert-warning';
            statusDiv.innerHTML = `
                <strong>⚠️ Servicio de escaneo no disponible</strong><br>
                Por favor inicia <code>scanner_service.py</code> para habilitar el escaneo directo
            `;
            btnScan.disabled = true;
            if (btnScanOCR) btnScanOCR.disabled = true;
            if (btnScanMultiple) btnScanMultiple.disabled = true;
        }
    } catch (error) {
        servicioDisponible = false;
        statusDiv.className = 'alert alert-error';
        statusDiv.innerHTML = '<strong>❌ Error verificando servicio</strong>';
        btnScan.disabled = true;
        if (btnScanOCR) btnScanOCR.disabled = true;
        if (btnScanMultiple) btnScanMultiple.disabled = true;
    }
};
