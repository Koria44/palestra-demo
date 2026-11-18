/**
 * PALESTRA - Interacciones de interfaz en JavaScript modular (ES6+).
 * Cumple con Content Security Policy (CSP) estricta: cero scripts inline ni eval().
 */
document.addEventListener("DOMContentLoaded", () => {
  // 1. Control del menu lateral movil (offcanvas responsivo)
  const botonAbrirMenu = document.getElementById("btn-abrir-menu-movil");
  const botonCerrarMenu = document.getElementById("btn-cerrar-menu-movil");
  const panelMenuMovil = document.getElementById("panel-menu-movil");
  const fondoMenuMovil = document.getElementById("fondo-menu-movil");

  const alternarMenuMovil = (mostrar) => {
    if (!panelMenuMovil || !fondoMenuMovil) return;
    if (mostrar) {
      panelMenuMovil.classList.remove("hidden");
      fondoMenuMovil.classList.remove("hidden");
      panelMenuMovil.setAttribute("aria-hidden", "false");
    } else {
      panelMenuMovil.classList.add("hidden");
      fondoMenuMovil.classList.add("hidden");
      panelMenuMovil.setAttribute("aria-hidden", "true");
    }
  };

  if (botonAbrirMenu) {
    botonAbrirMenu.addEventListener("click", () => alternarMenuMovil(true));
  }
  if (botonCerrarMenu) {
    botonCerrarMenu.addEventListener("click", () => alternarMenuMovil(false));
  }
  if (fondoMenuMovil) {
    fondoMenuMovil.addEventListener("click", () => alternarMenuMovil(false));
  }

  // 2. Cierre de alertas / mensajes del sistema
  document.querySelectorAll("[data-cerrar-alerta]").forEach((boton) => {
    boton.addEventListener("click", () => {
      const contenedor = boton.closest(".alert");
      if (contenedor) {
        contenedor.remove();
      }
    });
  });

  // 3. Modales de confirmacion antes de acciones destructivas (baja logica)
  const modalConfirmacion = document.getElementById("modal-confirmacion-accion");
  const textoModalConfirmacion = document.getElementById("modal-confirmacion-texto");
  const formularioModalConfirmacion = document.getElementById("modal-confirmacion-form");
  const botonCancelarModal = document.getElementById("btn-cancelar-modal");

  document.querySelectorAll("[data-confirmar-accion]").forEach((boton) => {
    boton.addEventListener("click", (evento) => {
      const urlAccion = boton.getAttribute("data-url-accion");
      const mensaje = boton.getAttribute("data-confirmar-accion");
      if (modalConfirmacion && formularioModalConfirmacion && urlAccion) {
        evento.preventDefault();
        if (textoModalConfirmacion && mensaje) {
          textoModalConfirmacion.textContent = mensaje;
        }
        formularioModalConfirmacion.setAttribute("action", urlAccion);
        modalConfirmacion.classList.add("abierto");
        modalConfirmacion.setAttribute("aria-hidden", "false");
      }
    });
  });

  if (botonCancelarModal && modalConfirmacion) {
    botonCancelarModal.addEventListener("click", () => {
      modalConfirmacion.classList.remove("abierto");
      modalConfirmacion.setAttribute("aria-hidden", "true");
    });
  }

  // 4. Barras de progreso dinamicas mediante atributo data-porcentaje (compatible con CSP style-src 'self')
  document.querySelectorAll("[data-porcentaje]").forEach((barra) => {
    const valor = parseFloat(barra.getAttribute("data-porcentaje") || "0");
    const acotado = Math.max(0, Math.min(100, isNaN(valor) ? 0 : valor));
    barra.style.width = `${acotado}%`;
  });

  // 5. Botones rapidos en toma de asistencia ("Marcar todos presentes")
  const botonTodosPresentes = document.getElementById("btn-marcar-todos-presente");
  if (botonTodosPresentes) {
    botonTodosPresentes.addEventListener("click", () => {
      document
        .querySelectorAll('input[type="radio"][value="presente"]')
        .forEach((radio) => {
          radio.checked = true;
        });
    });
  }

  // 6. Grafico SVG simple de evolucion de rendimiento para el Estudiante
  const contenedorGrafico = document.getElementById("grafico-evolucion-rendimiento");
  if (contenedorGrafico) {
    const datosCrudos = contenedorGrafico.getAttribute("data-puntos") || "";
    const pares = datosCrudos
      .split(";")
      .map((item) => item.trim())
      .filter(Boolean)
      .map((item) => {
        const [fecha, notaStr] = item.split("|");
        return { fecha, nota: parseFloat((notaStr || "0").replace(",", ".")) };
      })
      .filter((p) => !isNaN(p.nota) && p.nota >= 1.0 && p.nota <= 7.0);

    if (pares.length > 0) {
      renderizarGraficoRendimiento(contenedorGrafico, pares);
    }
  }
});

