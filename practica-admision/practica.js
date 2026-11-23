const boton = document.getElementById('corregir');
const resultado = document.getElementById('resultado');
const tituloResultado = document.getElementById('titulo-resultado');
const resumenResultado = document.getElementById('resumen-resultado');
const areas = Array.from(resultado.querySelectorAll('[data-area]'), (contador) => ({
    contador,
    preguntas: Array.from(document.querySelectorAll(`#${contador.dataset.area} .pregunta`)),
}));

function actualizarResultado() {
    let total = 0;
    let aciertos = 0;
    let sinResponder = 0;

    for (const { contador, preguntas } of areas) {
        let aciertosArea = 0;
        for (const pregunta of preguntas) {
            const respuesta = pregunta.querySelector('input:checked');
            if (!respuesta) {
                sinResponder += 1;
            } else if (respuesta.value === pregunta.dataset.correcta) {
                aciertosArea += 1;
            }
        }
        contador.textContent = `${aciertosArea} de ${preguntas.length}`;
        total += preguntas.length;
        aciertos += aciertosArea;
    }

    resumenResultado.textContent = `${aciertos} de ${total} aciertos. Preguntas sin responder: ${sinResponder}.`;
}

boton.addEventListener('click', () => {
    resultado.hidden = false;
    actualizarResultado();
    tituloResultado.focus();
});

document.querySelector('main').addEventListener('change', () => {
    if (!resultado.hidden) actualizarResultado();
});

boton.hidden = false;
