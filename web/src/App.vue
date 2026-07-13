<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import { listOrgs, listDocs, suscribirEventos } from "./api.js";
import DocList from "./components/DocList.vue";
import DocEditor from "./components/DocEditor.vue";
import HistoryPanel from "./components/HistoryPanel.vue";
import NewDocumentModal from "./components/NewDocumentModal.vue";

const orgs = ref([]);
const orgSlug = ref(null);
const docs = ref([]);
const cargandoDocs = ref(false);
const docSeleccionado = ref(null);
const error = ref("");
const editorSucio = ref(false);
const restaurarPayload = ref(null);
const refreshSignal = ref(0);
const mostrarNuevo = ref(false);

const docActivo = computed(() => docs.value.find((d) => d.codigo_base === docSeleccionado.value) || null);

async function cargarOrgs() {
  try {
    orgs.value = await listOrgs();
    if (!orgSlug.value) {
      const activa = orgs.value.find((o) => o.activa);
      orgSlug.value = activa ? activa.slug : orgs.value[0]?.slug ?? null;
    }
  } catch (e) {
    error.value = `No se pudieron cargar las organizaciones: ${e.message}`;
  }
}

async function cargarDocs() {
  if (!orgSlug.value) {
    docs.value = [];
    return;
  }
  cargandoDocs.value = true;
  try {
    docs.value = await listDocs(orgSlug.value);
  } catch (e) {
    error.value = `No se pudieron cargar los documentos: ${e.message}`;
  } finally {
    cargandoDocs.value = false;
  }
}

watch(orgSlug, () => {
  docSeleccionado.value = null;
  cargarDocs();
});

function seleccionarDoc(codigo) {
  if (codigo === docSeleccionado.value) return;
  if (editorSucio.value && !window.confirm("Tienes cambios sin guardar en el editor. ¿Descartarlos y cambiar de documento?")) {
    return;
  }
  restaurarPayload.value = null;
  docSeleccionado.value = codigo;
}

function onCambioEnServidor() {
  cargarDocs();
  refreshSignal.value++;
}

function onCargarEnEditor(payload) {
  restaurarPayload.value = { contenido: payload.contenido, version: payload.version };
}

async function onDocumentoCreado(doc) {
  mostrarNuevo.value = false;
  await cargarDocs();
  seleccionarDoc(doc.codigo_base);
}

let cancelarEventos = null;

onMounted(() => {
  cargarOrgs();
  cancelarEventos = suscribirEventos((evento) => {
    if (evento.tipo === "docs-changed") {
      cargarDocs();
      refreshSignal.value++;
    } else if (evento.tipo === "org-changed") {
      cargarOrgs();
    }
  });
});

onUnmounted(() => {
  if (cancelarEventos) cancelarEventos();
});
</script>

<template>
  <div class="app-shell">
    <div class="topbar">
      <h1>doctyp</h1>
      <select v-model="orgSlug">
        <option v-for="o in orgs" :key="o.slug" :value="o.slug">
          {{ o.nombre }}{{ o.activa ? " (activa)" : "" }}
        </option>
      </select>
    </div>
    <div v-if="error" class="error-banner">{{ error }}</div>
    <div class="main-layout">
      <DocList
        :docs="docs"
        :seleccionado="docSeleccionado"
        :cargando="cargandoDocs"
        @seleccionar="seleccionarDoc"
        @nuevo="mostrarNuevo = true"
      />
      <DocEditor
        :slug="orgSlug"
        :codigo="docSeleccionado"
        :doc="docActivo"
        :restaurar-payload="restaurarPayload"
        @sucio-cambio="editorSucio = $event"
        @cambio-en-servidor="onCambioEnServidor"
      />
      <HistoryPanel :slug="orgSlug" :codigo="docSeleccionado" :refresh-signal="refreshSignal" @cargar-en-editor="onCargarEnEditor" />
    </div>
    <NewDocumentModal
      v-if="mostrarNuevo"
      :slug="orgSlug"
      @creado="onDocumentoCreado"
      @cancelar="mostrarNuevo = false"
    />
  </div>
</template>
