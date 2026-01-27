// Función para comprimir PDF escaneado

async function comprimirPDF(archivo) {
    const level = document.getElementById('compressionLevel').value;

    if (level === 'none') {
        alert('⚠️ Selecciona un nivel de compresión');
        return;
    }

    const resultDiv = document.getElementById('compressionResult');
    resultDiv.innerHTML = '<div class="alert alert-info">⏳ Comprimiendo PDF...</div>';

    try {
        const response = await fetch('/escaneo/compress_pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                input_file: archivo,
                level: level
            })
        });

        const data = await response.json();

        if (data.success) {
            resultDiv.innerHTML = `
                <div class="alert alert-success">
                    <strong>✅ ${data.mensaje}</strong><br><br>
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem;">
                        <div>
                            <strong>Tamaño Original:</strong><br>
                            ${data.original_size_mb} MB
                        </div>
                        <div>
                            <strong>Tamaño Comprimido:</strong><br>
                            ${data.compressed_size_mb} MB
                        </div>
                        <div>
                            <strong>Reducción:</strong><br>
                            ${data.reduction_mb} MB (${data.reduction_percent}%)
                        </div>
                        <div>
                            <strong>Nivel:</strong><br>
                            ${data.level}
                        </div>
                    </div>
                    <br>
                    <code>${data.output_file}</code>
                </div>
            `;
        } else {
            resultDiv.innerHTML = `<div class="alert alert-error">❌ ${data.error}</div>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `<div class="alert alert-error">❌ Error: ${error.message}</div>`;
    }
}

// Agregar opción de compresión automática al escanear
const escanearConOCROriginal = window.escanearConOCR;
window.escanearConOCR = async function () {
    // Ejecutar escaneo original
    await escanearConOCROriginal();

    // Si hay compresión seleccionada, comprimir automáticamente
    const compressionLevel = document.getElementById('compressionLevel').value;
    if (compressionLevel !== 'none') {
        // Esperar a que termine el escaneo
        setTimeout(() => {
            const scanResult = document.getElementById('scanOCRResult');
            if (scanResult && scanResult.innerHTML.includes('success')) {
                // Extraer nombre de archivo del resultado
                const match = scanResult.innerHTML.match(/scanned\/[^<]+\.pdf/);
                if (match) {
                    comprimirPDF(match[0]);
                }
            }
        }, 2000);
    }
};
