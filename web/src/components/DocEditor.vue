<script setup>
import { ref, computed, watch, onMounted, nextTick } from "vue";
import { getTyp, putTyp, guardarVersion, compilar, getArchivosDoc, getArchivoDoc } from "../api.js";
import MetaEditorModal from "./MetaEditorModal.vue";
import StatusBar from "./StatusBar.vue";
import TypstCanvasPreview from "./TypstCanvasPreview.vue";
import CodeEditor from "./CodeEditor.vue";
import { useScrollSync } from "../composables/useScrollSync.js";

const props = defineProps({
  slug: { type: String, required: true },
  codigo: { type: String, default: null },
});

const emit = defineEmits(["sucio-cambio", "cambio-en-servidor"]);

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

// Etapa 12.4: scroll sincronizado "a la par" entre el editor de código y la vista previa. El
// contenedor del preview conserva su identidad entre compilaciones (solo cambia su innerHTML),
// así que basta con conectar una vez que los hijos existen en el DOM -- no hace falta
// reconectar en cada recompilación. `codigo` empieza en null (nada montado detrás de
// v-if="!codigo") así que se reconecta también cuando pasa a tener valor, no solo en onMounted.
const refEditor = ref(null);
const refPreview = ref(null);
const { reconectar } = useScrollSync(
  () => refEditor.value?.getScroller() ?? null,
  () => refPreview.value?.getScroller() ?? null,
);
onMounted(reconectar);
watch(
  () => props.codigo,
  () => nextTick(reconectar),
);

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
        <CodeEditor ref="refEditor" class="editor-textarea" v-model="texto" :disabled="cargando" />
        <TypstCanvasPreview ref="refPreview" :slug="slug" :codigo="codigo" :texto="texto" :cargar-archivos="cargarArchivosDoc" />
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
