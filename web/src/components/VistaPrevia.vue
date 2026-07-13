<script setup>
import { ref, watch, onUnmounted } from "vue";
import { compilarVistaPrevia } from "../api.js";

const props = defineProps({
  slug: { type: String, required: true },
  codigo: { type: String, required: true },
  texto: { type: String, default: "" },
});

const pdfUrl = ref(null);
const compilando = ref(false);
const error = ref("");

let temporizador = null;

function revocarUrlAnterior() {
  if (pdfUrl.value) {
    URL.revokeObjectURL(pdfUrl.value);
    pdfUrl.value = null;
  }
}

async function compilar() {
  compilando.value = true;
  try {
    const blob = await compilarVistaPrevia(props.slug, props.codigo, props.texto);
    const nuevaUrl = URL.createObjectURL(blob);
    revocarUrlAnterior();
    pdfUrl.value = nuevaUrl;
    error.value = "";
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
  () => compilar(),
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
  revocarUrlAnterior();
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
    <embed v-else-if="pdfUrl" :src="pdfUrl" type="application/pdf" class="vista-previa-embed" />
    <div v-else class="empty-state">{{ compilando ? "Compilando…" : "Sin vista previa aún." }}</div>
  </div>
</template>
