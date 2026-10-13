/* Regla común de validación: en todo formulario con `data-validar`, si hay campos
   obligatorios vacíos o inválidos se muestra la alerta, se resaltan los campos
   y el foco va al primero. El servidor aplica la misma regla (skillgraph/formularios.py). */
(function () {
  function esInvalido(el, form) {
    if (el.type === "checkbox") return !el.checked;
    if (el.type === "radio") return !form.querySelector('input[name="' + el.name + '"]:checked');
    if (el.type === "file") return el.files.length === 0;
    return !el.value.trim() || !el.checkValidity();
  }

  document.querySelectorAll("form[data-validar]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      var primero = null;
      form.querySelectorAll("[data-obligatorio]").forEach(function (el) {
        var malo = esInvalido(el, form);
        el.classList.toggle("is-invalid", malo);
        if (malo) el.setAttribute("aria-invalid", "true"); else el.removeAttribute("aria-invalid");
        if (malo && !primero) primero = el;
      });
      if (!primero) return;
      e.preventDefault();
      var alerta = document.getElementById("alerta-form");
      if (alerta) alerta.classList.remove("hidden");
      primero.focus();
      if (primero.scrollIntoView) primero.scrollIntoView({ block: "center", behavior: "smooth" });
    });
  });
})();
