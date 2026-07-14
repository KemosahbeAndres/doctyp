<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import {
  getTyp, putTyp, guardarVersion, compilar, getArchivosDoc, getArchivoDoc,
  actualizarMemoriaPreview, saltarAPosicionPreview,
} from "../api.js";
import MetaEditorModal from "./MetaEditorModal.vue";
import StatusBar from "./StatusBar.vue";
import TypstCanvasPreview from "./TypstCanvasPreview.vue";
import TinymistPreview from "./TinymistPreview.vue";
import CodeEditor from "./CodeEditor.vue";

const props = defineProps({
  slug: { type: String, required: true },
  codigo: { type: String, default: null },
});

const emit = defineEmits(["sucio-cambio", "cambio-en-servidor"]);

// Plan 15 F3/F8: tinymist es el motor de preview por defecto; si no está disponible en el
// backend (sin binario instalado, ver doctyp_preview_binary.py), se degrada a la vista previa
// typst.ts existente (Etapa 12.1) sin que el usuario pierda funcionalidad, solo sin
// clic↔cursor (F5/F6, no implementados en ese modo -- ver informe ETAPA-12-CLICK-TO-JUMP.md).
const usarPreviewLegacy = ref(false);

async function cargarArchivosDoc(slug, codigo, texto) {
  const rutas = (await getArchivosDoc(slug, codigo)).filter((r) => !r.startsWith("fonts/"));
  const archivos = await Promise.all(
    rutas.map(async (ruta) => ({ ruta, bytes: await getArchivoDoc(slug, codigo, ruta) })),
  );
  return { mainTexto: texto, archivos };
}

const texto = ref("");
const original = ref("");
const cargando = ref(false);
const ocupado = ref(false);
const mensaje = ref("");
const mensajeEsError = ref(false);
const mostrarMeta = ref(false);
const refreshSignalLocal = ref(0);

const sucio = computed(() => texto.value !== original.value);
watch(sucio, (v) => emit("sucio-cambio", v));

async function cargar(codigo) {
  if (!codigo) {
    texto.value = "";
    original.value = "";
    return;
  }
  cargando.value = true;
  mensaje.value = "";
  try {
    const contenido = await getTyp(props.slug, codigo);
    texto.value = contenido;
    original.value = contenido;
  } catch (e) {
    mensaje.value = `No se pudo cargar el documento: ${e.message}`;
    mensajeEsError.value = true;
  } finally {
    cargando.value = false;
  }
}

watch(
  () => props.codigo,
  (nuevo) => cargar(nuevo),
  { immediate: true },
);

function onCargarEnEditor(payload) {
  texto.value = payload.contenido;
  mensaje.value = `Versión v${payload.version} cargada en el editor (sin guardar aún).`;
  mensajeEsError.value = false;
}

async function guardarCambios() {
  ocupado.value = true;
  mensaje.value = "";
  try {
    await putTyp(props.slug, props.codigo, texto.value);
    original.value = texto.value;
    mensaje.value = "Cambios guardados.";
    mensajeEsError.value = false;
  } catch (e) {
    mensaje.value = `Error al guardar: ${e.message}`;
    mensajeEsError.value = true;
  } finally {
    ocupado.value = false;
  }
}

async function subirVersion() {
  const msg = window.prompt("Mensaje para la nueva versión (qué cambió):");
  if (!msg) return;
  ocupado.value = true;
  mensaje.value = "";
  try {
    if (sucio.value) {
      await putTyp(props.slug, props.codigo, texto.value);
      original.value = texto.value;
    }
    const res = await guardarVersion(props.slug, props.codigo, msg);
    mensaje.value = `Versión subida: v${res.version_actual} → v${res.version_nueva}.`;
    mensajeEsError.value = false;
    refreshSignalLocal.value++;
    emit("cambio-en-servidor");
  } catch (e) {
    mensaje.value = `Error al subir versión: ${e.message}`;
    mensajeEsError.value = true;
  } finally {
    ocupado.value = false;
  }
}

async function compilarDoc() {
  const msg = window.prompt("Mensaje para la versión que se compilará:");
  if (!msg) return;
  ocupado.value = true;
  mensaje.value = "";
  try {
    if (sucio.value) {
      await putTyp(props.slug, props.codigo, texto.value);
      original.value = texto.value;
    }
    const res = await compilar(props.slug, props.codigo, msg);
    mensaje.value = res.pdf
      ? `Compilado: ${res.pdf} (v${res.version}).`
      : `Guardado como v${res.version}, pero la compilación no generó PDF.`;
    mensajeEsError.value = false;
    refreshSignalLocal.value++;
    emit("cambio-en-servidor");
  } catch (e) {
    mensaje.value = `Error al compilar: ${e.message}`;
    mensajeEsError.value = true;
  } finally {
    ocupado.value = false;
  }
}

