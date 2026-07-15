<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import {
  getPlantillaLibTyp, guardarPlantillaLibTyp, putPlantillaLibTypContenido,
  getHistoriaPlantilla, getVersionContenidoPlantilla,
  getArchivosPlantilla, getArchivoPlantilla, getMuestraPlantilla,
  saltarAPosicionPreviewPlantilla, exportarLsp,
} from "../api.js";
import TypstCanvasPreview from "./TypstCanvasPreview.vue";
import TinymistPreview from "./TinymistPreview.vue";
import CodeEditor from "./CodeEditor.vue";
import DiagnosticosDropdown from "./DiagnosticosDropdown.vue";
import SubirImagenesModal from "./SubirImagenesModal.vue";
import { ultimoCompileStatus } from "../composables/compileStatusBus.js";
import { useDiagnosticos } from "../composables/useDiagnosticos.js";

const props = defineProps({
  slug: { type: String, required: true },
  nombre: { type: String, required: true },
});

const emit = defineEmits(["sucio-cambio", "guardado"]);

// Plan 15 (extensión): tinymist es el motor de preview por defecto también para plantillas;
// si no está disponible, degrada a typst.ts (Etapa 12.1), igual que DocEditor.vue.
const usarPreviewLegacy = ref(false);

const texto = ref("");
const original = ref("");
const cargando = ref(false);
const ocupado = ref(false);
const mensaje = ref("");
const mensajeEsError = ref(false);
const versiones = ref([]);
const guardando = ref(false);
const guardadoHora = ref("");
const tinymistPreviewRef = ref(null);
const mostrarImagenes = ref(false);

function _horaActual() {
  return new Date().toLocaleTimeString("es-CL", { hour12: false });
}

const sucio = computed(() => texto.value !== original.value);
watch(sucio, (v) => emit("sucio-cambio", v));

const palabras = computed(() => {
  const t = texto.value.trim();
  return t ? t.split(/\s+/).length : 0;
});
const tamanoKB = computed(() => (new Blob([texto.value]).size / 1024).toFixed(1));
const estadoGuardado = computed(() => {
  if (guardando.value) return "Guardando…";
  if (sucio.value) return "cambios sin guardar";
  return guardadoHora.value ? `Guardado ✓ ${guardadoHora.value}` : "sin cambios pendientes";
});

