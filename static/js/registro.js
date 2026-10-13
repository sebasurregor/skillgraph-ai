/* Registro: el campo Empresa solo aplica al rol de reclutador. */
(function () {
  var bloque = document.getElementById("bloque-empresa");
  var empresa = document.getElementById("id_empresa");
  var radios = document.querySelectorAll('input[name="rol"]');
  if (!bloque || !empresa) return;

  function actualizar() {
    var marcado = document.querySelector('input[name="rol"]:checked');
    var esReclutador = !!marcado && marcado.value === "reclutador";
    bloque.classList.toggle("hidden", !esReclutador);
    if (esReclutador) empresa.setAttribute("data-obligatorio", "1");
    else empresa.removeAttribute("data-obligatorio");
  }
  radios.forEach(function (r) { r.addEventListener("change", actualizar); });
  actualizar();
})();
