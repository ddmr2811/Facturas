// Script principal para la aplicación de procesamiento de facturas

document.addEventListener('DOMContentLoaded', function() {
    // Referencias a elementos del DOM
    const fileUpload = document.getElementById('file-upload');
    const selectedFile = document.getElementById('selected-file');
    const procesarBtn = document.getElementById('procesar-btn');
    const selectAllCheckbox = document.getElementById('select-all');
    
    // Inicializar tooltips de Bootstrap
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Inicializar modales
    const movimientoModal = new bootstrap.Modal(document.getElementById('movimientoModal'));
    const viewFacturaModal = new bootstrap.Modal(document.getElementById('viewFacturaModal'));
    
    // Inicializar toast
    const toastElement = document.getElementById('liveToast');
    const toast = new bootstrap.Toast(toastElement, {
        delay: 3000
    });
    
    // Función para mostrar notificación
    function showToast(message, success = true) {
        const toastBody = toastElement.querySelector('.toast-body');
        toastBody.textContent = message;
        
        if (success) {
            toastElement.classList.remove('bg-danger');
            toastElement.classList.add('bg-success');
            toastElement.querySelector('.toast-header').classList.remove('bg-danger');
            toastElement.querySelector('.toast-header').classList.add('bg-success');
        } else {
            toastElement.classList.remove('bg-success');
            toastElement.classList.add('bg-danger');
            toastElement.querySelector('.toast-header').classList.remove('bg-success');
            toastElement.querySelector('.toast-header').classList.add('bg-danger');
        }
        
        toast.show();
    }

    // Función para inicializar todos los botones y controles
    function initializeControls() {
        // Reinicializar botones de copia
        const copyButtons = document.querySelectorAll('.copy-btn');
        copyButtons.forEach(button => {
            button.removeEventListener('click', handleCopyClick);
            button.addEventListener('click', handleCopyClick);
        });

        // Reinicializar botones de vista
        const viewButtons = document.querySelectorAll('.view-btn');
        viewButtons.forEach(button => {
            button.removeEventListener('click', handleViewClick);
            button.addEventListener('click', handleViewClick);
        });

        // Reinicializar checkboxes de procesado
        initializeProcesadoCheckboxes();
    }

    // Handler para botones de copia
    function handleCopyClick(event) {
        const facturaId = event.target.closest('.copy-btn').getAttribute('data-factura-id');
        
        // Obtener solo el concepto del movimiento contable
        fetch(`/copiar_movimiento/${facturaId}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Copiar solo el concepto al portapapeles
                    const concepto = data.concepto || '';
                    
                    if (navigator.clipboard && window.isSecureContext) {
                        navigator.clipboard.writeText(concepto).then(() => {
                            showToast('Concepto copiado al portapapeles');
                        }).catch(err => {
                            console.error('Error al copiar al portapapeles:', err);
                            showToast('Error al copiar al portapapeles', false);
                        });
                    } else {
                        // Fallback para navegadores que no soportan clipboard API
                        const textArea = document.createElement('textarea');
                        textArea.value = concepto;
                        document.body.appendChild(textArea);
                        textArea.select();
                        try {
                            document.execCommand('copy');
                            showToast('Concepto copiado al portapapeles');
                        } catch (err) {
                            console.error('Error al copiar al portapapeles:', err);
                            showToast('Error al copiar al portapapeles', false);
                        }
                        document.body.removeChild(textArea);
                    }
                } else {
                    showToast('Error al obtener el movimiento contable: ' + data.error, false);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showToast('Error al obtener el movimiento contable', false);
            });
    }

    // Handler para botones de vista
    function handleViewClick(event) {
        const facturaId = event.target.closest('.view-btn').getAttribute('data-factura-id');
        const row = event.target.closest('tr');
        
        // Obtener datos de la fila para mostrar en el modal
        const nombre = row.cells[1].textContent;
        const cuenta = row.cells[4].textContent;
        const tipo = row.cells[5].textContent;
        const precio = row.cells[6].textContent;
        const estado = row.cells[7].textContent;
        const comunidad = row.cells[8].textContent;
        const numero = row.cells[9].textContent;
        const fecha = row.cells[3].textContent;
        
        // Llenar el modal
        document.getElementById('modal-view-nombre').textContent = nombre;
        document.getElementById('modal-view-cuenta').textContent = cuenta;
        document.getElementById('modal-view-comunidad').textContent = comunidad;
        document.getElementById('modal-view-fecha').textContent = fecha;
        document.getElementById('modal-view-numero').textContent = numero;
        document.getElementById('modal-view-estado').textContent = estado;
        document.getElementById('modal-view-precio').textContent = precio;
        document.getElementById('modal-view-tipo').textContent = tipo;
        
        // Configurar botones del modal
        const copyBtn = document.getElementById('copy-factura-modal');
        const downloadBtn = document.getElementById('download-factura-modal');
        
        if (copyBtn) copyBtn.setAttribute('data-factura-id', facturaId);
        if (downloadBtn) downloadBtn.setAttribute('data-factura-id', facturaId);
        
        // Mostrar el modal
        if (viewFacturaModal) viewFacturaModal.show();
        
        // Cargar la vista previa del PDF usando el ID de la factura
        loadPdfPreview(facturaId);
    }

    // Inicializar controles al cargar la página
    initializeControls();

    // Manejar selección de todos los checkboxes
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            const checkboxes = document.querySelectorAll('tbody input[type="checkbox"]');
            checkboxes.forEach(checkbox => {
                checkbox.checked = selectAllCheckbox.checked;
            });
        });
    }

    // Manejar la selección de archivos para subir
    if (fileUpload) {
        fileUpload.addEventListener('change', function() {
            if (this.files.length > 0) {
                if (this.files.length === 1) {
                    selectedFile.textContent = this.files[0].name;
                } else {
                    selectedFile.textContent = `${this.files.length} archivos seleccionados`;
                }
                procesarBtn.disabled = false;
            } else {
                selectedFile.textContent = "Ningún archivo seleccionado";
                procesarBtn.disabled = true;
            }
        });
    }

        // Manejar el procesamiento de archivos
    if (procesarBtn) {
        procesarBtn.addEventListener('click', function() {
            if (!fileUpload.files.length) {
                showToast('Por favor, seleccione archivos para procesar.', false);
                return;
            }
            
            const formData = new FormData();
            const progressContainer = document.getElementById('upload-progress-container');
            const progressBar = document.getElementById('upload-progress');
            
            // Agregar todos los archivos al FormData
            for (let i = 0; i < fileUpload.files.length; i++) {
                formData.append('file', fileUpload.files[i]);
            }

            // Incluir el estado de los checkboxes (nombres: pdf_optimizado, pdf_factura)
            const pdfOptimizado = document.getElementById('pdf-optimizado');
            const pdfFactura = document.getElementById('pdf-factura');
            // Enviar 'on' cuando están marcados. Si el elemento no existe (oculto), enviar valor por defecto 'on'
            if (pdfOptimizado) {
                if (pdfOptimizado.checked) {
                    formData.append('pdf_optimizado', 'on');
                }
            } else {
                // Asumimos optimizado por defecto si no hay control visual
                formData.append('pdf_optimizado', 'on');
            }
            if (pdfFactura) {
                if (pdfFactura.checked) {
                    formData.append('pdf_factura', 'on');
                }
            } else {
                // Si no existe el control (lo ocultamos visualmente), forzamos valor por defecto
                if (!formData.has('pdf_factura')) formData.append('pdf_factura', 'on');
            }
            
            // Mostrar progreso visual
            procesarBtn.disabled = true;
            procesarBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Procesando...';
            
            if (progressContainer) {
                progressContainer.classList.remove('d-none');
                progressBar.style.width = '0%';
                progressBar.setAttribute('aria-valuenow', 0);
            }
            
            // Simular proceso de reconocimiento
            showToast(`Iniciando reconocimiento de ${fileUpload.files.length} ${fileUpload.files.length > 1 ? 'facturas' : 'factura'}...`);
            
            // Simulamos proceso en etapas con animación de progreso
            let progress = 0;
            const updateProgress = (value) => {
                progress = value;
                if (progressBar) {
                    progressBar.style.width = `${progress}%`;
                    progressBar.setAttribute('aria-valuenow', progress);
                }
            };
            
            const progressInterval = setInterval(() => {
                if (progress < 90) {
                    updateProgress(progress + (90 - progress) / 10);
                }
            }, 300);
            
            // Simulamos un proceso en etapas para dar más realismo
            setTimeout(() => {
                showToast('Extrayendo texto de los PDFs...');
                updateProgress(30);
                
                setTimeout(() => {
                    showToast('Identificando campos de las facturas...');
                    updateProgress(60);
                    
                    setTimeout(() => {
                        showToast('Analizando cuentas contables...');
                        updateProgress(80);
                        
                        setTimeout(() => {
                            // Finalmente enviamos los archivos al servidor
                            fetch('/upload', {
                                method: 'POST',
                                body: formData
                            })
                            .then(response => response.json())
                            .then(data => {
                                if (data.success) {
                                    clearInterval(progressInterval);
                                    updateProgress(100);
                                    
                                    const plural = data.total_procesadas > 1;
                                    showToast(`¡${data.total_procesadas} ${plural ? 'facturas procesadas' : 'factura procesada'} correctamente!`);
                                    
                                    // Simulamos una breve espera antes de recargar
                                    setTimeout(() => {
                                        window.location.reload();
                                    }, 1500);
                                } else {
                                    showToast('Error al procesar las facturas: ' + data.error, false);
                                }
                            })
                            .catch(error => {
                                console.error('Error:', error);
                                showToast('Error al procesar las facturas', false);
                            })
                            .finally(() => {
                                clearInterval(progressInterval);
                                procesarBtn.disabled = false;
                                procesarBtn.innerHTML = '<i class="fas fa-cogs me-1"></i> Procesar Archivos';
                                fileUpload.value = '';
                                selectedFile.textContent = "Ningún archivo seleccionado";
                                
                                if (progressContainer) {
                                    setTimeout(() => {
                                        progressContainer.classList.add('d-none');
                                    }, 1500);
                                }
                            });
                        }, 1000);
                    }, 800);
                }, 1200);
            }, 500);
        });
    }

    // Variables para controlar la vista previa del PDF
    let currentPdfPage = 1;
    let totalPdfPages = 1;
    let currentPdfFilename = '';
    
    // Función para cargar vista previa del PDF
    function loadPdfPreview(facturaId, page = 1) {
        const previewImage = document.getElementById('pdf-preview-image');
        const loadingElement = document.getElementById('pdf-preview-loading');
        const previewContainer = document.getElementById('pdf-preview-container');
        const pageIndicator = document.getElementById('page-indicator');
        const prevBtn = document.getElementById('prev-page-btn');
        const nextBtn = document.getElementById('next-page-btn');
        
        // Mostrar loading y ocultar imagen
        if (loadingElement && previewContainer) {
            loadingElement.classList.remove('d-none');
            previewContainer.classList.add('d-none');
        }
        
        // Cargar la vista previa usando el ID de la factura
        fetch(`/pdf_preview/${facturaId}?page=${page}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Si el backend devuelve imageData (base64), usarla
                    if (data.imageData) {
                        previewImage.src = data.imageData;
                        // Actualizar contadores de página
                        currentPdfPage = data.currentPage || 1;
                        totalPdfPages = data.totalPages || 1;
                        currentPdfFilename = facturaId; // Ahora guardamos el ID

                        pageIndicator.textContent = `Página ${currentPdfPage} de ${totalPdfPages}`;
                        prevBtn.disabled = currentPdfPage <= 1;
                        nextBtn.disabled = currentPdfPage >= totalPdfPages;

                        if (data.limitedPreview) {
                            showToast('Vista previa limitada. Para mejor visualización, instale las dependencias completas.', false);
                        }

                        previewImage.onload = function() {
                            loadingElement.classList.add('d-none');
                            previewContainer.classList.remove('d-none');
                        };
                    } else if (data.pdf_url) {
                        // Si el backend devuelve pdf_url (archivo), cargamos como PDF renderizado por el navegador en un iframe alternativo
                        // Reemplazamos la imagen por un iframe dinámico
                        let iframe = document.createElement('iframe');
                        iframe.src = data.pdf_url;
                        iframe.width = '100%';
                        iframe.height = '600px';
                        iframe.style.border = '1px solid #ddd';

                        // Limpiar contenedor y añadir iframe
                        previewContainer.innerHTML = '';
                        previewContainer.appendChild(iframe);

                        iframe.onload = function() {
                            loadingElement.classList.add('d-none');
                            previewContainer.classList.remove('d-none');
                        };

                        currentPdfPage = 1;
                        totalPdfPages = 1;
                        currentPdfFilename = filename;
                        pageIndicator.textContent = `Página ${currentPdfPage} de ${totalPdfPages}`;
                        prevBtn.disabled = true;
                        nextBtn.disabled = true;
                    } else {
                        showToast('El servidor devolvió una respuesta de vista previa incompleta.', false);
                        loadingElement.classList.add('d-none');
                    }
                } else {
                    showToast('Error al cargar la vista previa: ' + (data.error || 'desconocido'), false);
                    loadingElement.classList.add('d-none');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showToast('Error al cargar la vista previa', false);
                loadingElement.classList.add('d-none');
            });
    }
    
    // Configurar botones de navegación de PDF
    const prevPageBtn = document.getElementById('prev-page-btn');
    const nextPageBtn = document.getElementById('next-page-btn');
    
    if (prevPageBtn) {
        prevPageBtn.addEventListener('click', function() {
            if (currentPdfPage > 1) {
                loadPdfPreview(currentPdfFilename, currentPdfPage - 1);
            }
        });
    }

    if (nextPageBtn) {
        nextPageBtn.addEventListener('click', function() {
            if (currentPdfPage < totalPdfPages) {
                loadPdfPreview(currentPdfFilename, currentPdfPage + 1);
            }
        });
    }
    
    // Manejar el botón de copiar al portapapeles desde el modal de movimiento
    const copyMovimientoBtn = document.getElementById('copy-movimiento');
    if (copyMovimientoBtn) {
        copyMovimientoBtn.addEventListener('click', function() {
            const cuenta = document.getElementById('modal-cuenta').value;
            const numero = document.getElementById('modal-numero').value;
            const importe = document.getElementById('modal-importe').value;
            const concepto = document.getElementById('modal-concepto').value;
            
            const textoACopiar = `Cuenta: ${cuenta}\nNúmero: ${numero}\nImporte: ${importe}\nConcepto: ${concepto}`;
            
            copyTextToClipboard(textoACopiar, '¡Movimiento contable copiado al portapapeles!');
            
            // Cerrar el modal después de copiar
            setTimeout(() => {
                movimientoModal.hide();
            }, 1000);
        });
    }
    
    // Manejar el botón de copiar desde el modal de vista
    const copyFacturaModalBtn = document.getElementById('copy-factura-modal');
    if (copyFacturaModalBtn) {
        copyFacturaModalBtn.addEventListener('click', function() {
            const facturaId = this.getAttribute('data-factura-id');
            
            // Usar la misma funcionalidad que los botones de copiar en la tabla
            fetch(`/copiar_movimiento/${facturaId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const textoACopiar = `Cuenta: ${data.movimiento.cuenta}\nNúmero: ${data.movimiento.numero}\nImporte: ${data.movimiento.importe}\nConcepto: ${data.movimiento.concepto}`;
                        
                        copyTextToClipboard(textoACopiar, '¡Movimiento contable copiado al portapapeles!');
                    } else {
                        showToast('Error al obtener el movimiento contable: ' + data.error, false);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showToast('Error al obtener el movimiento contable', false);
                });
        });
    }
    
    // Manejar el botón de descarga desde el modal de vista
    const downloadFacturaModalBtn = document.getElementById('download-factura-modal');
    if (downloadFacturaModalBtn) {
        downloadFacturaModalBtn.addEventListener('click', function() {
            const facturaId = this.getAttribute('data-factura-id');
            if (facturaId) {
                window.open(`/descargar/${facturaId}`, '_blank');
            } else {
                showToast('Error: ID de factura no encontrado', false);
            }
        });
    }

    // Función para inicializar checkboxes de procesado
    function initializeProcesadoCheckboxes() {
        const procesadoCheckboxes = document.querySelectorAll('.procesado-checkbox');
        procesadoCheckboxes.forEach(checkbox => {
            // Remover listener anterior si existe
            checkbox.removeEventListener('change', handleProcesadoChange);
            // Agregar nuevo listener
            checkbox.addEventListener('change', handleProcesadoChange);
        });
    }

    // Handler para cambios en checkboxes de procesado
    function handleProcesadoChange(event) {
        const facturaId = event.target.getAttribute('data-factura-id');
        
        // Enviar el cambio al servidor
        fetch(`/toggle_procesado/${facturaId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // El checkbox ya está actualizado visualmente
                const estado = data.procesado ? 'marcada como procesada' : 'desmarcada';
                showToast(`Factura ${estado}`);
            } else {
                // Si hay error, revertir el checkbox
                event.target.checked = !event.target.checked;
                showToast('Error al actualizar el estado: ' + data.error, false);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            // Si hay error, revertir el checkbox
            event.target.checked = !event.target.checked;
            showToast('Error al actualizar el estado', false);
        });
    }

    // Manejar checkboxes de procesado
    initializeProcesadoCheckboxes();

    // Re-inicializar checkboxes después de cargar nuevas facturas
    const originalLoadFacturas = window.loadFacturas || function() {};
    window.loadFacturas = function() {
        originalLoadFacturas();
        setTimeout(initializeProcesadoCheckboxes, 100);
    };
    
    // Función para copiar texto al portapapeles
    function copyTextToClipboard(text, successMessage) {
        navigator.clipboard.writeText(text).then(() => {
            showToast(successMessage);
        }).catch(() => {
            // Fallback para navegadores que no soportan clipboard API
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            showToast(successMessage);
        });
    }
});
