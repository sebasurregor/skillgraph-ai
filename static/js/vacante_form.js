/* Formulario de vacante (HU-RF-011): filas de habilidades ponderadas, suma de pesos
   en vivo y previsualización de candidatos potenciales. */
(function () {
  var PREFIJO = "req";
  var cuerpo = document.querySelector("#tabla-requisitos tbody");
  var plantilla = document.getElementById("fila-vacia");
  var total = document.getElementById("id_" + PREFIJO + "-TOTAL_FORMS");
  var suma = document.getElementById("suma-pesos");
  var caja = document.getElementById("previsualizacion");
  if (!cuerpo || !plantilla || !total) return;

  function filasActivas() {
    return Array.prototype.filter.call(cuerpo.querySelectorAll(".fila-requisito"), function (f) {
      return !f.classList.contains("hidden");
    });
  }

  function campo(fila, nombre) { return fila.querySelector('[name$="-' + nombre + '"]'); }

  function agregarFila() {
    var indice = parseInt(total.value, 10);
    var html = plantilla.innerHTML.replace(/__prefix__/g, indice);
    cuerpo.insertAdjacentHTML("beforeend", html);
    total.value = indice + 1;
    actualizar();
    return cuerpo.lastElementChild;
  }

  function quitarFila(fila) {
    campo(fila, "DELETE").checked = true;
    fila.classList.add("hidden");
    // Una fila retirada deja de ser obligatoria para la validación del navegador.
    fila.querySelectorAll("[data-obligatorio]").forEach(function (el) {
      el.removeAttribute("data-obligatorio");
    });
    actualizar();
  }

  function actualizarSuma() {
    var centesimas = filasActivas().reduce(function (acum, fila) {
      var v = parseFloat(campo(fila, "peso").value);
      return acum + (isNaN(v) ? 0 : Math.round(v * 100));
    }, 0);
    suma.innerHTML = "Suma de pesos: <b>" + (centesimas / 100).toFixed(2) + "</b> de 1.00";
    suma.classList.toggle("suma-ok", centesimas === 100);
    suma.classList.toggle("suma-mal", centesimas !== 100);
  }

  var espera = null;
  function actualizarPrevisualizacion() {
    clearTimeout(espera);
    espera = setTimeout(function () {
      var requisitos = filasActivas().map(function (fila) {
        return {
          habilidad: campo(fila, "habilidad").value,
          nivel_minimo: campo(fila, "nivel_minimo").value || 3,
          obligatoria: campo(fila, "obligatoria").checked
        };
      }).filter(function (r) { return r.habilidad; });

      if (!requisitos.length) {
        caja.textContent = "Agregue habilidades para ver cuántos candidatos potenciales cumplirían los requisitos.";
        return;
      }
      fetch(caja.dataset.url, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value
        },
        body: JSON.stringify({ requisitos: requisitos })
      }).then(function (r) { return r.ok ? r.json() : Promise.reject(r); })
        .then(function (d) {
          var texto = "<b>" + d.candidatos + "</b> de " + d.total +
            " candidatos registrados cumplirían " +
            (requisitos.some(function (r) { return r.obligatoria; })
              ? "todas las habilidades obligatorias."
              : "al menos una de las habilidades. Marque las obligatorias para afinar el resultado.");
          if (d.aviso) texto += '<br><span class="tiny muted" data-aviso-grafo>' + d.aviso + "</span>";
          caja.innerHTML = texto;
        })
        .catch(function () {
          caja.textContent = "No fue posible calcular la previsualización en este momento.";
        });
    }, 300);
  }

  function actualizar() { actualizarSuma(); actualizarPrevisualizacion(); }

  document.getElementById("agregar-requisito").addEventListener("click", function () {
    campo(agregarFila(), "habilidad").focus();
  });
  cuerpo.addEventListener("click", function (e) {
    var boton = e.target.closest("[data-quitar]");
    if (boton) quitarFila(boton.closest(".fila-requisito"));
  });
  cuerpo.addEventListener("input", actualizar);
  cuerpo.addEventListener("change", actualizar);

  // Las filas que el servidor devolvió marcadas para eliminar siguen ocultas.
  cuerpo.querySelectorAll(".fila-requisito").forEach(function (fila) {
    if (campo(fila, "DELETE").checked) quitarFila(fila);
  });
  if (!filasActivas().length) agregarFila();
  actualizar();
})();
