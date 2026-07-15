<script setup>
import { ref, computed, watch } from "vue";
import { getHistoria, getVersionDiff, getVersionContenido, exportarLsp } from "../api.js";
import { ultimoCompileStatus } from "../composables/compileStatusBus.js";
import { useDiagnosticos } from "../composables/useDiagnosticos.js";
import DiagnosticosDropdown from "./DiagnosticosDropdown.vue";

const props = defineProps({
  slug: { type: String, required: true },
  codigo: { type: String, required: true },
  texto: { type: String, default: "" },
  sucio: { type: Boolean, default: false },
  refreshSignal: { type: Number, default: 0 },
  tipo: { type: String, default: "doc" }, // "doc" | "plantilla" -- debe calzar con recurso_tipo del evento
  // Fase 3.3 de tinymist-implementation-plan.md: el autoguardado reemplaza el botón "Guardar"
  // por un indicador -- "Guardando…" mientras el PUT está en vuelo, "Guardado ✓ hh:mm:ss" tras
  // el último autoguardado exitoso.
  guardando: { type: Boolean, default: false },
  guardadoHora: { type: String, default: "" },
});

const emit = defineEmits(["cargar-en-editor", "abrir-imagenes"]);

const versiones = ref([]);
const error = ref("");
const diff = ref(null); // { version, filas }
const cargandoDiff = ref(false);

// Fase 2.1 de tinymist-implementation-plan.md (H1): indicador de compileStatus de la preview
// tinymist en vivo (Compilando/OK/Error) -- antes solo lo veía el frontend embebido de tinymist
// dentro del iframe. Los `kind` reales (Compiling/CompileSuccess/CompileError) se confirman en
// vivo contra el binario instalado; el match es case-insensitive por si difieren en mayúsculas.
const compileStatus = ref(""); // "" | "compiling" | "ok" | "error"

watch(ultimoCompileStatus, (evento) => {
  if (!evento) return;
  if (evento.recurso_tipo !== props.tipo || evento.slug !== props.slug || evento.nombre !== props.codigo) return;
  const kind = evento.kind || "";
  if (/compil/i.test(kind) && !/success|error|fail/i.test(kind)) compileStatus.value = "compiling";
  else if (/error|fail/i.test(kind)) compileStatus.value = "error";
  else if (/success|ok/i.test(kind)) compileStatus.value = "ok";
});

const compileStatusTexto = computed(() => ({
  compiling: "Compilando…",
  ok: "Vista previa OK",
  error: "Error de compilación",
}[compileStatus.value] || ""));

// Fase 1B de tinymist-implementation-plan.md: diagnósticos LSP (errores/avisos) del archivo
// abierto en este editor. `useDiagnosticos` deriva del bus la lista vigente (no un historial:
// cuando el LSP deja de reportar un diagnóstico, desaparece) ordenada por línea para el
// desplegable (pedido del usuario -- CodeMirror los pinta en el editor, pero no había forma de
// verlos todos listados a la vez).
const tipoRef = computed(() => props.tipo);
const slugRef = computed(() => props.slug);
const codigoRef = computed(() => props.codigo);
const { lista: diagnosticos, errores, resumenTexto: diagnosticosTexto } =
  useDiagnosticos(tipoRef, slugRef, codigoRef);

const versionActual = computed(() => versiones.value[0]?.version || "—");
const estadoGuardado = computed(() => {
  if (props.guardando) return "Guardando…";
  if (props.sucio) return "cambios sin guardar";
  return props.guardadoHora ? `Guardado ✓ ${props.guardadoHora}` : "sin cambios pendientes";
});
const palabras = computed(() => {
  const t = props.texto.trim();
  return t ? t.split(/\s+/).length : 0;
});
const tamanoKB = computed(() => (new Blob([props.texto]).size / 1024).toFixed(1));

async function cargarHistoria() {
  try {
    versiones.value = await getHistoria(props.slug, props.codigo);
  } catch (e) {
    error.value = e.message;
  }
}