// Fase 2.1 de tinymist-implementation-plan.md (H1), mismo indicador que StatusBar.vue.
const compileStatus = ref(""); // "" | "compiling" | "ok" | "error"
watch(ultimoCompileStatus, (evento) => {
  if (!evento) return;
  if (evento.recurso_tipo !== "plantilla" || evento.slug !== props.slug || evento.nombre !== props.nombre) return;
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

// Fase 1B de tinymist-implementation-plan.md, mismo indicador que StatusBar.vue.
const tipoRef = computed(() => "plantilla");
const slugRef = computed(() => props.slug);
const nombreRef = computed(() => props.nombre);
const { lista: diagnosticos, errores, resumenTexto: diagnosticosTexto } =
  useDiagnosticos(tipoRef, slugRef, nombreRef);

async function cargar() {
  cargando.value = true;
  mensaje.value = "";
  try {
    const contenido = await getPlantillaLibTyp(props.slug, props.nombre);
    texto.value = contenido;
    original.value = contenido;
  } catch (e) {
    mensaje.value = `No se pudo cargar la plantilla: ${e.message}`;
    mensajeEsError.value = true;
  } finally {
    cargando.value = false;
  }
}

async function cargarHistoria() {
  try {
    versiones.value = await getHistoriaPlantilla(props.slug, props.nombre);
  } catch (e) {
    mensaje.value = e.message;
    mensajeEsError.value = true;
  }
}

onMounted(() => {
  cargar();
  cargarHistoria();
  window.addEventListener("beforeunload", onBeforeUnload);
});
onUnmounted(() => {
  window.removeEventListener("beforeunload", onBeforeUnload);
  flushGuardado();
});

// Fase 3.3 de tinymist-implementation-plan.md (decisión del usuario 2026-07-14: el
// autoguardado aplica también al editor de plantillas, mismo mecanismo/debounce que
// documentos). Reemplaza el debounce de updateMemoryFiles de Plan 15 F6: ahora se escribe
// lib.typ a disco de verdad (PUT .../lib-typ-contenido, SIN versión/snapshot -- eso lo sigue
// haciendo únicamente "Guardar plantilla", más abajo) y tinymist detecta el cambio solo.
let temporizadorGuardado = null;

watch(texto, () => {
  if (temporizadorGuardado) clearTimeout(temporizadorGuardado);
  temporizadorGuardado = setTimeout(autoguardar, 300);
});

async function autoguardar() {
  temporizadorGuardado = null;
  if (!sucio.value) return;
  if (ocupado.value) {
    temporizadorGuardado = setTimeout(autoguardar, 300);
    return;
  }
  const contenido = texto.value;
  guardando.value = true;
  try {
    await putPlantillaLibTypContenido(props.slug, props.nombre, contenido);
    if (texto.value === contenido) {
      original.value = contenido;
      guardadoHora.value = _horaActual();
      mensaje.value = "";
    }
    // Señal explícita del cliente (mismo criterio que DocEditor.vue): reasegurar tinymist
    // fire-and-forget tras cada autoguardado, por si el subproceso cayó y agotó sus reintentos.
    tinymistPreviewRef.value?.reconectar();
  } catch (e) {
    mensaje.value = `Autoguardado falló: ${e.message}`;
    mensajeEsError.value = true;
  } finally {
    guardando.value = false;
  }
}

function flushGuardado() {
  if (temporizadorGuardado) {
    clearTimeout(temporizadorGuardado);
    temporizadorGuardado = null;
  }
  if (sucio.value && !ocupado.value) return autoguardar();
  return Promise.resolve();
}

function onBeforeUnload() {
  flushGuardado();
}

// Fase 3.2 de tinymist-implementation-plan.md (extensión a plantillas, mismo criterio que
// DocEditor.vue): jump automático al clic, sin botón ni atajo.
function onClicEnEditor({ line, character }) {
  if (usarPreviewLegacy.value) return;
  saltarAPosicionPreviewPlantilla(props.slug, props.nombre, line, character).catch(() => {});
}

// H2 (Fase 3.1, extensión a plantillas): el clic resolvió al .typ de MUESTRA (lo que el
// usuario ve renderizado, no lo que edita) -- acá el archivo editable ES lib.typ, así que el
// caso "no editable" es el espejo del de documentos: prosa generada por la muestra, no por
// lib.typ. Sin mensaje (a diferencia de DocEditor.vue): es la muestra ficticia, no hay otro
// editor al que mandar al usuario.
function onSaltoNoEditable() {}

async function guardar() {
  const msg = window.prompt("Mensaje para la nueva versión (qué cambió en la plantilla):");
  if (!msg) return;
  if (temporizadorGuardado) {
    clearTimeout(temporizadorGuardado); // evita una carrera con el autoguardado en vuelo
    temporizadorGuardado = null;
  }
  ocupado.value = true;
  mensaje.value = "";
  try {
    const fila = await guardarPlantillaLibTyp(props.slug, props.nombre, texto.value, msg);
    original.value = texto.value;
    guardadoHora.value = _horaActual();
    mensaje.value = `Versión guardada: v${fila.version}.`;
    mensajeEsError.value = false;
    await cargarHistoria();
    emit("guardado");
  } catch (e) {
    mensaje.value = `Error al guardar: ${e.message}`;
    mensajeEsError.value = true;
  } finally {
    ocupado.value = false;
  }
}

async function cargarVersionEnEditor(version) {
  try {
    texto.value = await getVersionContenidoPlantilla(props.slug, props.nombre, version);
    mensaje.value = `Versión v${version} cargada en el editor (sin guardar aún).`;
    mensajeEsError.value = false;
  } catch (e) {
    mensaje.value = e.message;
    mensajeEsError.value = true;
  }
}

function onCambioVersion(ev) {
  const version = ev.target.value;
  ev.target.value = "";
  if (version) cargarVersionEnEditor(version);
}

// Fase 1D (D5), mismo criterio que StatusBar.vue -- exporta la MUESTRA (documento ficticio que
// importa lib.typ), no lib.typ directamente (no es compilable por sí solo).
const exportando = ref(false);
async function onCambioExportar(ev) {
  const formato = ev.target.value;
  ev.target.value = "";
  if (!formato) return;
  exportando.value = true;
  mensaje.value = "";
  try {
    await exportarLsp(props.slug, props.nombre, "plantilla", formato);
  } catch (e) {
    mensaje.value = `Error al exportar: ${e.message}`;
    mensajeEsError.value = true;
  } finally {
    exportando.value = false;
  }
}

// Las imágenes subidas/eliminadas desde el modal quedan en disco (Images/) pero el iframe de
// tinymist ya cargó su propio snapshot del proyecto al abrirse -- sin esto, #image("Images/…")
// recién agregado en lib.typ no aparecería hasta la próxima vez que algo más recargue el iframe.
function onImagenesCambiadas() {
  tinymistPreviewRef.value?.refrescarForzado();
}

async function cargarArchivosPlantilla(slug, nombre, texto) {
  const [rutas, muestra] = await Promise.all([
    getArchivosPlantilla(slug, nombre),
    getMuestraPlantilla(slug, nombre),
  ]);
  const archivos = await Promise.all(
    rutas
      .filter((r) => !r.startsWith("fonts/"))
      .map(async (ruta) => ({ ruta, bytes: await getArchivoPlantilla(slug, nombre, ruta) })),
  );
  archivos.push({ ruta: "lib.typ", bytes: new TextEncoder().encode(texto) });
  return { mainTexto: muestra, archivos };
}

// El botón "Guardar plantilla" vive en la cabecera (App.vue, .documento-header), no acá --
// mismo criterio que DocEditor.vue.
defineExpose({ ocupado, guardar });
</script>

<template>
  <div class="panel panel-editor">
    <div v-if="cargando" class="empty-state">Cargando…</div>
    <template v-else>
      <div v-if="mensaje" class="estado editor-mensaje" :style="{ color: mensajeEsError ? 'var(--danger)' : undefined }">
        {{ mensaje }}
      </div>
      <div class="editor-preview-split">
        <CodeEditor
          class="editor-textarea"
          v-model="texto"
          :slug="slug"
          :codigo="nombre"
          tipo="plantilla"
          @clic-en-editor="onClicEnEditor"
          @salto-no-editable="onSaltoNoEditable"
          @guardar="flushGuardado"
        />
        <TinymistPreview
          v-if="!usarPreviewLegacy"
          ref="tinymistPreviewRef"
          :slug="slug"
          :codigo="nombre"
          tipo="plantilla"
          @no-disponible="usarPreviewLegacy = true"
        />
        <TypstCanvasPreview
          v-else
          :slug="slug"
          :codigo="nombre"
          :texto="texto"
          :cargar-archivos="cargarArchivosPlantilla"
        />
      </div>
      <div class="status-bar">
        <div class="status-bar-fila">
          <select @change="onCambioVersion">
            <option value="">Ver / cargar versión anterior…</option>
            <option v-for="v in versiones" :key="v.version" :value="v.version" :disabled="!v.snapshot_disponible">
              v{{ v.version }} · {{ v.mensaje }}
            </option>
          </select>
          <select :disabled="exportando" @change="onCambioExportar" title="Exportación rápida (sin versión) vía tinymist, sobre el documento de muestra">
            <option value="">{{ exportando ? "Exportando…" : "Exportar…" }}</option>
            <option value="pdf">PDF</option>
            <option value="text">Texto plano</option>
            <option value="markdown">Markdown</option>
          </select>
          <button type="button" @click="mostrarImagenes = true">Imágenes…</button>
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
      </div>
      <SubirImagenesModal
        v-if="mostrarImagenes"
        :slug="slug"
        :nombre="nombre"
        @cerrar="mostrarImagenes = false"
        @cambiado="onImagenesCambiadas"
      />
    </template>
  </div>
</template>
