/* Ordena · bandeja. Vanilla JS: lista, ficha, arrastrar y soltar, acciones. */
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

const estado = { vista: "pedidos", filas: [], sel: null, motivos: [], abierto: null };

// ---------- utilidades ----------
async function api(ruta, opciones) {
  const r = await fetch(ruta, opciones);
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch (e) {}
    throw new Error(msg);
  }
  return r.json();
}
function toast(texto) {
  const t = $("#toast"); t.textContent = texto; t.classList.add("ver");
  setTimeout(() => t.classList.remove("ver"), 3200);
}
function fecha(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleDateString("es-ES") + " " + d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
}
function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function chip(e) { return `<span class="estado ${esc(e)}">${esc(e.replace("_", " "))}</span>`; }
function tipoTxt(t) { return ({ pedido: "Pedido", modificacion: "Modificación", consulta: "Consulta", queja: "Queja", comentario: "Comentario", ruido: "Ruido" })[t] || t; }

// ---------- lista ----------
const COLUMNAS = {
  pedidos: ["Nº", "Fecha", "Tipo", "Cliente", "Asunto", "Estado", "Incompleto", "Dudosos", "ERP"],
  otros: ["Nº", "Fecha", "Tipo", "Cliente", "Asunto", "Estado", "Dudosos"],
  mensajes: ["Nº", "Fecha", "Canal", "Remitente", "Archivo", "Estado", "Tickets", "Modelo"],
};

async function cargarLista() {
  const [est, filas] = await Promise.all([
    api("/api/estado"),
    estado.vista === "mensajes" ? api("/api/mensajes") : api(`/api/tickets?familia=${estado.vista}`),
  ]);
  // Solo se repinta si algo ha cambiado: repintar sin motivo rompe el doble clic y la selección.
  const firma = JSON.stringify([estado.vista, est, filas]);
  if (firma === estado.firma) return;
  estado.firma = firma;
  estado.filas = filas;
  pintarEstado(est);
  pintarLista(est);
  actualizarBotones();
}

function pintarEstado(est) {
  const c = est.cuenta || {};
  const pend = (c.pedidos_pendiente || 0), otrosPend = (c.otros_pendiente || 0);
  $("#n-pedidos").textContent = pend ? `(${pend})` : "";
  $("#n-otros").textContent = otrosPend ? `(${otrosPend})` : "";
  $("#n-mensajes").textContent = est.mensajes ? `(${est.mensajes})` : "";
  const filas = [
    ["Pedidos pendientes", pend], ["Validados", c.pedidos_validado || 0], ["Escritos en ERP", c.pedidos_escrito || 0],
    ["Rechazados", c.pedidos_rechazado || 0], ["Otros pendientes", otrosPend], ["Mensajes", est.mensajes],
    ["En cola", est.en_cola], ["Modelo", est.modelo], ["Transcriptor", est.transcriptor],
    ["Business Central", est.bc_configurado ? "configurado" : "sin configurar"], ["Maestros", est.maestros],
  ];
  $("#fb-estado").innerHTML = filas.map(([k, v]) => `<div class="fila"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`).join("")
    + (est.procesando ? `<div class="fila aviso"><span class="k">Procesando</span><span class="v">${esc(est.procesando)} · ${esc(est.fase)}</span></div>` : "");
}

