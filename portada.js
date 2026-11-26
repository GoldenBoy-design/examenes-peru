function iniciarCarrusel() {
    const panel = document.getElementById('front-slides');
    const hoy = peruDateTime().date;
    const tarjetas = [...panel.children].filter((tarjeta) => {
        tarjeta.hidden = true;
        return tarjeta.dataset.exam >= hoy;
    });
    if (!tarjetas.length) {
        document.getElementById('front-feature').hidden = true;
        document.getElementById('front-empty').hidden = false;
        return;
    }
    const indice = [];
    for (const enlace of document.querySelectorAll('[data-story-select]')) {
        const posicion = tarjetas.findIndex((tarjeta) => tarjeta.id === enlace.dataset.storySelect);
        if (posicion < 0) {
            enlace.parentElement.hidden = true;
            continue;
        }
        const selector = document.createElement('button');
        selector.type = 'button';
        selector.className = enlace.className;
        selector.setAttribute('aria-controls', panel.id);
        selector.append(...enlace.childNodes);
        selector.addEventListener('click', () => navegar(posicion));
        enlace.replaceWith(selector);
        indice.push(selector);
    }

    const posicion = document.getElementById('front-position');
    const aviso = document.getElementById('front-announcement');
    const boton = document.getElementById('front-toggle');
    const etiquetaPausa = boton.lastElementChild;
    const movimiento = matchMedia('(prefers-reduced-motion: reduce)');
    let actual = 0;
    let pausado = movimiento.matches;
    let ratonSobreNoticia = false;
    let temporizador;

    function mostrar(indiceNuevo, manual = false) {
        tarjetas[actual].hidden = true;
        actual = (indiceNuevo + tarjetas.length) % tarjetas.length;
        const seleccion = tarjetas[actual];
        seleccion.hidden = false;
        posicion.textContent = `${actual + 1} de ${tarjetas.length}`;
        indice.forEach((selector, i) => selector.setAttribute('aria-pressed', String(i === actual)));
        if (manual) aviso.textContent = seleccion.querySelector('h3').textContent;
    }

    mostrar(0);
    if (tarjetas.length === 1) {
        document.getElementById('front-edition').hidden = true;
        return;
    }
    document.getElementById('front-controls').hidden = false;

    function programar() {
        clearTimeout(temporizador);
        etiquetaPausa.textContent = pausado ? 'Reanudar rotación' : 'Pausar rotación';
        boton.classList.toggle('is-paused', pausado);
        if (pausado || ratonSobreNoticia || panel.contains(document.activeElement) || document.hidden) return;
        temporizador = setTimeout(() => {
            mostrar(actual + 1);
            programar();
        }, 8000);
    }

    function navegar(nuevo) {
        mostrar(nuevo, true);
        programar();
    }

    document.getElementById('front-prev').addEventListener('click', () => navegar(actual - 1));
    document.getElementById('front-next').addEventListener('click', () => navegar(actual + 1));
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

iniciarCarrusel();
