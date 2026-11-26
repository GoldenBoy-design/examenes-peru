async function actualizarActividad() {
    const contador = document.getElementById('footer-counter');
    const estado = document.getElementById('footer-points');
    const metodos = contador.dataset.actividad === 'contar' ? ['POST', 'GET'] : ['GET'];
    const formato = new Intl.NumberFormat('es-PE');

    for (const method of metodos) {
        try {
            const respuesta = await fetch('/.netlify/functions/visitas', {
                method,
                cache: 'no-store',
                signal: AbortSignal.timeout(6000)
            });
            if (!respuesta.ok) continue;
            const { puntos } = await respuesta.json();
            if (!Number.isSafeInteger(puntos) || puntos < 0) continue;
            estado.textContent = `${formato.format(puntos)} puntos`;
            estado.classList.add('activity-value');
            return;
        } catch {
            // Conserva el estado visible si el servicio no responde.
        }
    }
}

actualizarActividad();
