<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import {
  getTyp, putTyp, guardarVersion, compilar, getArchivosDoc, getArchivoDoc,
  saltarAPosicionPreview,
} from "../api.js";
import MetaEditorModal from "./MetaEditorModal.vue";
import StatusBar from "./StatusBar.vue";
import TypstCanvasPreview from "./TypstCanvasPreview.vue";
import TinymistPreview from "./TinymistPreview.vue";
import CodeEditor from "./CodeEditor.vue";
import SubirImagenesModal from "./SubirImagenesModal.vue";

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
const mostrarImagenes = ref(false);
const refreshSignalLocal = ref(0);
const guardando = ref(false);
const guardadoHora = ref("");
const tinymistPreviewRef = ref(null);

const sucio = computed(() => texto.value !== original.value);
watch(sucio, (v) => emit("sucio-cambio", v));

function _horaActual() {
  return new Date().toLocaleTimeString("es-CL", { hour12: false });
}

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

// Fase 3.3 de tinymist-implementation-plan.md: autoguardado a 300 ms tras la última edición.
// Reemplaza tanto el botón "Guardar" (retirado de StatusBar.vue) como el debounce de
// updateMemoryFiles de Plan 15 F6 -- ahora se escribe a disco de verdad y tinymist detecta el
// cambio y recompila solo (ya no hace falta enviarle el contenido en memoria aparte).
let temporizadorGuardado = null;

watch(texto, () => {
  if (!props.codigo) return;
  if (temporizadorGuardado) clearTimeout(temporizadorGuardado);
  temporizadorGuardado = setTimeout(autoguardar, 300);
});

async function autoguardar() {
  temporizadorGuardado = null;
  if (!props.codigo || !sucio.value) return;
  if (ocupado.value) {
    // Subir versión/Compilar en vuelo: no competir por la escritura -- reprogramar en vez de
    // perder este ciclo (la próxima edición igual dispararía uno nuevo, pero si el usuario deja
    // de tipear justo mientras ocupado, sin esto el autoguardado nunca correría).
    temporizadorGuardado = setTimeout(autoguardar, 300);
    return;
  }
  const contenido = texto.value; // capturar ANTES del await -- ver nota de carrera abajo
  guardando.value = true;
  try {
    await putTyp(props.slug, props.codigo, contenido);
    // Si el usuario siguió tipeando durante el await, texto.value ya no es `contenido`: NO
    // marcar limpio (perderíamos de vista que lo más nuevo aún no está en disco). El watch(texto)
    // de arriba ya disparó un temporizador nuevo para ese contenido más reciente.
    if (texto.value === contenido) {
      original.value = contenido;
      guardadoHora.value = _horaActual();
      mensaje.value = "";
    }
    // El .typ ya está en disco -- tinymist detectará el cambio y recompilará solo, pero si el
    // subproceso cayó (se agotaron sus reintentos automáticos, ver doctyp_preview_server.py) eso
    // nunca pasaría hasta que algo vuelva a pedir /api/preview/info. Señal explícita del cliente
    // (pedido del usuario): reasegurar tinymist fire-and-forget tras cada autoguardado exitoso.
    tinymistPreviewRef.value?.reconectar();
  } catch (e) {
    mensaje.value = `Autoguardado falló: ${e.message}`;
    mensajeEsError.value = true;
  } finally {
    guardando.value = false;
  }
}

/** Flush inmediato, sin esperar los 300 ms -- beforeunload, salir de la vista, o antes de
 * Subir versión/Compilar (que además ya guardan si `sucio`, ver abajo -- esto es cinturón). */
function flushGuardado() {
  if (temporizadorGuardado) {
    clearTimeout(temporizadorGuardado);
    temporizadorGuardado = null;
  }
  if (sucio.value && !ocupado.value) return autoguardar();
  return Promise.resolve();
}

function onBeforeUnload() {
  flushGuardado(); // best-effort: el navegador no espera un fetch async en beforeunload
}

onMounted(() => window.addEventListener("beforeunload", onBeforeUnload));
onUnmounted(() => {
  window.removeEventListener("beforeunload", onBeforeUnload);
  flushGuardado();
});

async function subirVersion() {
  const msg = window.prompt("Mensaje para la nueva versión (qué cambió):");
  if (!msg) return;
  await flushGuardado();
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
  await flushGuardado();
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

// Fase 3.2 de tinymist-implementation-plan.md: jump automático editor→preview al clic (sin
// botón, sin atajo -- reemplaza el salto explícito Ctrl+Alt+J de Plan 15 F6, revertido por
// decisión del usuario 2026-07-14, ver H6 del plan). El disparador es el evento "clic-en-editor"
// de CodeEditor.vue (clic de posicionamiento real, no selección/arrastre).
function onClicEnEditor({ line, character }) {
  if (usarPreviewLegacy.value || !props.codigo) return;
  saltarAPosicionPreview(props.slug, props.codigo, line, character).catch(() => {});
}

// H2 (Fase 3.1): el clic en el render resolvió a un archivo que este editor no edita (lib.typ,
// D4) -- aviso no intrusivo, sin mover el cursor.
function onSaltoNoEditable() {
  mensaje.value = "Definido en la plantilla (lib.typ) — edítala desde el editor de plantillas.";
  mensajeEsError.value = false;
}

// Mismo motivo que TemplateEditor.vue: el iframe de tinymist ya cargó su propio snapshot del
// proyecto al abrirse -- sin esto, una imagen recién subida/eliminada en img/ no aparecería en
// la vista previa hasta que algo más recargue el iframe.
function onImagenesCambiadas() {
  tinymistPreviewRef.value?.refrescarForzado();
}

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

// Los botones de acción viven en la cabecera del documento (App.vue, .documento-header), no
// en este componente -- se exponen ocupado/las acciones para que App.vue los invoque vía
// template ref, en vez de duplicar la lógica de guardado/versión/compilado allá arriba.
defineExpose({ ocupado, subirVersion, compilarDoc, abrirMetadatos: () => { mostrarMeta.value = true; } });
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
          class="editor-textarea"
          v-model="texto"
          :disabled="cargando"
          :slug="slug"
          :codigo="codigo"
          tipo="doc"
          @clic-en-editor="onClicEnEditor"
          @salto-no-editable="onSaltoNoEditable"
          @guardar="flushGuardado"
        />
        <TinymistPreview
          v-if="!usarPreviewLegacy"
          ref="tinymistPreviewRef"
          :slug="slug"
          :codigo="codigo"
          tipo="doc"
          @no-disponible="usarPreviewLegacy = true"
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
        :guardando="guardando"
        :guardado-hora="guardadoHora"
        :refresh-signal="refreshSignalLocal"
        @cargar-en-editor="onCargarEnEditor"
        @abrir-imagenes="mostrarImagenes = true"
      />
      <MetaEditorModal
        v-if="mostrarMeta"
        :slug="slug"
        :codigo="codigo"
        @guardado="onMetaGuardado"
        @cancelar="mostrarMeta = false"
      />
      <SubirImagenesModal
        v-if="mostrarImagenes"
        tipo="doc"
        :slug="slug"
        :nombre="codigo"
        @cerrar="mostrarImagenes = false"
        @cambiado="onImagenesCambiadas"
      />
    </template>
  </div>
</template>