function pintarLista(est) {
  const cols = COLUMNAS[estado.vista];
  $("#rejilla thead").innerHTML = "<tr>" + cols.map((c) => `<th>${c}</th>`).join("") + "</tr>";
  const tb = $("#rejilla tbody");
  let html = "";
  if (est.procesando && estado.vista !== "mensajes") {
    html += `<tr class="proceso"><td colspan="${cols.length}">Ordena está procesando el mensaje ${esc(est.procesando)} (${esc(est.fase)})… el ticket aparecerá aquí.</td></tr>`;
  }
  for (const f of estado.filas) {
    const id = estado.vista === "mensajes" ? f.id : f.id;
    const sel = estado.sel === id ? " sel" : "";
    if (estado.vista === "mensajes") {
      html += `<tr data-id="${esc(id)}" class="${sel}"><td>${f.numero}</td><td>${fecha(f.fecha)}</td><td>${esc(f.canal)}</td><td>${esc(f.remitente || "")}</td><td>${esc(f.nombre_fichero)}</td><td>${chip(f.estado)}${f.error ? ` <span class="dud" title="${esc(f.error)}">⚠</span>` : ""}</td><td>${f.n_tickets}</td><td>${esc(f.etiqueta_modelo || "")}</td></tr>`;
    } else {
      const base = `<td>${esc(f.numero_texto)}</td><td>${fecha(f.fecha_mensaje)}</td><td>${tipoTxt(f.tipo)}</td><td>${esc(f.cliente_valor ? f.cliente_valor + " · " + (f.cliente_etiqueta || "") : "—")}</td><td title="${esc(f.asunto)}">${esc(f.asunto)}</td><td>${chip(f.estado)}</td>`;
      if (estado.vista === "pedidos") {
        const erp = f.erp_url ? `<a class="link" href="${esc(f.erp_url)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${esc(f.erp_numero)}</a>` : esc(f.erp_numero || "");
        html += `<tr data-id="${esc(id)}" class="${sel}">${base}<td>${f.incompleto ? '<span class="aviso">sí</span>' : ""}</td><td>${f.n_dudosos || ""}</td><td>${erp}</td></tr>`;
      } else {
        html += `<tr data-id="${esc(id)}" class="${sel}">${base}<td>${f.n_dudosos || ""}</td></tr>`;
      }
    }
  }
  if (!estado.filas.length && !est.procesando) html += `<tr><td colspan="${cols.length}" style="color:#6b7c8f">Nada por aquí todavía.</td></tr>`;
  tb.innerHTML = html;
  $$("#rejilla tbody tr[data-id]").forEach((tr) => {
    tr.onclick = () => seleccionar(tr.dataset.id);
    tr.ondblclick = () => { if (estado.vista !== "mensajes") abrirFicha(tr.dataset.id); };
  });
}

function filaSel() { return estado.filas.find((f) => f.id === estado.sel); }

function actualizarBotones() {
  const f = estado.vista === "mensajes" ? null : filaSel();
  const pedido = f && f.familia === "pedidos";
  $("#btn-ver").disabled = !f;
  $("#btn-validar").disabled = !(pedido && f.estado === "pendiente");
  $("#btn-rechazar").disabled = !(pedido && f.estado === "pendiente");
  $("#btn-cerrar").disabled = !(f && f.familia === "otros" && f.estado === "pendiente");
  $("#btn-escribir").disabled = !(pedido && f.estado === "validado");
}

async function seleccionar(id) {
  estado.sel = id;
  $$("#rejilla tbody tr").forEach((tr) => tr.classList.toggle("sel", tr.dataset.id === id));
  actualizarBotones();
  if (estado.vista === "mensajes") return;
  try {
    const d = await api(`/api/tickets/${id}`);
    pintarOriginal(d);
    $("#fb-dudosos").innerHTML = (d.ticket.dudosos || []).map((x) => `<div class="fila"><span class="dud">⚠ ${esc(x)}</span></div>`).join("") || `<span style="color:#6b7c8f">Sin dudosos.</span>`;
  } catch (e) { toast(e.message); }
}

function pintarOriginal(d) {
  const m = d.mensaje;
  let html = `<div class="fila"><span class="k">Mensaje</span><span class="v">${esc(m.id)} · ${esc(m.canal)}</span></div>`;
  html += `<div class="fila"><span class="k">Fecha</span><span class="v">${fecha(m.fecha)}</span></div>`;
  html += `<div class="fila"><span class="k">Remitente</span><span class="v">${esc(m.remitente || "desconocido")}</span></div>`;
  html += `<div class="fila"><span class="k">Modelo</span><span class="v">${esc(m.etiqueta_modelo || "")}</span></div>`;
  if (m.canal === "audio") html += `<audio controls src="/api/originales/${esc(m.id)}"></audio>`;
  if (m.transcripcion) {
    html += `<div class="texto">` + m.transcripcion.segmentos.map((s) => `<span class="seg${s.dudoso ? " dudoso" : ""}" title="${s.inicio}s">${esc(s.texto)} </span>`).join("") + `</div>`;
    html += `<div class="hist">${esc(m.transcripcion.modelo)} · ${m.transcripcion.duracion}s</div>`;
  } else {
    html += `<div class="texto">${esc(m.texto)}</div>`;
  }
  $("#fb-original").innerHTML = html;
}

