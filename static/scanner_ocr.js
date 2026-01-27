// Funciones para escaneo con OCR inmediato

async function escanearConOCR() {
    if (!servicioDisponible) {
        mostrarMensaje('⚠️ Por favor inicia el servicio de escaneo primero', 'warning');
        return;
    }

    const año = document.getElementById('año').value;
    const tipo = document.getElementById('tipo').value;
    const resolution = document.getElementById('scanResolution').value;
    const mode = document.getElementById('scanMode').value;
    const btnScanOCR = document.getElementById('btnScanOCR');
    const resultDiv = document.getElementById('scanOCRResult');

    btnScanOCR.disabled = true;
    btnScanOCR.innerHTML = '<span class="pulse">🖨️ Escaneando + OCR...</span>';
    resultDiv.innerHTML = '<div class="alert alert-info">⏳ Escaneando documento y detectando códigos. Por favor espera...</div>';

    try {
        const response = await fetch('/escaneo/scan_with_ocr', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                resolution: parseInt(resolution),
                mode: mode,
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
                            <button onclick="agregarCodigoAEscaneado('${data.archivo}', ${JSON.stringify(data.codigos).replace(/"/g, '&quot;')})" class="btn btn-primary">
                                ➕ Agregar Código Manual
                            </button>
                        </div>
                    </div>
                `;
            } else {
                html += `
                    <div class="alert alert-warning" style="margin-top: 1rem;">
                        <strong>⚠️ No se detectaron códigos</strong><br>
                        Puedes agregar códigos manualmente o verificar el documento.
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
        btnScanOCR.disabled = false;
        btnScanOCR.innerHTML = '🤖 Escanear con OCR Inmediato';
    }
}

async function procesarDocumentoEscaneado(archivo, codigos) {
    const año = document.getElementById('año').value;
    const tipo = document.getElementById('tipo').value;

    try {
        const response = await fetch('/escaneo/procesar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                archivo: archivo,
                codigos: JSON.parse(codigos.replace(/&quot;/g, '"')),
                año: año,
                tipo: tipo
            })
        });

        const data = await response.json();

        if (data.success) {
            alert(`✅ Procesamiento completado!\n${data.archivos_generados} archivos generados en ${data.ruta_salida}`);
            location.reload();
        } else {
            alert(`❌ Error: ${data.error}`);
        }
    } catch (error) {
        alert(`❌ Error: ${error.message}`);
    }
}

function agregarCodigoAEscaneado(archivo, codigos) {
    // Guardar datos para usar en modal
    archivoActual = archivo;
    codigosActuales = JSON.parse(codigos.replace(/&quot;/g, '"'));
    mostrarModalCodigo();
}

// Actualizar verificarServicio para habilitar ambos botones
const verificarServicioOriginal = window.verificarServicio;
window.verificarServicio = async function () {
    const statusDiv = document.getElementById('serviceStatus');
    const btnScan = document.getElementById('btnScan');
    const btnScanOCR = document.getElementById('btnScanOCR');

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
        } else {
            servicioDisponible = false;
            statusDiv.className = 'alert alert-warning';
            statusDiv.innerHTML = `
                <strong>⚠️ Servicio de escaneo no disponible</strong><br>
                Por favor inicia <code>scanner_service.py</code> para habilitar el escaneo directo
            `;
            btnScan.disabled = true;
            if (btnScanOCR) btnScanOCR.disabled = true;
        }
    } catch (error) {
        servicioDisponible = false;
        statusDiv.className = 'alert alert-error';
        statusDiv.innerHTML = '<strong>❌ Error verificando servicio</strong>';
        btnScan.disabled = true;
        if (btnScanOCR) btnScanOCR.disabled = true;
    }
};
