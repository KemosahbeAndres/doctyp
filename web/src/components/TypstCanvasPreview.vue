<script setup>
import { ref, watch, onUnmounted } from "vue";
import { compilarYRenderizar, reiniciarProyecto } from "../typst-wasm/client.js";

const props = defineProps({
  slug: { type: String, required: true },
  codigo: { type: String, required: true },
  texto: { type: String, default: "" },
  // (slug, codigo, texto) => Promise<{ mainTexto, archivos: {ruta, bytes}[] }>
  // Encapsula la diferencia documento/plantilla (mismo patrón que compilar-fn en la Etapa 10).
  cargarArchivos: { type: Function, required: true },
});

const contenedor = ref(null);
const compilando = ref(false);
const error = ref("");

let temporizador = null;

async function compilar() {
  if (!contenedor.value) return;
  compilando.value = true;
  try {
    const { mainTexto, archivos } = await props.cargarArchivos(props.slug, props.codigo, props.texto);
    const res = await compilarYRenderizar({
      slug: props.slug,
      codigo: props.codigo,
      mainTexto,
      archivos,
      contenedor: contenedor.value,
    });
    error.value = res.ok ? "" : res.diagnosticos.join("\n");
  } catch (e) {
    error.value = e.message;
  } finally {
    compilando.value = false;
  }
}

function actualizarAhora() {
  if (temporizador) clearTimeout(temporizador);
  compilar();
}

watch(
  () => props.codigo,
  async () => {
    await reiniciarProyecto();
    compilar();
  },
  { immediate: true },
);

watch(
  () => props.texto,
  () => {
    if (temporizador) clearTimeout(temporizador);
    temporizador = setTimeout(compilar, 1200);
  },
);

onUnmounted(() => {
  if (temporizador) clearTimeout(temporizador);
});

// Etapa 12.4: expone el elemento con scroll real (.vista-previa-canvas) para que el padre
// (DocEditor/TemplateEditor) pueda sincronizarlo con el scroll del editor de código.
defineExpose({
  getScroller: () => contenedor.value,
});
</script>

<template>
  <div class="vista-previa">
    <div class="vista-previa-toolbar">
      <button :disabled="compilando" @click="actualizarAhora">
        {{ compilando ? "Compilando…" : "Actualizar vista previa" }}
      </button>
    </div>
    <div v-if="error" class="vista-previa-error">
      <pre>{{ error }}</pre>
    </div>
    <div v-show="!error" ref="contenedor" class="vista-previa-canvas"></div>
  </div>
</template>
