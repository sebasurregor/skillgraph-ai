/* Prueba de humo del prototipo: recorre el flujo completo en un DOM simulado
   y falla si alguna pantalla no aparece o si se lanza un error de JavaScript. */
const fs = require("fs");
const { JSDOM } = require("jsdom");

const html = fs.readFileSync(__dirname + "/index.html", "utf8");
const errores = [];

const dom = new JSDOM(html, {
  runScripts: "dangerously",
  pretendToBeVisual: true,
  virtualConsole: new (require("jsdom").VirtualConsole)()
    .on("jsdomError", e => errores.push("jsdomError: " + e.message))
    .on("error", (...a) => errores.push("console.error: " + a.join(" "))),
  // El canvas no existe en jsdom: se neutraliza ANTES de que corra el script.
  beforeParse(w){
    w.HTMLCanvasElement.prototype.getContext = () => ({
      clearRect(){}, beginPath(){}, moveTo(){}, lineTo(){}, stroke(){}, arc(){}, fill(){},
      set strokeStyle(v){}, set fillStyle(v){}, set lineWidth(v){}
    });
  }
});

const { window } = dom;
const doc = window.document;
const $ = s => doc.querySelector(s);

const visible = id => !$(id).classList.contains("hidden");
const pantalla = () => ["#s-email","#s-password","#s-signup","#s-quiz","#s-profile","#s-app"]
  .find(visible) || "(ninguna)";

let ok = 0, fallos = 0;
function check(desc, cond, extra=""){
  if(cond){ ok++; console.log("  OK   " + desc); }
  else { fallos++; console.log("  FALLA " + desc + (extra ? "  → " + extra : "")); }
}
function click(sel){
  const el = $(sel);
  if(!el){ fallos++; console.log("  FALLA no existe el elemento " + sel); return; }
  el.dispatchEvent(new window.Event("click", {bubbles:true}));
}
function submit(sel){ $(sel).dispatchEvent(new window.Event("submit", {bubbles:true, cancelable:true})); }
function setVal(sel, v){ $(sel).value = v; }