// ---------- ficha (ventana hija) ----------
function campo(c, k) {
  const dud = c && c.dudoso ? " dud" : "";
  let v = "";
  if (c && c.valor) v = `<span class="link">${esc(c.valor)}</span>${c.etiqueta && c.etiqueta !== c.valor ? " · " + esc(c.etiqueta) : ""}${c.puntuacion != null && c.puntuacion < 100 ? ` <span style="color:#6b7c8f">(${Math.round(c.puntuacion)})</span>` : ""}`;
  else if (c && c.tal_cual) v = `<i>${esc(c.tal_cual)}</i>`;
  else v = "—";
  if (c && c.motivo) v += ` <span style="color:#a05a00;font-size:11px">${c.dudoso ? "⚠ " : ""}${esc(c.motivo)}</span>`;
  return `<div class="k">${esc(k)}:</div><div class="v ro${dud}">${v}</div>`;
}

async function abrirFicha(id) {
  let d;
  try { d = await api(`/api/tickets/${id}`); } catch (e) { toast(e.message); return; }
  estado.abierto = d;
  const t = d.ticket;
  $("#titulo-ticket").textContent = `Editar - Ticket - ${d.numero_texto} · ${tipoTxt(t.tipo)}`;
  const inc = t.incompleto && t.incompleto.length ? `<span class="aviso">INCOMPLETO: falta ${esc(t.incompleto.join(", "))}</span>` : "";
  let html = `<div class="pagina-titulo" style="padding:8px 12px 0">${esc(d.numero_texto)} · ${esc(t.asunto)}</div>
    <div class="subtitulo" style="padding:0 12px 4px">${chip(d.estado)} ${t.exige_validacion ? "exige validación" : "informativo"} · confianza ${(t.confianza ?? 0).toFixed(2)} ${inc}${d.erp_numero ? ` · <b>ERP ${d.erp_url ? `<a class="link" href="${esc(d.erp_url)}" target="_blank" rel="noopener">${esc(d.erp_numero)}</a>` : esc(d.erp_numero)}</b>` : ""}</div>`;
  html += `<div class="fasttab"><div class="ft-cab">General <span class="chev">▴</span></div><div class="ft-cuerpo"><div class="campos">
    <div class="k">Nº ticket:</div><div class="v ro">${esc(d.numero_texto)} <span style="color:#6b7c8f">(${esc(t.id)})</span></div>
    <div class="k">Tipo:</div><div class="v ro">${tipoTxt(t.tipo)}</div>
    ${campo(t.cliente, "Nº cliente")}
    <div class="k">Contacto:</div><div class="v ro">${esc(t.contacto || "—")}</div>
    ${campo(t.direccion_entrega, "Dirección entrega")}
    ${campo(t.fecha_entrega, "Fecha entrega")}
    <div class="k">Ref. cliente:</div><div class="v ro">${esc(t.referencia_cliente || "—")}</div>
    <div class="k">Fecha mensaje:</div><div class="v ro">${fecha(d.mensaje.fecha)}</div>
    ${d.familia === "pedidos" ? `<div class="k">Pedido ERP:</div><div class="v ro">${d.erp_url ? `<a class="link" href="${esc(d.erp_url)}" target="_blank" rel="noopener">${esc(d.erp_numero)}</a> <span style="color:#6b7c8f">sin registrar, con el original adjunto</span>` : "—"}</div><div></div><div></div>` : ""}
    ${t.se_refiere_a && t.se_refiere_a.tal_cual ? campo(t.se_refiere_a, "Se refiere a") : ""}
    <div class="k">Resumen:</div><div class="v ro" style="grid-column:2 / span 3">${esc(t.resumen)}</div>
    ${t.observaciones ? `<div class="k">Observaciones:</div><div class="v ro" style="grid-column:2 / span 3">${esc(t.observaciones)}</div>` : ""}
    ${t.hermanos && t.hermanos.length ? `<div class="k">Hermanos:</div><div class="v ro" style="grid-column:2 / span 3">${esc(t.hermanos.join(", "))}</div>` : ""}
  </div></div></div>`;
  if (t.lineas && t.lineas.length) {
    html += `<div class="fasttab"><div class="ft-cab">Líneas <span class="chev">▴</span></div><div class="ft-cuerpo"><table class="rejilla lineas"><thead><tr><th>#</th><th>Tal cual</th><th>Cantidad</th><th>Unidad</th><th>Nº artículo</th><th>Descripción</th><th>Tarifa</th><th></th></tr></thead><tbody>`;
    t.lineas.forEach((l, i) => {
      const a = l.articulo, u = l.unidad;
      html += `<tr><td>${i + 1}</td><td><i>${esc(l.original.descripcion_tal_cual)}</i></td><td class="num">${l.cantidad != null ? l.cantidad : '<span class="aviso">?</span>'}</td><td>${esc(u.valor || u.tal_cual || "—")}${u.dudoso ? ' <span class="dud">⚠</span>' : ""}</td><td>${a.valor ? `<span class="link">${esc(a.valor)}</span>` : "—"}</td><td>${esc(a.etiqueta || "")}${a.puntuacion != null && a.puntuacion < 100 ? ` <span style="color:#6b7c8f">(${Math.round(a.puntuacion)})</span>` : ""}</td><td class="num">${l.precio_tarifa != null ? l.precio_tarifa.toFixed(2) : "—"}</td><td>${l.dudoso ? `<span class="dud">⚠ ${esc(a.dudoso ? a.motivo || "" : u.dudoso ? u.motivo || "" : "")}</span>` : ""}</td></tr>`;
    });
    html += `</tbody></table></div></div>`;
  }
  html += `<div class="fasttab"><div class="ft-cab">Comentarios (dudosos) <span class="chev">▴</span></div><div class="ft-cuerpo">${(t.dudosos || []).map((x) => `<div class="dud">⚠ ${esc(x)}</div>`).join("") || '<span style="color:#6b7c8f">Sin dudosos.</span>'}</div></div>`;
  const m = d.mensaje;
  html += `<div class="fasttab"><div class="ft-cab">Original <span class="chev">▴</span></div><div class="ft-cuerpo">`;
  if (m.canal === "audio") html += `<audio controls src="/api/originales/${esc(m.id)}" style="width:100%"></audio>`;
  if (m.transcripcion) html += `<div class="texto" style="margin-top:6px">` + m.transcripcion.segmentos.map((s) => `<span class="seg${s.dudoso ? " dudoso" : ""}" title="${s.inicio}s">${esc(s.texto)} </span>`).join("") + `</div><div class="hist">${esc(m.transcripcion.modelo)}</div>`;
  else html += `<div class="texto">${esc(m.texto)}</div>`;
  html += `</div></div>`;
  html += `<div class="fasttab"><div class="ft-cab">Historial <span class="chev">▴</span></div><div class="ft-cuerpo hist">${d.historial.map((h) => `${fecha(h.cuando)} · ${esc(h.quien)} · ${esc(h.accion)}${h.detalle ? " · " + esc(h.detalle) : ""}`).join("<br>")}</div></div>`;
  $("#ficha").innerHTML = html;

  const pedido = d.familia === "pedidos";
  $("#ft-validar").disabled = !(pedido && d.estado === "pendiente");
  $("#ft-rechazar").disabled = !(pedido && d.estado === "pendiente");
  $("#ft-cerrar").disabled = !(!pedido && d.estado === "pendiente");
  $("#ft-escribir").disabled = !(pedido && d.estado === "validado");
  $("#ft-abrir-bc").disabled = !d.erp_url;
  $("#ventana-ticket").classList.add("abierta");
}

