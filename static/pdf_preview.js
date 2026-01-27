// Función para abrir vista previa de PDF

function abrirVistaPrevia(archivo) {
    // Extraer solo el nombre del archivo si viene con ruta
    const filename = archivo.split('/').pop();

    // Abrir en nueva ventana
    const width = 1200;
    const height = 800;
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;

    const vistaPrevia = window.open(
        `/escaneo/preview/${filename}`,
        'Vista Previa PDF',
        `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes`
    );

    if (!vistaPrevia) {
        alert('⚠️ Por favor permite las ventanas emergentes para ver la vista previa');
    }
}

// Escuchar mensajes de la ventana de vista previa
window.addEventListener('message', function (event) {
    if (event.data.action === 'process') {
        // El usuario quiere procesar el PDF desde la vista previa
        const filename = event.data.filename;
        console.log('Procesando PDF:', filename);

        // Aquí puedes agregar lógica adicional si es necesario
        // Por ejemplo, actualizar la interfaz o iniciar procesamiento automático
    }
});

// Agregar botón de vista previa a resultados de escaneo
const escanearConOCROriginalPreview = window.escanearConOCR;
if (typeof escanearConOCROriginalPreview === 'function') {
    window.escanearConOCR = async function () {
        await escanearConOCROriginalPreview.apply(this, arguments);

        // Esperar a que termine y agregar botón de vista previa
        setTimeout(() => {
            const resultDiv = document.getElementById('scanOCRResult');
            if (resultDiv && resultDiv.innerHTML.includes('success')) {
                const match = resultDiv.innerHTML.match(/scanned\/[^<"]+\.pdf/);
                if (match) {
                    const archivo = match[0];
                    // Agregar botón de vista previa si no existe
                    if (!resultDiv.innerHTML.includes('👁️ Vista Previa')) {
                        const btnPreview = `
                            <button onclick="abrirVistaPrevia('${archivo}')" class="btn btn-secondary" style="margin-top: 0.5rem;">
                                👁️ Vista Previa
                            </button>
                        `;
                        resultDiv.innerHTML = resultDiv.innerHTML.replace('</div>', btnPreview + '</div>');
                    }
                }
            }
        }, 500);
    };
}
