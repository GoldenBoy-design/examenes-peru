// Mapa de meses en español → índice 0-11
const meses = {
    enero: 0, febrero: 1, marzo: 2, abril: 3,
    mayo: 4, junio: 5, julio: 6, agosto: 7,
    septiembre: 8, octubre: 9, noviembre: 10, diciembre: 11
};

// Convierte "15 de Octubre, 2025" → objeto Date
function convertirFecha(texto) {
    const limpio = texto.replace(',', '').toLowerCase().trim();
    const partes = limpio.split(/\s+/);
    // partes = ["15", "de", "octubre", "2025"]
    const dia  = parseInt(partes[0], 10);
    const mes  = meses[partes[2]];
    const anio = parseInt(partes[3], 10);
    return new Date(anio, mes, dia);
}

let ordenAscendente = true;

function ordenarPorFecha() {
    const tbody  = document.querySelector('#tablaUniversidades tbody');
    const filas  = Array.from(tbody.querySelectorAll('tr'));
    const header = document.getElementById('fechaHeader');

    filas.sort((a, b) => {
        const dateA = convertirFecha(a.querySelector('.fecha').textContent.trim());
        const dateB = convertirFecha(b.querySelector('.fecha').textContent.trim());
        return ordenAscendente ? dateA - dateB : dateB - dateA;
    });

    // Re-insertar filas ordenadas
    filas.forEach(fila => tbody.appendChild(fila));

    // Actualizar ícono del header
    header.textContent = ordenAscendente ? 'Fecha de Examen ↑' : 'Fecha de Examen ↓';

    // Alternar dirección para el siguiente clic
    ordenAscendente = !ordenAscendente;
}

// Esperar a que el DOM esté listo antes de asignar el listener
    document.getElementById('fechaHeader').addEventListener('click', ordenarPorFecha);