function cerrarFicha() { $("#ventana-ticket").classList.remove("abierta"); estado.abierto = null; }

async function accion(id, acc) {
  let motivo = null;
  if (acc === "rechazar") {
    const lista = estado.motivos.map((m, i) => `${i + 1}. ${m}`).join("\n");
    const r = prompt(`Motivo de rechazo (número o texto):\n${lista}`);
    if (r == null || !r.trim()) return;
    const n = parseInt(r, 10);
    motivo = n >= 1 && n <= estado.motivos.length ? estado.motivos[n - 1] : r.trim();
  }
  try {
    const res = await api(`/api/tickets/${id}/${acc}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ motivo }) });
    toast(`${id}: ${res.estado}${res.detalle ? " · " + res.detalle : ""}`);
  } catch (e) { toast("No se pudo: " + e.message); }
  estado.firma = null;
  await cargarLista();
  if (estado.abierto && estado.abierto.ticket.id === id) abrirFicha(id);
}

// ---------- entrada: arrastrar y soltar, archivo, texto ----------
async function subir(archivos) {
  for (const f of archivos) {
    const fd = new FormData();
    fd.append("fichero", f, f.name);
    try {
      const r = await api("/api/mensajes", { method: "POST", body: fd });
      toast(r.duplicado ? `${f.name}: ya existía como ${r.id} (duplicado exacto)` : `${f.name}: recibido como ${r.id}, en cola`);
    } catch (e) { toast(`${f.name}: ${e.message}`); }
  }
  cargarLista();
}

function preparar() {
  const zona = $("#zona-drop");
  ["dragenter", "dragover"].forEach((ev) => document.addEventListener(ev, (e) => { e.preventDefault(); zona.classList.add("encima"); }));
  ["dragleave", "drop"].forEach((ev) => document.addEventListener(ev, (e) => { e.preventDefault(); if (ev === "drop" || e.target === document.documentElement) zona.classList.remove("encima"); }));
  document.addEventListener("drop", (e) => { if (e.dataTransfer.files.length) subir(e.dataTransfer.files); });
  $("#enlace-archivo").onclick = () => $("#input-archivo").click();
  $("#btn-archivo").onclick = () => $("#input-archivo").click();
  $("#input-archivo").onchange = (e) => { subir(e.target.files); e.target.value = ""; };

  $("#btn-nuevo").onclick = () => { $("#ventana-nuevo").classList.add("abierta"); $("#nuevo-texto").focus(); };
  $("#cerrar-nuevo").onclick = $("#cancelar-nuevo").onclick = () => $("#ventana-nuevo").classList.remove("abierta");
  $("#enviar-nuevo").onclick = async () => {
    const texto = $("#nuevo-texto").value, remitente = $("#nuevo-remitente").value, f = $("#nuevo-fecha").value;
    try {
      const r = await api("/api/mensajes/texto", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ texto, remitente: remitente || null, fecha: f || null }) });
      toast(r.duplicado ? `Ya existía como ${r.id}` : `Recibido como ${r.id}, en cola`);
      $("#ventana-nuevo").classList.remove("abierta"); $("#nuevo-texto").value = "";
      cargarLista();
    } catch (e) { toast(e.message); }
  };

  $$("[data-vista]").forEach((el) => el.onclick = () => cambiarVista(el.dataset.vista));
  $("#btn-refrescar").onclick = cargarLista;
  $("#btn-ver").onclick = () => estado.sel && abrirFicha(estado.sel);
  $("#btn-validar").onclick = () => accion(estado.sel, "validar");
  $("#btn-rechazar").onclick = () => accion(estado.sel, "rechazar");
  $("#btn-cerrar").onclick = () => accion(estado.sel, "cerrar");
  $("#btn-escribir").onclick = () => accion(estado.sel, "escribir");
  $("#ft-validar").onclick = () => accion(estado.abierto.ticket.id, "validar");
  $("#ft-rechazar").onclick = () => accion(estado.abierto.ticket.id, "rechazar");
  $("#ft-cerrar").onclick = () => accion(estado.abierto.ticket.id, "cerrar");
  $("#ft-escribir").onclick = () => accion(estado.abierto.ticket.id, "escribir");
  $("#ft-abrir-bc").onclick = () => { if (estado.abierto && estado.abierto.erp_url) window.open(estado.abierto.erp_url, "_blank", "noopener"); };
  $("#ok-ticket").onclick = $("#cerrar-ticket").onclick = cerrarFicha;
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { cerrarFicha(); $("#ventana-nuevo").classList.remove("abierta"); } });
}

function cambiarVista(v) {
  estado.vista = v; estado.sel = null; estado.firma = null;
  $$("[data-vista]").forEach((el) => el.classList.toggle("activa", el.dataset.vista === v));
  $$(".panel-nav .item").forEach((el) => el.classList.toggle("activo", el.dataset.vista === v));
  $("#titulo-lista").textContent = { pedidos: "Tickets de pedido", otros: "Otros tickets", mensajes: "Mensajes" }[v];
  $("#subtitulo-lista").textContent = { pedidos: "Exigen validación: pedidos y modificaciones. Doble clic abre la ficha.", otros: "Informativos: consultas, quejas, comentarios y ruido. Se leen y se cierran.", mensajes: "Todo lo que ha entrado, con su estado de proceso. Nada se borra." }[v];
  $("#fb-original").innerHTML = `<span style="color:#6b7c8f">Selecciona un ticket.</span>`; $("#fb-dudosos").innerHTML = "";
  cargarLista();
}

(async function init() {
  preparar();
  try { estado.motivos = await api("/api/motivos"); } catch (e) {}
  cambiarVista("pedidos");
  setInterval(() => { if (!estado.abierto) cargarLista(); }, 2500);
})();
