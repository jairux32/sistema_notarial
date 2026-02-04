// Función para escaneo multipágina con OCR automático

async function escanearMultipaginaConOCR() {
    if (!servicioDisponible) {
        mostrarMensaje('⚠️ Por favor inicia el servicio de escaneo primero', 'warning');
        return;
    }

    const año = document.getElementById('año').value;
    const tipo = document.getElementById('tipo').value;
    const resolution = document.getElementById('scanResolution').value;
    const mode = document.getElementById('scanMode').value;
    const duplex = document.getElementById('duplexMode').checked;
    const maxPages = document.getElementById('maxPages').value;
    const btnScanMultipleOCR = document.getElementById('btnScanMultipleOCR');
    const resultDiv = document.getElementById('scanMultipleOCRResult');

    if (!año || !tipo) {
        alert('⚠️ Por favor selecciona año y tipo de libro');
        return;
    }

    btnScanMultipleOCR.disabled = true;
    btnScanMultipleOCR.innerHTML = '<span class="pulse">📄🔍 Escaneando múltiples páginas + OCR...</span>';
    resultDiv.innerHTML = '<div class="alert alert-info">⏳ Escaneando documento multipágina y detectando códigos. Coloca las páginas en el ADF...</div>';

    try {
        const response = await fetch('/escaneo/scan_multiple_with_ocr', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                resolution: parseInt(resolution),
                mode: mode,
                duplex: duplex,
                max_pages: parseInt(maxPages),
                año: año,
                tipo: tipo
            })
        });

        const data = await response.json();

        if (data.success) {
            // Mostrar resultados con códigos detectados
            let html = `
                <div class="alert alert-success">
                    <strong>✅ ${data.mensaje}</strong><br>
                    Archivo: <code>${data.archivo}</code><br>
                    Páginas escaneadas: <strong>${data.num_paginas}</strong><br>
                    Modo: ${duplex ? 'Duplex (ambos lados)' : 'Simple'}<br>
                    Caracteres extraídos: ${data.caracteres_extraidos ? data.caracteres_extraidos.toLocaleString() : 'N/A'}
                </div>
            `;

            if (data.total_codigos > 0) {
                html += `
                    <div style="margin-top: 1rem;">
                        <h4>📋 Códigos Detectados (${data.total_codigos})</h4>
                        <div class="codes-grid" style="max-height: 200px; overflow-y: auto; margin-top: 0.5rem;">
                            ${data.codigos.map((c, i) => `<div class="code-item">${i + 1}. ${c}</div>`).join('')}
                        </div>
                        <div style="margin-top: 1rem;">
                            <button onclick="procesarDocumentoEscaneado('${data.archivo}', ${JSON.stringify(data.codigos).replace(/"/g, '&quot;')})" class="btn btn-success">
                                ✅ Procesar y Generar PDFs
                            </button>
                            <button onclick="abrirVistaPrevia('${data.archivo}')" class="btn btn-secondary">
                                👁️ Vista Previa
                            </button>
                        </div>
                    </div>
                `;
            } else {
                html += `
                    <div class="alert alert-warning" style="margin-top: 1rem;">
                        <strong>⚠️ No se detectaron códigos</strong><br>
                        Puedes agregar códigos manualmente o verificar el documento.
                        <div style="margin-top: 0.5rem;">
                            <button onclick="abrirVistaPrevia('${data.archivo}')" class="btn btn-secondary">
                                👁️ Vista Previa
                            </button>
                        </div>
                    </div>
                `;
            }

            resultDiv.innerHTML = html;
        } else {
            resultDiv.innerHTML = `<div class="alert alert-error">❌ ${data.error}</div>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `<div class="alert alert-error">❌ Error: ${error.message}</div>`;
    } finally {
        btnScanMultipleOCR.disabled = false;
        btnScanMultipleOCR.innerHTML = '📄🔍 Escanear Múltiples Páginas + OCR';
    }
}

// Actualizar verificarServicio para habilitar el nuevo botón
const verificarServicioOriginal3 = window.verificarServicio;
window.verificarServicio = async function () {
    const statusDiv = document.getElementById('serviceStatus');
    const btnScan = document.getElementById('btnScan');
    const btnScanOCR = document.getElementById('btnScanOCR');
    const btnScanMultiple = document.getElementById('btnScanMultiple');
    const btnScanMultipleOCR = document.getElementById('btnScanMultipleOCR');

    try {
        const response = await fetch('/escaneo/check_service');
        const data = await response.json();

        if (data.available) {
            servicioDisponible = true;
            statusDiv.className = 'alert alert-success';
            statusDiv.innerHTML = `
                <strong>✅ Servicio de escaneo activo</strong><br>
                Sistema operativo: ${data.os}
            `;
            btnScan.disabled = false;
            if (btnScanOCR) btnScanOCR.disabled = false;
            if (btnScanMultiple) btnScanMultiple.disabled = false;
            if (btnScanMultipleOCR) btnScanMultipleOCR.disabled = false;
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
            if (btnScanMultipleOCR) btnScanMultipleOCR.disabled = true;
        }
    } catch (error) {
        servicioDisponible = false;
        statusDiv.className = 'alert alert-error';
        statusDiv.innerHTML = '<strong>❌ Error verificando servicio</strong>';
        btnScan.disabled = true;
        if (btnScanOCR) btnScanOCR.disabled = true;
        if (btnScanMultiple) btnScanMultiple.disabled = true;
        if (btnScanMultipleOCR) btnScanMultipleOCR.disabled = true;
    }
};
