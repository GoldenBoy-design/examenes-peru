(() => {
    function normalizar(texto) {
        return texto.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLocaleLowerCase("es").trim();
    }

    const archivos = document.getElementById("archive-universities");
    if (archivos) {
        const tarjetas = Array.from(archivos.querySelectorAll(".archive-item"), tarjeta => ({
            tarjeta,
            texto: normalizar(tarjeta.querySelector("summary").textContent),
        }));
        const busqueda = document.getElementById("archive-search");
        const cantidad = document.getElementById("archive-count");
        const sinResultados = document.getElementById("archive-empty");

        busqueda.addEventListener("input", () => {
            const consulta = normalizar(busqueda.value);
            let visibles = 0;
            for (const { tarjeta, texto } of tarjetas) {
                tarjeta.hidden = !texto.includes(consulta);
                if (!tarjeta.hidden) visibles++;
            }
            cantidad.textContent = visibles === 1 ? "1 archivo de universidad" : `${visibles} archivos de universidades`;
            sinResultados.hidden = visibles !== 0;
        });
        document.getElementById("archive-filter").hidden = false;
    }

    const tabla = document.getElementById("score-table");
    if (tabla) {
        const cuerpo = tabla.tBodies[0];
        const filas = Array.from(cuerpo.rows, fila => ({
            fila,
            nombre: fila.cells[0].querySelector("a").textContent,
            minimo: fila.cells[1].dataset.score ? Number(fila.cells[1].dataset.score) : -Infinity,
            maximo: fila.cells[2].dataset.score ? Number(fila.cells[2].dataset.score) : -Infinity,
        }));
        const busqueda = document.getElementById("score-search");
        const orden = document.getElementById("score-order");
        const cantidad = document.getElementById("score-count");
        const sinResultados = document.getElementById("score-empty");

        function actualizarPuntajes() {
            const consulta = normalizar(busqueda.value);
            let visibles = 0;
            for (const { fila, nombre } of filas) {
                fila.hidden = !normalizar(nombre).includes(consulta);
                if (!fila.hidden) visibles++;
            }
            cantidad.textContent = visibles === 1 ? "1 carrera o sede" : `${visibles} carreras y sedes`;
            sinResultados.hidden = visibles !== 0;
            tabla.parentElement.scrollTop = 0;
        }

        orden.addEventListener("change", () => {
            const criterio = orden.value;
            filas.sort((a, b) => {
                const diferencia = criterio === "escuela" ? 0 : b[criterio] - a[criterio];
                return diferencia || a.nombre.localeCompare(b.nombre, "es");
            });
            cuerpo.append(...filas.map(({ fila }) => fila));
            actualizarPuntajes();
        });
        busqueda.addEventListener("input", actualizarPuntajes);
        document.getElementById("score-filter").hidden = false;
        cantidad.hidden = false;
    }

    function mostrarArchivoEnlazado() {
        const destino = document.getElementById(location.hash.slice(1));
        if (destino instanceof HTMLDetailsElement) {
            destino.open = true;
            destino.scrollIntoView();
        }
    }

    mostrarArchivoEnlazado();
    window.addEventListener("hashchange", mostrarArchivoEnlazado);
})();