watch(() => props.codigo, cargarHistoria, { immediate: true });
watch(() => props.refreshSignal, cargarHistoria);

async function verDiff(version) {
  cargandoDiff.value = true;
  error.value = "";
  try {
    diff.value = await getVersionDiff(props.slug, props.codigo, version);
  } catch (e) {
    error.value = e.message;
  } finally {
    cargandoDiff.value = false;
  }
}

async function cargarVersionEnEditor(version) {
  try {
    const contenido = await getVersionContenido(props.slug, props.codigo, version);
    emit("cargar-en-editor", { contenido, version });
    diff.value = null;
  } catch (e) {
    error.value = e.message;
  }
}

function onCambioVersion(ev) {
  const version = ev.target.value;
  ev.target.value = "";
  if (version) verDiff(version);
}

// Fase 1D (D5): exportación rápida -- sin versión/snapshot, sin fila en org.json, nunca pisa
// el <código-base>.pdf oficial de "Compilar" (el backend respalda/restaura, ver
// api_lsp_exportar en doctyp_web.py). Solo pdf/text/markdown -- svg/png quedan fuera por una
// limitación real de tinymist 0.15.2 (ver nota de la Etapa 16 en CLAUDE.md).
const exportando = ref(false);
async function onCambioExportar(ev) {
  const formato = ev.target.value;
  ev.target.value = "";
  if (!formato) return;
  exportando.value = true;
  error.value = "";
  try {
    await exportarLsp(props.slug, props.codigo, props.tipo, formato);
  } catch (e) {
    error.value = `Error al exportar: ${e.message}`;
  } finally {
    exportando.value = false;
  }
}
</script>

<template>
  <div class="status-bar">
    <div v-if="error" class="error-banner">{{ error }}</div>
    <div class="status-bar-fila">
      <span class="status-badge">v{{ versionActual }}</span>
      <select @change="onCambioVersion">
        <option value="">Ver versión / diff…</option>
        <option v-for="v in versiones" :key="v.version" :value="v.version" :disabled="!v.snapshot_disponible">
          v{{ v.version }}{{ !v.snapshot_disponible ? " (sin snapshot)" : "" }}
        </option>
      </select>
      <select :disabled="exportando" @change="onCambioExportar" title="Exportación rápida (sin versión) vía tinymist">
        <option value="">{{ exportando ? "Exportando…" : "Exportar…" }}</option>
        <option value="pdf">PDF</option>
        <option value="text">Texto plano</option>
        <option value="markdown">Markdown</option>
      </select>
      <button type="button" @click="emit('abrir-imagenes')">Imágenes…</button>
      <span class="estado">{{ palabras }} palabras · {{ tamanoKB }} KB</span>
      <span
        v-if="compileStatusTexto"
        class="estado"
        :style="{ color: compileStatus === 'error' ? 'var(--danger)' : undefined }"
      >{{ compileStatusTexto }}</span>
      <DiagnosticosDropdown
        v-if="diagnosticosTexto"
        :lista="diagnosticos"
        :resumen-texto="diagnosticosTexto"
        :tiene-errores="!!errores"
      />
      <span class="status-bar-spacer"></span>
      <span class="estado">{{ estadoGuardado }}</span>
    </div>
    <div v-if="cargandoDiff" class="empty-state">Cargando diferencias…</div>
    <div v-else-if="diff" class="diff-panel">
      <div class="acciones" style="margin-bottom: 0.5em">
        <strong>Diferencias v{{ diff.version }} → vigente</strong>
        <button class="primary" @click="cargarVersionEnEditor(diff.version)">Cargar v{{ diff.version }} en editor</button>
        <button @click="diff = null">Cerrar</button>
      </div>
      <pre class="diff-lineas"><span
        v-for="(f, i) in diff.filas" :key="i"
        :class="['diff-linea', `diff-${f.tipo}`]"
      >{{ (f.tipo === "agregada" ? "+ " : f.tipo === "eliminada" ? "- " : "  ") + f.texto }}
</span></pre>
    </div>
  </div>
</template>
