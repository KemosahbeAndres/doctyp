<script setup>
import { ref, computed, watch } from "vue";
import { getHistoria, getVersionDiff, getVersionContenido } from "../api.js";

const props = defineProps({
  slug: { type: String, required: true },
  codigo: { type: String, required: true },
  texto: { type: String, default: "" },
  sucio: { type: Boolean, default: false },
  ocupado: { type: Boolean, default: false },
  refreshSignal: { type: Number, default: 0 },
});

const emit = defineEmits(["guardar", "subir-version", "compilar", "metadatos", "cargar-en-editor"]);

const versiones = ref([]);
const error = ref("");
const diff = ref(null); // { version, filas }
const cargandoDiff = ref(false);

const versionActual = computed(() => versiones.value[0]?.version || "—");
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
</script>

<template>
  <div class="status-bar">
    <div v-if="error" class="error-banner">{{ error }}</div>
    <div class="status-bar-fila">
      <span class="status-badge">v{{ versionActual }}</span>
      <span class="estado">{{ sucio ? "cambios sin guardar" : "sin cambios pendientes" }}</span>
      <select @change="onCambioVersion">
        <option value="">Ver versión / diff…</option>
        <option v-for="v in versiones" :key="v.version" :value="v.version" :disabled="!v.snapshot_disponible">
          v{{ v.version }}{{ !v.snapshot_disponible ? " (sin snapshot)" : "" }}
        </option>
      </select>
      <span class="estado">{{ palabras }} palabras · {{ tamanoKB }} KB</span>
      <span class="status-bar-spacer"></span>
      <button :disabled="!sucio || ocupado" @click="emit('guardar')">Guardar</button>
      <button class="primary" :disabled="ocupado" @click="emit('subir-version')">Subir versión</button>
      <button :disabled="ocupado" @click="emit('compilar')">Compilar</button>
      <button :disabled="ocupado" @click="emit('metadatos')">Metadatos</button>
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
