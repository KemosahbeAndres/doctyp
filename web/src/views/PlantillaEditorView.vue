<script setup>
import { ref } from "vue";
import { useRoute, useRouter, onBeforeRouteLeave, onBeforeRouteUpdate } from "vue-router";
import TemplateEditor from "../components/TemplateEditor.vue";
import { useOrgContext } from "../composables/useOrgContext.js";

const route = useRoute();
const router = useRouter();
const { orgSlug, plantillaEditorSucio, cargarPlantillas } = useOrgContext();

const refPlantillaEditor = ref(null);

function confirmarSalida(mensaje) {
  return !plantillaEditorSucio.value || window.confirm(mensaje);
}

onBeforeRouteLeave((to, from, next) => {
  next(confirmarSalida("Tienes cambios sin guardar en la plantilla. ¿Salir igualmente?"));
});

onBeforeRouteUpdate((to, from, next) => {
  next(confirmarSalida("Tienes cambios sin guardar en la plantilla. ¿Descartarlos y cambiar de plantilla?"));
});

function volver() {
  if (!confirmarSalida("Tienes cambios sin guardar en la plantilla. ¿Volver a la cuadrícula igualmente?")) return;
  router.push("/plantillas");
}
</script>

<template>
  <div class="vista-documento">
    <div class="documento-header">
      <button @click="volver">← Plantillas</button>
      <strong>{{ route.params.nombre }}</strong>
      <span class="status-bar-spacer"></span>
      <button class="primary" :disabled="refPlantillaEditor?.ocupado" @click="refPlantillaEditor?.guardar()">Guardar plantilla</button>
    </div>
    <!-- Mismo motivo que DocumentoEditorView.vue: en un refresh directo orgSlug aún es null
         mientras cargarOrgs() resuelve -- sin la guarda, TemplateEditor monta con slug=null. -->
    <div v-if="!orgSlug" class="empty-state">Cargando organización…</div>
    <TemplateEditor
      v-else
      ref="refPlantillaEditor"
      :slug="orgSlug"
      :nombre="route.params.nombre"
      @sucio-cambio="plantillaEditorSucio = $event"
      @guardado="cargarPlantillas"
    />
  </div>
</template>
