function iniciarCarrusel() {
    const panel = document.getElementById('front-slides');
    const hoy = peruDateTime().date;
    const tarjetas = [...panel.children].filter((tarjeta) => {
        tarjeta.hidden = tarjeta.dataset.exam < hoy;
        tarjeta.inert = true;
        return !tarjeta.hidden;
    });
    const indice = [...document.querySelectorAll('[data-story-select]')];
    const vigentes = new Set(tarjetas.map((tarjeta) => tarjeta.id));
    for (const enlace of indice) {
        enlace.parentElement.hidden = !vigentes.has(enlace.dataset.storySelect);
    }
    if (!tarjetas.length) {
        document.getElementById('front-news-grid').hidden = true;
        document.getElementById('front-empty').hidden = false;
        return;
    }

    const posicion = document.getElementById('front-position');
    const aviso = document.getElementById('front-announcement');
    const boton = document.getElementById('front-toggle');
    const movimiento = matchMedia('(prefers-reduced-motion: reduce)');
    let actual = 0;
    let pausado = movimiento.matches;
    let ratonSobreNoticia = false;
    let temporizador;

    function mostrar(indiceNuevo, manual = false) {
        tarjetas[actual].inert = true;
        actual = (indiceNuevo + tarjetas.length) % tarjetas.length;
        const seleccion = tarjetas[actual];
        seleccion.inert = false;
        posicion.textContent = `${actual + 1} de ${tarjetas.length}`;
        for (const enlace of indice) {
            if (enlace.dataset.storySelect === seleccion.id) enlace.setAttribute('aria-current', 'true');
            else enlace.removeAttribute('aria-current');
        }
        if (manual) aviso.textContent = seleccion.querySelector('h3').textContent;
    }

    mostrar(0);
    if (tarjetas.length === 1) return;
    document.getElementById('front-controls').hidden = false;

    function programar() {
        clearTimeout(temporizador);
        boton.textContent = pausado ? 'Reanudar rotación' : 'Pausar rotación';
        if (pausado || ratonSobreNoticia || panel.contains(document.activeElement) || document.hidden) return;
        temporizador = setTimeout(() => {
            mostrar(actual + 1);
            programar();
        }, 8000);
    }

    document.getElementById('front-prev').addEventListener('click', () => {
        mostrar(actual - 1, true);
        programar();
    });
    document.getElementById('front-next').addEventListener('click', () => {
        mostrar(actual + 1, true);
        programar();
    });
    boton.addEventListener('click', () => {
        pausado = !pausado;
        programar();
    });
    panel.addEventListener('mouseenter', () => {
        ratonSobreNoticia = true;
        programar();
    });
    panel.addEventListener('mouseleave', () => {
        ratonSobreNoticia = false;
        programar();
    });
    panel.addEventListener('focusin', programar);
    panel.addEventListener('focusout', () => queueMicrotask(programar));
    document.addEventListener('visibilitychange', programar);
    movimiento.addEventListener('change', () => {
        pausado = movimiento.matches;
        programar();
    });
    programar();
}

async function mostrarActividad() {
    try {
        const respuesta = await fetch('/.netlify/functions/visitas', { method: 'POST' });
        if (!respuesta.ok) return;
        const { puntos } = await respuesta.json();
        if (!Number.isSafeInteger(puntos) || puntos < 124) return;
        document.getElementById('front-points').textContent = new Intl.NumberFormat('es-PE').format(puntos);
        document.getElementById('front-counter').hidden = false;
    } catch {
        // La portada y el calendario siguen disponibles si falla el contador.
    }
}

iniciarCarrusel();
mostrarActividad();