/**
 * Renderiza un grafico de lineas SVG accesible con la evolucion de notas (escala 1.0 a 7.0).
 */
function renderizarGraficoRendimiento(contenedor, puntos) {
  const ancho = 640;
  const alto = 220;
  const margenIzq = 44;
  const margenDer = 24;
  const margenSup = 20;
  const margenInf = 38;
  const anchoUtil = ancho - margenIzq - margenDer;
  const altoUtil = alto - margenSup - margenInf;

  const coordX = (indice) => {
    if (puntos.length === 1) return margenIzq + anchoUtil / 2;
    return margenIzq + (indice / (puntos.length - 1)) * anchoUtil;
  };
  const coordY = (nota) => {
    const proporcion = (nota - 1.0) / 6.0;
    return margenSup + altoUtil - proporcion * altoUtil;
  };

  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${ancho} ${alto}`);
  svg.setAttribute("class", "w-full");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Gráfico de evolución de rendimiento académico-deportivo");

  // Lineas guia horizontales (notas 1.0, 4.0, 7.0)
  [1.0, 4.0, 7.0].forEach((nivel) => {
    const y = coordY(nivel);
    const linea = document.createElementNS(ns, "line");
    linea.setAttribute("x1", String(margenIzq));
    linea.setAttribute("x2", String(ancho - margenDer));
    linea.setAttribute("y1", String(y));
    linea.setAttribute("y2", String(y));
    linea.setAttribute("stroke", nivel === 4.0 ? "#E9A23B" : "#D9DFE7");
    linea.setAttribute("stroke-dasharray", nivel === 4.0 ? "4 4" : "none");
    svg.appendChild(linea);

    const etiqueta = document.createElementNS(ns, "text");
    etiqueta.setAttribute("x", String(margenIzq - 8));
    etiqueta.setAttribute("y", String(y + 4));
    etiqueta.setAttribute("text-anchor", "end");
    etiqueta.setAttribute("fill", "#5B6776");
    etiqueta.setAttribute("font-size", "11");
    etiqueta.textContent = nivel.toFixed(1).replace(".", ",");
    svg.appendChild(etiqueta);
  });

  // Polilinea de evolucion
  if (puntos.length > 1) {
    const poly = document.createElementNS(ns, "polyline");
    const listaCoords = puntos.map((p, i) => `${coordX(i)},${coordY(p.nota)}`).join(" ");
    poly.setAttribute("fill", "none");
    poly.setAttribute("stroke", "#1D4E89");
    poly.setAttribute("stroke-width", "2.5");
    poly.setAttribute("points", listaCoords);
    svg.appendChild(poly);
  }

  // Puntos y etiquetas
  puntos.forEach((p, idx) => {
    const cx = coordX(idx);
    const cy = coordY(p.nota);

    const circulo = document.createElementNS(ns, "circle");
    circulo.setAttribute("cx", String(cx));
    circulo.setAttribute("cy", String(cy));
    circulo.setAttribute("r", "5");
    circulo.setAttribute("fill", "#1B998B");
    circulo.setAttribute("stroke", "#FFFFFF");
    circulo.setAttribute("stroke-width", "1.5");
    svg.appendChild(circulo);

    const textoNota = document.createElementNS(ns, "text");
    textoNota.setAttribute("x", String(cx));
    textoNota.setAttribute("y", String(cy - 10));
    textoNota.setAttribute("text-anchor", "middle");
    textoNota.setAttribute("fill", "#0B2545");
    textoNota.setAttribute("font-size", "11");
    textoNota.setAttribute("font-weight", "600");
    textoNota.textContent = p.nota.toFixed(1).replace(".", ",");
    svg.appendChild(textoNota);

    const textoFecha = document.createElementNS(ns, "text");
    textoFecha.setAttribute("x", String(cx));
    textoFecha.setAttribute("y", String(alto - 10));
    textoFecha.setAttribute("text-anchor", "middle");
    textoFecha.setAttribute("fill", "#5B6776");
    textoFecha.setAttribute("font-size", "10");
    textoFecha.textContent = p.fecha;
    svg.appendChild(textoFecha);
  });

  contenedor.innerHTML = "";
  contenedor.appendChild(svg);
}
