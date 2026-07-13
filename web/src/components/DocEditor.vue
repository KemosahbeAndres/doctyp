<script setup>
import { ref, computed, watch } from "vue";
import { getTyp, putTyp, guardarVersion, compilar } from "../api.js";
import MetaEditorModal from "./MetaEditorModal.vue";

const props = defineProps({
  slug: { type: String, required: true },
  codigo: { type: String, default: null },
  doc: { type: Object, default: null },
  restaurarPayload: { type: Object, default: null },
});

const emit = defineEmits(["sucio-cambio", "cambio-en-servidor"]);

const texto = ref("");
const original = ref("");
const cargando = ref(false);
const ocupado = ref(false);
const mensaje = ref("");
const mensajeEsError = ref(false);
const mostrarMeta = ref(false);

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

watch(
  () => props.restaurarPayload,
  (payload) => {
    if (payload) {
      texto.value = payload.contenido;
      mensaje.value = `Versión v${payload.version} cargada en el editor (sin guardar aún).`;
      mensajeEsError.value = false;
    }
  },
);

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
    emit("cambio-en-servidor");
  } catch (e) {
    mensaje.value = `Error al compilar: ${e.message}`;
    mensajeEsError.value = true;
  } finally {
    ocupado.value = false;
  }
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
</script>

<template>
  <div class="panel panel-editor">
    <div v-if="!codigo" class="empty-state">Selecciona un documento para editarlo.</div>
    <template v-else>
      <div class="editor-toolbar">
        <strong>{{ doc?.codigo_base || codigo }}</strong>
        <span class="estado">
          {{ cargando ? "Cargando…" : sucio ? "cambios sin guardar" : "sin cambios pendientes" }}
        </span>
        <button :disabled="!sucio || ocupado || cargando" @click="guardarCambios">Guardar cambios</button>
        <button class="primary" :disabled="ocupado || cargando" @click="subirVersion">Subir versión</button>
        <button :disabled="ocupado || cargando" @click="compilarDoc">Compilar</button>
        <button :disabled="ocupado || cargando" @click="mostrarMeta = true">Metadatos</button>
        <span class="estado" :style="{ color: mensajeEsError ? 'var(--danger)' : undefined }">
          {{ mensaje }}
        </span>
      </div>
      <textarea
        class="editor-textarea"
        v-model="texto"
        :disabled="cargando"
        spellcheck="false"
      ></textarea>
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
