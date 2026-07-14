<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import {
  getPlantillaLibTyp, guardarPlantillaLibTyp,
  getHistoriaPlantilla, getVersionContenidoPlantilla,
  getArchivosPlantilla, getArchivoPlantilla, getMuestraPlantilla,
  actualizarMemoriaPreviewPlantilla, saltarAPosicionPreviewPlantilla,
} from "../api.js";
import TypstCanvasPreview from "./TypstCanvasPreview.vue";
import TinymistPreview from "./TinymistPreview.vue";
import CodeEditor from "./CodeEditor.vue";

const props = defineProps({
  slug: { type: String, required: true },
  nombre: { type: String, required: true },
});

const emit = defineEmits(["sucio-cambio", "guardado"]);

// Plan 15 (extensión): tinymist es el motor de preview por defecto también para plantillas;
// si no está disponible, degrada a typst.ts (Etapa 12.1), igual que DocEditor.vue.
const usarPreviewLegacy = ref(false);
const refEditor = ref(null);

const texto = ref("");
const original = ref("");
const cargando = ref(false);
const ocupado = ref(false);
const mensaje = ref("");
const mensajeEsError = ref(false);
const versiones = ref([]);

const sucio = computed(() => texto.value !== original.value);
watch(sucio, (v) => emit("sucio-cambio", v));

const palabras = computed(() => {
  const t = texto.value.trim();
  return t ? t.split(/\s+/).length : 0;
});
const tamanoKB = computed(() => (new Blob([texto.value]).size / 1024).toFixed(1));

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
  window.addEventListener("keydown", onKeydownGlobal);
});

onUnmounted(() => {
  window.removeEventListener("keydown", onKeydownGlobal);
});

// Plan 15 F6 (extensión a plantillas): mientras el usuario tipea (sin guardar), se envía
// lib.typ al subproceso de preview vía updateMemoryFiles -- ver
// api_preview_update_memory_plantilla en doctyp_web.py (la muestra en disco importa lib.typ,
// así que tinymist recompila igual sin tocar el archivo real).
let temporizadorMemoria = null;
watch(texto, (nuevo) => {
  if (usarPreviewLegacy.value) return;
  if (temporizadorMemoria) clearTimeout(temporizadorMemoria);
  temporizadorMemoria = setTimeout(() => {
    actualizarMemoriaPreviewPlantilla(props.slug, props.nombre, nuevo).catch(() => {});
  }, 300);
});

// Plan 15 F6 (extensión): salto explícito cursor→preview, mismo atajo que documentos.
function saltarEnPreview() {
  if (usarPreviewLegacy.value) return;
  const pos = refEditor.value?.getPosicionCursor();
  if (!pos) return;
  saltarAPosicionPreviewPlantilla(props.slug, props.nombre, pos.line, pos.character).catch(() => {});
}

function onKeydownGlobal(ev) {
  if (ev.ctrlKey && ev.altKey && ev.key.toLowerCase() === "j") {
    ev.preventDefault();
    saltarEnPreview();
  }
}

async function guardar() {
  const msg = window.prompt("Mensaje para la nueva versión (qué cambió en la plantilla):");
  if (!msg) return;
  ocupado.value = true;
  mensaje.value = "";
  try {
    const fila = await guardarPlantillaLibTyp(props.slug, props.nombre, texto.value, msg);
    original.value = texto.value;
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
          ref="refEditor"
          class="editor-textarea"
          v-model="texto"
          :slug="slug"
          :codigo="nombre"
          tipo="plantilla"
        />
        <TinymistPreview
          v-if="!usarPreviewLegacy"
          :slug="slug"
          :codigo="nombre"
          tipo="plantilla"
          @no-disponible="usarPreviewLegacy = true"
          @saltar-aqui="saltarEnPreview"
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
          <span class="estado">{{ sucio ? "cambios sin guardar" : "sin cambios pendientes" }}</span>
          <select @change="onCambioVersion">
            <option value="">Ver / cargar versión anterior…</option>
            <option v-for="v in versiones" :key="v.version" :value="v.version" :disabled="!v.snapshot_disponible">
              v{{ v.version }} · {{ v.mensaje }}
            </option>
          </select>
          <span class="estado">{{ palabras }} palabras · {{ tamanoKB }} KB</span>
          <span class="status-bar-spacer"></span>
          <button class="primary" :disabled="ocupado" @click="guardar">Guardar plantilla</button>
        </div>
      </div>
    </template>
  </div>
</template>
