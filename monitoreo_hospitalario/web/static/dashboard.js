const socket = io();

const UMBRALES = { temp: 28.0, humedad: 70.0, co2_ppm: 1000 };
const MAX_PUNTOS_GRAFICA = 30;

// Paleta de colores por cuarto (mismo estilo que la ventana de matplotlib)
const PALETA = ["#4C8DFF", "#FF9F40", "#4CAF50", "#E23B3B", "#B983FF", "#FFD45C", "#39C0C8", "#FF6FA5"];
function colorDeCuarto(cuartoId) {
  return PALETA[(cuartoId - 1) % PALETA.length];
}

// ---------- Estado ----------
const cuartosConocidos = new Set();
const cuartosEnAlerta = new Set();

// ---------- Gráfica de temperatura (todos los cuartos) ----------
const ctx = document.getElementById("grafica-temp").getContext("2d");
const grafica = new Chart(ctx, {
  type: "line",
  data: { datasets: [] },
  options: {
    responsive: true,
    parsing: false,   // usamos puntos {x, y} directos, más simple y confiable
    scales: {
      x: {
        type: "linear",
        title: { display: true, text: "Lectura #", color: "#b9c2dd" },
        ticks: { color: "#b9c2dd" }, grid: { color: "rgba(255,255,255,0.05)" }
      },
      y: {
        title: { display: true, text: "Temperatura (°C)", color: "#b9c2dd" },
        ticks: { color: "#b9c2dd" }, grid: { color: "rgba(255,255,255,0.05)" }
      }
    },
    plugins: { legend: { labels: { color: "#f4f6fb" } } }
  }
});
const contadorPorCuarto = {};   // cuarto_id -> cuántas lecturas de temp lleva (eje X propio)

function datasetDeCuarto(cuartoId) {
  let ds = grafica.data.datasets.find(d => d.cuartoId === cuartoId);
  if (!ds) {
    const color = colorDeCuarto(cuartoId);
    ds = {
      cuartoId,
      label: `Cuarto ${cuartoId}`,
      data: [],
      borderColor: color,
      backgroundColor: color + "22",
      tension: 0.3,
    };
    grafica.data.datasets.push(ds);
  }
  return ds;
}

// ---------- Tarjetas por cuarto ----------
function asegurarTarjeta(cuartoId, cuartoNombre) {
  if (cuartosConocidos.has(cuartoId)) return;
  cuartosConocidos.add(cuartoId);

  const grid = document.getElementById("cuartos-grid");
  const div = document.createElement("div");
  div.className = "tarjeta-cuarto";
  div.id = `cuarto-${cuartoId}`;
  div.style.setProperty("--color-cuarto", colorDeCuarto(cuartoId));
  div.innerHTML = `
    <div class="tarjeta-cuarto-header">
      <span class="tarjeta-cuarto-nombre">${cuartoNombre || ("Cuarto " + cuartoId)}</span>
      <span class="tarjeta-cuarto-estado" id="estado-${cuartoId}">🟢</span>
    </div>
    <div class="tarjeta-cuarto-datos">
      <div><span class="mini-etiqueta">💡 Luz</span><span class="mini-valor" id="lux-${cuartoId}">--</span></div>
      <div><span class="mini-etiqueta">🌡️ Temp</span><span class="mini-valor" id="temp-${cuartoId}">--</span></div>
      <div><span class="mini-etiqueta">💧 Hum</span><span class="mini-valor" id="humedad-${cuartoId}">--</span></div>
      <div><span class="mini-etiqueta">🫧 Aire</span><span class="mini-valor" id="co2-${cuartoId}">--</span></div>
    </div>
  `;
  grid.appendChild(div);
}

function actualizarBannerGlobal() {
  const banner = document.getElementById("alerta-banner");
  const lista = document.getElementById("cuartos-en-alerta");
  if (cuartosEnAlerta.size === 0) {
    banner.classList.add("oculto");
    return;
  }
  lista.textContent = Array.from(cuartosEnAlerta).sort((a, b) => a - b).join(", ");
  banner.classList.remove("oculto");
}

function agregarFilaHistorial(lectura) {
  const tbody = document.querySelector("#tabla-historial tbody");
  const fila = document.createElement("tr");
  if (lectura.buzzer) fila.classList.add("fila-alerta");

  const hora = new Date(lectura.timestamp).toLocaleTimeString();
  fila.innerHTML = `
    <td>${lectura.cuarto_id}</td>
    <td>${hora}</td>
    <td>${lectura.lux}</td>
    <td>${lectura.temp}</td>
    <td>${lectura.humedad}</td>
    <td>${lectura.co2_ppm}</td>
    <td>${lectura.buzzer ? "🔴 Alerta" : "🟢 Normal"}</td>
  `;
  tbody.prepend(fila);
  while (tbody.children.length > 20) tbody.removeChild(tbody.lastChild);
}

// ---------- Recepción en vivo ----------
socket.on("nueva_lectura", (lectura) => {
  const cid = lectura.cuarto_id;
  if (cid === undefined || cid === null) return;

  asegurarTarjeta(cid, lectura.cuarto_nombre);

  document.getElementById(`lux-${cid}`).textContent = lectura.lux;
  document.getElementById(`temp-${cid}`).textContent = lectura.temp;
  document.getElementById(`humedad-${cid}`).textContent = lectura.humedad;
  document.getElementById(`co2-${cid}`).textContent = lectura.co2_ppm;

  const tarjeta = document.getElementById(`cuarto-${cid}`);
  const estadoEl = document.getElementById(`estado-${cid}`);
  if (lectura.buzzer) {
    tarjeta.classList.add("critico");
    estadoEl.textContent = "🔴";
    cuartosEnAlerta.add(cid);
  } else {
    tarjeta.classList.remove("critico");
    estadoEl.textContent = "🟢";
    cuartosEnAlerta.delete(cid);
  }
  actualizarBannerGlobal();

  // Gráfica
  const ds = datasetDeCuarto(cid);
  contadorPorCuarto[cid] = (contadorPorCuarto[cid] || 0) + 1;
  ds.data.push({ x: contadorPorCuarto[cid], y: lectura.temp });
  if (ds.data.length > MAX_PUNTOS_GRAFICA) ds.data.shift();
  grafica.update();

  agregarFilaHistorial(lectura);
});

// ---------- Historial inicial (todos los cuartos) ----------
fetch("/api/historial?n=20")
  .then(r => r.json())
  .then(datos => datos.forEach(agregarFilaHistorial));

// ---------- Descarga de reporte PDF ----------
document.getElementById("fecha-reporte").valueAsDate = new Date();
document.getElementById("btn-reporte").addEventListener("click", () => {
  const fecha = document.getElementById("fecha-reporte").value;
  window.location.href = `/api/reporte/${fecha}`;
});
