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

const emit = defineEmits(["no-disponible"]);

const cargando = ref(true);
const error = ref("");
const staticUrl = ref("");
// Pedido explícito del usuario: botón para refrescar el render a la fuerza -- a diferencia de
// reconectar()/onIframeError (silenciosos, NO tocan el iframe si la URL no cambió, para no
// perder el zoom/scroll del usuario en cada autoguardado), este SIEMPRE remonta el <iframe>
// aunque la URL sea idéntica. Se fuerza cambiando `key` (no basta con reasignar :src al mismo
// valor -- el navegador podría no recargar, y aunque recargara, Vue no destruye/recrea el
// elemento solo porque el atributo no cambió).
const iframeKey = ref(0);

// GET /api/preview/info arranca/reutiliza el subproceso tinymist si no está corriendo
// (ver _asegurar_preview_generico en doctyp_web.py) -- así que basta con volver a llamarlo para
// "asegurar tinymist" desde el cliente, sin endpoint nuevo. Se reusa como señal explícita en dos
// casos que el montaje inicial no cubre: (1) tras cada autoguardado, por si tinymist cayó justo
// antes de que el usuario mandara cambios nuevos -- ver reconectar() expuesto abajo; (2) cuando
// el propio iframe deja de responder mientras el usuario solo miraba la preview sin escribir.
//
// IMPORTANTE (pedido explícito del usuario): en el caso normal (tinymist sigue vivo) esto NO
// debe tocar el <iframe> -- remontarlo reinicia el frontend embebido de tinymist y pierde el
// zoom/scroll que el usuario dejó ahí. Como cada reinicio real de tinymist pide un puerto nuevo
// (_puerto_libre() en doctyp_preview_server.py), `static_url` cambia solo cuando el proceso
// cambió de verdad -- basta con dejar que Vue actualice `:src` normalmente (no destruye el
// elemento) y NUNCA vaciar staticUrl a propósito.
async function conectar({ silencioso = false } = {}) {
  if (!silencioso) {
    cargando.value = true;
    error.value = "";
    staticUrl.value = "";
  }
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
    if (!silencioso) error.value = e.message;
  } finally {
    if (!silencioso) cargando.value = false;
  }
}

watch(() => [props.slug, props.codigo, props.tipo], () => conectar(), { immediate: true });

// El iframe deja de emitir cualquier señal si el proceso tinymist detrás muere mientras el
// usuario solo está mirando (sin escribir) -- no hay evento de "el servidor remoto murió" desde
// dentro de un <iframe> cross-origin-ish (mismo host, pero contenido ajeno), así que se usa
// `onerror` del propio elemento (dispara si la carga falla o si el server cierra la conexión de
// forma abrupta) como señal para reasegurar.
function onIframeError() {
  conectar({ silencioso: true });
}

async function refrescarForzado() {
  await conectar({ silencioso: true }); // reasegura tinymist por si acaso, sin tocar el iframe
  iframeKey.value += 1; // fuerza el remount aunque static_url no haya cambiado
}

// Expuesto para que DocEditor.vue/TemplateEditor.vue lo llamen fire-and-forget tras cada
// autoguardado exitoso -- reasegura tinymist ANTES de confiar en que el iframe se actualizará
// solo (pedido explícito del usuario: el cliente debe avisarle al backend que va a compilar).
// refrescarForzado también se expone por si el padre quiere ofrecer su propio botón/atajo.
defineExpose({ reconectar: () => conectar({ silencioso: true }), refrescarForzado });

onUnmounted(() => {
  // El subproceso de tinymist sigue vivo en el backend (una preview a la vez, ver
  // doctyp_web.py) -- no hay nada que limpiar acá al desmontar el iframe.
});
</script>

<template>
  <div class="vista-previa">
    <div v-if="cargando" class="vista-previa-toolbar">
      <span class="estado">Conectando con la vista previa…</span>
    </div>
    <div v-else-if="staticUrl" class="vista-previa-toolbar">
      <button type="button" title="Refrescar el render a la fuerza" @click="refrescarForzado">
        ↻ Refrescar vista previa
      </button>
    </div>
    <div v-if="error" class="vista-previa-error">
      <pre>{{ error }}</pre>
    </div>
    <iframe
      v-else-if="staticUrl"
      :key="iframeKey"
      class="vista-previa-iframe"
      :src="staticUrl"
      title="Vista previa del documento"
      @error="onIframeError"
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

.vista-previa-toolbar {
  padding: 0.3em 0.5em;
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: flex-end;
}

.vista-previa-toolbar button {
  font-size: 0.8rem;
  padding: 0.2em 0.6em;
}
</style>
