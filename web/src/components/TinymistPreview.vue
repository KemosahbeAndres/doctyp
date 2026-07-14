<script setup>
import { ref, watch, onUnmounted } from "vue";
import { getPreviewInfo, getPreviewInfoPlantilla } from "../api.js";

// Plan 15 F3: reemplaza la vista previa typst.ts (Etapa 12.1) por el frontend real de
// tinymist, servido por el subproceso que arranca doctyp_web.py (ver doctyp_preview_server.py).
// Solo se cambia CÓMO se renderiza -- el guardado/versionado del documento no se toca. El
// backend mantiene la conexión persistente al control plane (clic<->cursor, F5/F6); este
// componente únicamente monta el <iframe> con el frontend estático que tinymist ya sirve.
//
// Extendido para plantillas: `tipo="plantilla"` usa el .typ de muestra materializado en disco
// (ver core.asegurar_muestra_typ / _asegurar_preview_plantilla en doctyp_web.py) en vez del
// documento real -- el usuario sigue editando lib.typ, no ese archivo de muestra.
const props = defineProps({
  slug: { type: String, required: true },
  codigo: { type: String, required: true },
  tipo: { type: String, default: "doc" }, // "doc" | "plantilla"
});

const emit = defineEmits(["no-disponible", "saltar-aqui"]);

const cargando = ref(true);
const error = ref("");
const staticUrl = ref("");

async function conectar() {
  cargando.value = true;
  error.value = "";
  staticUrl.value = "";
  try {
    const info = props.tipo === "plantilla"
      ? await getPreviewInfoPlantilla(props.slug, props.codigo)
      : await getPreviewInfo(props.slug, props.codigo);
    if (!info.enabled) {
      // tinymist no está disponible -- el padre decide si cae a la vista previa legacy.
      emit("no-disponible");
      return;
    }
    staticUrl.value = info.static_url;
  } catch (e) {
    error.value = e.message;
  } finally {
    cargando.value = false;
  }
}

watch(() => [props.slug, props.codigo, props.tipo], conectar, { immediate: true });

onUnmounted(() => {
  // El subproceso de tinymist sigue vivo en el backend (una preview a la vez, ver
  // doctyp_web.py) -- no hay nada que limpiar acá al desmontar el iframe.
});
</script>

<template>
  <div class="vista-previa">
    <div class="vista-previa-toolbar">
      <button v-if="cargando" disabled>Conectando con la vista previa…</button>
      <button
        v-else
        title="Salto explícito: lleva la vista previa a la posición del cursor en el editor (Ctrl+Alt+J). No se hace automáticamente al mover el cursor ni al scrollear."
        @click="emit('saltar-aqui')"
      >
        Ver posición del cursor (Ctrl+Alt+J)
      </button>
    </div>
    <div v-if="error" class="vista-previa-error">
      <pre>{{ error }}</pre>
    </div>
    <iframe
      v-else-if="staticUrl"
      class="vista-previa-iframe"
      :src="staticUrl"
      title="Vista previa del documento"
    ></iframe>
    <div v-else-if="cargando" class="empty-state">Iniciando la vista previa…</div>
  </div>
</template>

<style>
.vista-previa-iframe {
  flex: 1;
  width: 100%;
  border: none;
  background: #fff;
}
</style>