const refEditor = ref(null);

// Plan 15 F6: mientras el usuario tipea (sin guardar), se envía el contenido al subproceso de
// preview vía updateMemoryFiles (recompila en memoria, sin tocar el .typ en disco). Debounce
// para no saturar con cada tecla. Regla explícita del usuario (§0/§8 del plan): esto reemplaza
// el "compilar al tipear" de la Etapa 12.1/typst.ts -- NO es lo mismo que el scroll sync
// eliminado (F7): acá solo se envía contenido, nunca se mueve el cursor/scroll automáticamente.
let temporizadorMemoria = null;
watch(texto, (nuevo) => {
  if (usarPreviewLegacy.value || !props.codigo) return; // legacy usa su propio debounce interno
  if (temporizadorMemoria) clearTimeout(temporizadorMemoria);
  temporizadorMemoria = setTimeout(() => {
    actualizarMemoriaPreview(props.slug, props.codigo, nuevo).catch(() => {
      // silencioso: si la preview no está activa (p. ej. tinymist cayó), no hay nada que
      // reportar -- la próxima vez que se abra la preview arrancará con el contenido guardado.
    });
  }, 300);
});

// Plan 15 F6: salto explícito cursor→preview (acción deliberada, NUNCA automática en scroll --
// regla del usuario). Atajo Ctrl+Alt+J, ajustable si choca con alguna convención del navegador.
function saltarEnPreview() {
  if (usarPreviewLegacy.value || !props.codigo) return;
  const pos = refEditor.value?.getPosicionCursor();
  if (!pos) return;
  saltarAPosicionPreview(props.slug, props.codigo, pos.line, pos.character).catch(() => {});
}

function onKeydownGlobal(ev) {
  if (ev.ctrlKey && ev.altKey && ev.key.toLowerCase() === "j") {
    ev.preventDefault();
    saltarEnPreview();
  }
}

onMounted(() => window.addEventListener("keydown", onKeydownGlobal));
onUnmounted(() => window.removeEventListener("keydown", onKeydownGlobal));

function onMetaGuardado(res) {
  // El backend ya escribió el .typ en disco (incluye el patch de metadatos) -- resincronizamos
  // texto/original con ese contenido para no arriesgar que "Guardar cambios" lo pise después.
  texto.value = res.contenido;
  original.value = res.contenido;
  mostrarMeta.value = false;
  mensaje.value = "Metadatos guardados.";
  mensajeEsError.value = false;
  emit("cambio-en-servidor");
}
</script>

<template>
  <div class="panel panel-editor">
    <div v-if="!codigo" class="empty-state">Selecciona un documento para editarlo.</div>
    <template v-else>
      <div v-if="cargando" class="empty-state">Cargando…</div>
      <div v-if="mensaje" class="estado editor-mensaje" :style="{ color: mensajeEsError ? 'var(--danger)' : undefined }">
        {{ mensaje }}
      </div>
      <div class="editor-preview-split">
        <CodeEditor
          ref="refEditor"
          class="editor-textarea"
          v-model="texto"
          :disabled="cargando"
          :slug="slug"
          :codigo="codigo"
          tipo="doc"
        />
        <TinymistPreview
          v-if="!usarPreviewLegacy"
          :slug="slug"
          :codigo="codigo"
          tipo="doc"
          @no-disponible="usarPreviewLegacy = true"
          @saltar-aqui="saltarEnPreview"
        />
        <TypstCanvasPreview
          v-else
          :slug="slug"
          :codigo="codigo"
          :texto="texto"
          :cargar-archivos="cargarArchivosDoc"
        />
      </div>
      <StatusBar
        :slug="slug"
        :codigo="codigo"
        :texto="texto"
        :sucio="sucio"
        :ocupado="ocupado"
        :refresh-signal="refreshSignalLocal"
        @guardar="guardarCambios"
        @subir-version="subirVersion"
        @compilar="compilarDoc"
        @metadatos="mostrarMeta = true"
        @cargar-en-editor="onCargarEnEditor"
      />
      <MetaEditorModal
        v-if="mostrarMeta"
        :slug="slug"
        :codigo="codigo"
        @guardado="onMetaGuardado"
        @cancelar="mostrarMeta = false"
      />
    </template>
  </div>
</template>