setTimeout(() => {
  console.log("\n=== 1. Estado inicial ===");
  check("arranca en la pantalla de correo", pantalla() === "#s-email", pantalla());

  console.log("\n=== 2. Correo inexistente → registro ===");
  setVal("#i-email", "nuevo.usuario@correo.com");
  submit("#form-email");
  check("lleva a la pantalla de registro", pantalla() === "#s-signup", pantalla());
  check("prellena el correo digitado", $("#i-mail2").value === "nuevo.usuario@correo.com");

  console.log("\n=== 3. Validación de campos obligatorios ===");
  submit("#form-signup");
  check("muestra la alerta con la microcopia exigida",
        !$("#su-alert").classList.contains("hidden") &&
        $("#su-alert").textContent.includes("Favor ingresar información válida"));
  check("conserva el correo ya digitado", $("#i-mail2").value === "nuevo.usuario@correo.com");
  check("resalta en rojo el primer campo pendiente", $("#i-nom").classList.contains("is-invalid"));
  check("sigue en la pantalla de registro", pantalla() === "#s-signup", pantalla());

  console.log("\n=== 4. Registro completo → cuestionario ===");
  setVal("#i-nom","Camilo"); setVal("#i-ape","Zapata Ospina");
  setVal("#i-tel","3109876543"); $("#i-ciudad").value = "Medellín";
  setVal("#i-pw1","clave12345"); setVal("#i-pw2","clave12345");
  $("#i-hab").checked = true;
  submit("#form-signup");
  check("tras crear la cuenta lleva al inicio de sesión", pantalla() === "#s-password", pantalla());
  check("confirma la creación de la cuenta",
        $("#pw-alert").textContent.includes("creada correctamente"));
  check("muestra el correo registrado", $("#pw-email-echo").textContent === "nuevo.usuario@correo.com");
  setVal("#i-pw","clave12345");
  submit("#form-pw");
  check("la cuenta recién creada permite iniciar sesión", pantalla() === "#s-quiz", pantalla());
  check("renderiza las 10 preguntas", doc.querySelectorAll("#quiz-body .q-block").length === 10,
        doc.querySelectorAll("#quiz-body .q-block").length + " bloques");
  check("muestra las habilidades transversales sin elegir sector",
        doc.querySelectorAll("#skill-picker .chip").length >= 8);

  console.log("\n=== 5. El sector cambia las habilidades ofrecidas ===");
  const antes = doc.querySelectorAll("#skill-picker .chip").length;
  click('#quiz-body .opt[data-q="sector"][data-v="Logística y bodega"]');
  const despues = doc.querySelectorAll("#skill-picker .chip").length;
  check("aparecen habilidades propias del sector", despues > antes, antes + " → " + despues);
  check("incluye una habilidad de bodega",
        [...doc.querySelectorAll("#skill-picker .chip")].some(c => c.dataset.skill === "Picking y packing"));
  check("NO incluye habilidades de otro sector",
        ![...doc.querySelectorAll("#skill-picker .chip")].some(c => c.dataset.skill === "Colorimetría"));

  console.log("\n=== 6. Declarar habilidades y nivel ===");
  ["Trabajo en equipo","Puntualidad","Picking y packing"].forEach(sk =>
    click(`#skill-picker .chip[data-skill="${sk}"]`));
  check("registra las 3 habilidades", Object.keys(window.SkillGraph.state.skills).length === 3,
        JSON.stringify(window.SkillGraph.state.skills));
  check("aparece el selector de nivel", doc.querySelectorAll("#skill-levels .lvl").length === 3);
  click('#skill-levels .lvl button[data-s="Puntualidad"][data-n="5"]');
  check("guarda el nivel elegido", window.SkillGraph.state.skills["Puntualidad"] === 5);
  check("dibuja el grafo en vivo", doc.querySelectorAll("#live-graph circle").length > 1);

  console.log("\n=== 7. Bloqueo por preguntas sin responder ===");
  click("#quiz-next");
  check("no deja avanzar y avisa", pantalla() === "#s-quiz" &&
        !$("#quiz-alert").classList.contains("hidden"));

  console.log("\n=== 8. Responder todo → perfil ===");
  [["experiencia","Menos de 1 año"],["jornada","Temporal o por temporada"],
   ["modalidad","Presencial"],["salario","Hasta $1.500.000"],
   ["disponibilidad","Inmediatamente"],["requisitos","Libreta militar"],
   ["prioridad","El salario"]].forEach(([q,v]) =>
    click(`#quiz-body .opt[data-q="${q}"][data-v="${v}"]`));
  click('#learn-picker .chip[data-learn="Nada por ahora"]');
  click("#quiz-next");
  check("entra a la pantalla de perfil", pantalla() === "#s-profile", pantalla());
  check("prellena el nombre", $("#p-nombre").value === "Camilo Zapata Ospina");

  console.log("\n=== 9. Perfil: exige hoja de vida ===");
  setVal("#p-nac","2003-05-12"); $("#p-tipodoc").value = "Cédula de ciudadanía";
  setVal("#p-doc","1035784412"); setVal("#p-dir","Calle 78 # 45-12");
  setVal("#p-ciudad","Medellín"); $("#p-edu").value = "Bachiller"; setVal("#p-anios","0");
  submit("#form-profile");
  check("bloquea sin hoja de vida", pantalla() === "#s-profile" &&
        $("#prof-alert").textContent.includes("hoja de vida"));

  window.SkillGraph.state.docs.cv = { nombre:"hv.pdf", kb:120 };
  submit("#form-profile");
  check("entra a la aplicación", pantalla() === "#s-app", pantalla());
  check("abre en la pestaña de búsqueda", !$("#tab-search").classList.contains("hidden"));
  check("lista vacantes", doc.querySelectorAll("#jobs .job").length > 0,
        doc.querySelectorAll("#jobs .job").length + " tarjetas");

  console.log("\n=== 10. Navegación del rail ===");
  click('.rail-btn[data-tab="saved"]');
  check("abre guardados", !$("#tab-saved").classList.contains("hidden"));
  click('.rail-btn[data-tab="settings"]');
  check("abre ajustes", !$("#tab-settings").classList.contains("hidden"));
  click('#settings-tabs .tab[data-st="app"]');
  click("#sw-dark");
  check("activa el modo oscuro", doc.documentElement.dataset.theme === "dark");
  click("#sw-dark");
  check("vuelve al modo claro", doc.documentElement.dataset.theme === "light");
  click('.rail-btn[data-tab="search"]');
  check("regresa a búsqueda con la lupa", !$("#tab-search").classList.contains("hidden"));

  console.log("\n=== 11. Guardar con el corazón ===");
  const primera = doc.querySelector("#jobs [data-like]");
  click(`#jobs [data-like="${primera.dataset.like}"]`);
  check("marca la vacante", window.SkillGraph.state.guardadas.size === 1);
  check("muestra el contador", !$("#saved-badge").classList.contains("hidden"));

  console.log("\n=== 12. Explicabilidad ===");
  const idw = doc.querySelector("#jobs [data-why]").dataset.why;
  click(`#jobs [data-why="${idw}"]`);
  check("despliega el desglose", !$("#ex-"+idw).classList.contains("hidden"));
  check("muestra los 4 componentes", $("#ex-"+idw).querySelectorAll(".comp").length === 5);
  check("dibuja el subgrafo", $("#ex-"+idw).querySelectorAll(".mini-graph svg rect").length > 0);

  console.log("\n=== 13. Búsqueda e historial ===");
  setVal("#q","mesero"); click("#btn-search");
  check("filtra resultados", doc.querySelectorAll("#jobs .job").length > 0 &&
        doc.querySelectorAll("#jobs .job").length < 16);
  check("registra la búsqueda reciente",
        [...doc.querySelectorAll("#recents-list .chip")].some(c => c.dataset.r === "mesero"));

  console.log("\n=== 14. Login con cuenta existente ===");
  click('.rail-btn[data-tab="settings"]');
  click('#settings-tabs .tab[data-st="cuenta"]');
  click("#logout");
  check("cierra sesión y vuelve al correo", pantalla() === "#s-email", pantalla());
  setVal("#i-email","ana.rios@correo.com");
  submit("#form-email");
  check("pide contraseña porque la cuenta existe", pantalla() === "#s-password", pantalla());
  setVal("#i-pw","incorrecta");
  submit("#form-pw");
  check("rechaza credenciales inválidas", pantalla() === "#s-password" &&
        $("#pw-alert").textContent.includes("no coinciden"));
  setVal("#i-pw","skillgraph2026");
  submit("#form-pw");
  check("inicia sesión y entra al cuestionario", pantalla() === "#s-quiz", pantalla());

  console.log("\n=== 15. Atajos de demostración ===");
  window.dispatchEvent(new window.KeyboardEvent("keydown", {key:"d", altKey:true}));
  check("Alt+D salta a la aplicación", pantalla() === "#s-app", pantalla());
  const pctAna = [...doc.querySelectorAll("#jobs .ring b")].map(b => parseInt(b.textContent));
  check("Ana María obtiene 82 % en su mejor vacante", Math.max(...pctAna) === 82,
        "máximo " + Math.max(...pctAna) + " %");
  window.dispatchEvent(new window.KeyboardEvent("keydown", {key:"n", altKey:true}));
  const pctCam = [...doc.querySelectorAll("#jobs .ring b")].map(b => parseInt(b.textContent));
  check("Alt+N carga el perfil de temporada", pantalla() === "#s-app" && Math.max(...pctCam) === 53,
        "máximo " + Math.max(...pctCam) + " %");

  console.log("\n" + "=".repeat(56));
  console.log(`RESULTADO: ${ok} correctas · ${fallos} fallidas`);
  if(errores.length){
    console.log("\nErrores de JavaScript capturados:");
    [...new Set(errores)].forEach(e => console.log("  ! " + e.split("\n")[0]));
  } else {
    console.log("Sin errores de JavaScript.");
  }
  process.exit(fallos || errores.length ? 1 : 0);
}, 400);
