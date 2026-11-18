const $ = (id) => document.getElementById(id);
let modelInfo = null;
let toastTimer;

function notify(message) {
  const el = $("toast"); el.textContent = message; el.classList.add("show");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove("show"), 2800);
}
function safeText(value) { return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
function formatMetric(value) {
  if (value === null || value === undefined) return "—";
  return Number(value).toFixed(3).replace(/0+$/,"").replace(/\.$/,"");
}
async function api(path, options={}) {
  const response = await fetch(path, options);
  let data = {};
  try { data = await response.json(); } catch (_) {}
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map(x => x.msg).join("; ") : (data.detail || `Error HTTP ${response.status}`);
    throw new Error(detail);
  }
  return data;
}
function fieldMarkup(c) {
  const id = `field-${c.nombre}`;
  if (c.tipo === "lista") {
    return `<div class="field full"><label for="${id}">${safeText(c.etiqueta)}<small>OBLIGATORIO</small></label><select id="${id}" name="${safeText(c.nombre)}" data-kind="lista" required>${(c.opciones || []).map(o=>`<option value="${safeText(o)}" ${o===c.ejemplo?"selected":""}>${safeText(o)}</option>`).join("")}</select><span class="field-hint">Selecciona el sector GICS al que pertenece la empresa.</span></div>`;
  }
  if (c.tipo === "booleano") {
    const optional = c.opcional ? "Automático (recomendado)" : "No";
    return `<div class="field"><label for="${id}">${safeText(c.etiqueta)}<small>OPCIONAL</small></label><select id="${id}" name="${safeText(c.nombre)}" data-kind="booleano"><option value="">${optional}</option><option value="true">Sí</option><option value="false">No</option></select><span class="field-hint">${safeText(c.nota || "Dato complementario de la empresa.")}</span></div>`;
  }
  const unit = c.unidad || "";
  const range = `Rango típico: ${formatMetric(c.minimo_tipico)} a ${formatMetric(c.maximo_tipico)}`;
  const example = c.ejemplo ?? "";
  return `<div class="field"><label for="${id}">${safeText(c.etiqueta)}<small>${safeText(unit)}</small></label><input id="${id}" name="${safeText(c.nombre)}" data-kind="numero" type="number" step="any" value="${safeText(example)}" placeholder="Deja vacío para usar mediana"><span class="field-hint">${range}</span></div>`;
}
function renderFields(info) {
  const numeric = info.campos.filter(c => c.tipo === "numero");
  const categorical = info.campos.filter(c => c.tipo !== "numero");
  $("numeric-fields").innerHTML = numeric.map(fieldMarkup).join("");
  $("categorical-fields").innerHTML = categorical.map(fieldMarkup).join("");
}
async function initialize() {
  try {
    const [info, health] = await Promise.all([api("/api/info"), api("/api/health")]);
    modelInfo = info;
    $("project-name").textContent = info.proyecto || "Proyecto de clasificación financiera";
    $("project-description").textContent = info.descripcion || info.proyecto || "Proyecto de clasificación financiera.";
    $("model-name").textContent = info.modelo || "Modelo de clasificación";
    const metrics = info.metricas_prueba || {};
    const metric = (key) => Number.isFinite(Number(metrics[key])) ? Number(metrics[key]).toFixed(3) : "—";
    $("auc-value").textContent = metric("ROC-AUC");
    $("f1-value").textContent = metric("F1-Score");
    $("accuracy-value").textContent = metrics.Accuracy != null ? `${(Number(metrics.Accuracy) * 100).toFixed(1)}%` : "—";
    $("precision-value").textContent = metrics.Precision != null ? `${(Number(metrics.Precision) * 100).toFixed(1)}%` : "—";
    $("recall-value").textContent = metrics.Recall != null ? `${(Number(metrics.Recall) * 100).toFixed(1)}%` : "—";
    const target = info.que_predice || {};
    $("target-one-text").textContent = target["1"] || "La acción supera a RSP en 12 meses";
    $("target-zero-text").textContent = target["0"] || "La acción no supera a RSP en 12 meses";
    const training = info.entrenamiento || {};
    $("split-description").textContent = training.anio_corte != null ? `Entrenamiento hasta ${training.anio_corte} · Prueba desde ${Number(training.anio_corte) + 1}` : "Validación temporal";
    $("test-records").textContent = training.filas_prueba != null ? Number(training.filas_prueba).toLocaleString("es-EC") : "—";
    const estimators = info.hiperparametros?.n_estimators;
    $("estimators").textContent = estimators != null ? `${estimators} árboles` : "Random Forest";
    $("model-warning").textContent = info.advertencia || "Las predicciones son estimaciones estadísticas.";
    $("system-state").textContent = "API conectada";
    $("system-source").textContent = health.fuente_modelo || "Modelo disponible";
    renderFields(info);
  } catch (error) {
    $("system-state").textContent = "API no disponible";
    $("system-source").textContent = "Revisa el backend FastAPI";
    $("numeric-fields").innerHTML = `<div class="request-error">No fue posible cargar los campos del modelo: ${safeText(error.message)}. Comprueba que FastAPI esté ejecutándose y vuelve a cargar la página.</div>`;
    $("categorical-fields").innerHTML = "";
  }
}
function collectPayload() {
  const data = {};
  document.querySelectorAll("#prediction-form [name]").forEach(el => {
    const kind = el.dataset.kind;
    if (kind === "numero") data[el.name] = el.value.trim() === "" ? null : Number(el.value);
    else if (kind === "booleano") { if (el.value !== "") data[el.name] = el.value === "true"; }
    else data[el.name] = el.value;
  });
  return data;
}
function showResult(result) {
  const panel = document.querySelector(".result-panel");
  panel.classList.remove("favorable","desfavorable","incierto");
  panel.classList.add(result.nivel);
  $("empty-result").hidden = true;
  $("request-error").hidden = true;
  $("result-content").hidden = false;
  const pct = Number(result.probabilidad_supera_pct);
  $("probability-value").textContent = pct.toFixed(2);
  $("probability-bar").style.width = `${Math.max(0,Math.min(100,pct))}%`;
  $("result-level").textContent = result.nivel === "favorable" ? "SEÑAL FAVORABLE" : result.nivel === "desfavorable" ? "SEÑAL DESFAVORABLE" : "ZONA DE INCERTIDUMBRE";
  $("result-tag").textContent = result.nivel.toUpperCase();
  $("verdict-title").textContent = result.resultado;
  $("verdict-text").textContent = result.interpretacion;
  $("verdict-icon").textContent = result.nivel === "favorable" ? "↗" : result.nivel === "desfavorable" ? "↘" : "≈";
  $("yes-prob").textContent = `${Number(result.probabilidad_supera_pct).toFixed(2)} %`;
  $("no-prob").textContent = `${(Number(result.probabilidad_no_supera)*100).toFixed(2)} %`;
  $("result-model").textContent = result.modelo;
  $("model-disclaimer").textContent = result.aviso_modelo || "Uso académico. No constituye asesoría financiera.";
  const warnings = result.advertencias || [];
  $("warnings").hidden = warnings.length === 0;
  $("warnings").innerHTML = warnings.length ? `<b>⚠ OBSERVACIONES DEL PROCESAMIENTO</b><ul>${warnings.map(w=>`<li>${safeText(w)}</li>`).join("")}</ul>` : "";
}
$("prediction-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!modelInfo) { notify("La información del modelo aún no está disponible."); return; }
  const payload = collectPayload();
  if (!payload.Sector) { notify("Selecciona el sector de la empresa."); return; }
  if (["Revenue_Growth","Net_Income","Profit_Margin","Debt_to_Equity","PE_Ratio"].every(k => payload[k] === null)) {
    notify("Ingresa al menos uno de los cinco indicadores financieros."); return;
  }
  const button = $("predict-button"); button.disabled = true;
  button.querySelector("span").textContent = "Procesando modelo...";
  $("request-error").hidden = true;
  try {
    const result = await api("/api/predict", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    showResult(result);
    notify("Predicción generada correctamente.");
    if (window.innerWidth < 900) $("result-content").scrollIntoView({behavior:"smooth",block:"start"});
  } catch (error) {
    $("result-content").hidden = true; $("empty-result").hidden = true;
    $("request-error").hidden = false;
    $("request-error").textContent = `No se pudo generar la predicción. ${error.message}`;
  } finally {
    button.disabled = false; button.querySelector("span").textContent = "Ejecutar predicción";
  }
});
$("load-example").addEventListener("click", async () => {
  try {
    const example = await api("/api/ejemplo");
    Object.entries(example).forEach(([key,value]) => {
      const el = document.querySelector(`[name="${CSS.escape(key)}"]`);
      if (el) el.value = value ?? "";
    });
    notify("Ejemplo de entrada cargado.");
  } catch (error) { notify(`No se pudo cargar el ejemplo: ${error.message}`); }
});
initialize();
