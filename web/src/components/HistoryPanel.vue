<script setup>
import { ref, watch } from "vue";
import { getHistoria, getVersionContenido } from "../api.js";

const props = defineProps({
  slug: { type: String, required: true },
  codigo: { type: String, default: null },
  refreshSignal: { type: Number, default: 0 },
});

const emit = defineEmits(["cargar-en-editor"]);

const versiones = ref([]);
const cargando = ref(false);
const error = ref("");
const previa = ref(null); // { version, contenido }

function formatFecha(f) {
  return f && f.length === 8 ? `${f.slice(0, 4)}-${f.slice(4, 6)}-${f.slice(6)}` : f || "";
}

async function cargar() {
  previa.value = null;
  if (!props.codigo) {
    versiones.value = [];
    return;
  }
  cargando.value = true;
  error.value = "";
  try {
    versiones.value = await getHistoria(props.slug, props.codigo);
  } catch (e) {
    error.value = e.message;
  } finally {
    cargando.value = false;
  }
}

watch(() => props.codigo, cargar, { immediate: true });
watch(() => props.refreshSignal, cargar);

async function ver(version) {
  try {
    const contenido = await getVersionContenido(props.slug, props.codigo, version);
    previa.value = { version, contenido };
  } catch (e) {
    error.value = e.message;
  }
}

function cargarEnEditor() {
  if (previa.value) {
    emit("cargar-en-editor", { contenido: previa.value.contenido, version: previa.value.version });
  }
}
</script>

<template>
  <div class="panel panel-history">
    <div v-if="!codigo" class="empty-state">Selecciona un documento para ver su historial.</div>
    <template v-else>
      <div v-if="error" class="error-banner">{{ error }}</div>
      <div v-if="cargando" class="empty-state">Cargando historial…</div>
      <div v-else-if="!versiones.length" class="empty-state">Sin versiones registradas.</div>
      <div class="history-list">
        <div v-for="v in versiones" :key="v.version" class="version-row">
          <div><span class="version">v{{ v.version }}</span> <span class="fecha">{{ formatFecha(v.fecha) }}</span></div>
          <div class="mensaje">{{ v.mensaje }}</div>
          <div class="acciones">
            <button :disabled="!v.snapshot_disponible" @click="ver(v.version)">Ver</button>
            <span v-if="!v.snapshot_disponible" class="estado">(sin snapshot)</span>
          </div>
        </div>
      </div>
      <div v-if="previa" class="snapshot-preview">
        <div class="acciones" style="margin-bottom: 0.5em">
          <strong>v{{ previa.version }}</strong>
          <button class="primary" @click="cargarEnEditor">Cargar en editor</button>
          <button @click="previa = null">Cerrar</button>
        </div>
        <pre>{{ previa.contenido }}</pre>
      </div>
    </template>
  </div>
</template>
