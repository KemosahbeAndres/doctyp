<script setup>
import { ref, computed } from "vue";
import { useRoute, useRouter, onBeforeRouteLeave, onBeforeRouteUpdate } from "vue-router";
import DocEditor from "../components/DocEditor.vue";
import { useOrgContext } from "../composables/useOrgContext.js";

const route = useRoute();
const router = useRouter();
const { orgSlug, docActivo, editorSucio, cargarDocs } = useOrgContext();

const refDocEditor = ref(null);
const docActivoComputado = computed(() => docActivo(route.params.codigo));

function confirmarSalida(mensaje) {
  return !editorSucio.value || window.confirm(mensaje);
}

// Cubre salir de esta ruta hacia cualquier otra (Documentos, Plantillas, Organización, u otro
// documento -- aunque para "otro documento" en verdad dispara onBeforeRouteUpdate, ver abajo,
// porque Vue Router reusa el componente cuando solo cambia el param).
onBeforeRouteLeave((to, from, next) => {
  next(confirmarSalida("Tienes cambios sin guardar en el editor. ¿Salir igualmente?"));
});

// Cubre cambiar de documento sin salir de /documentos/:codigo (p. ej. otra pestaña navegó a un
// codigo distinto) -- Vue Router reutiliza esta misma instancia de componente en ese caso, así
// que onBeforeRouteLeave no se dispara.
onBeforeRouteUpdate((to, from, next) => {
  next(confirmarSalida("Tienes cambios sin guardar en el editor. ¿Descartarlos y cambiar de documento?"));
});

function volver() {
  if (!confirmarSalida("Tienes cambios sin guardar en el editor. ¿Volver a la cuadrícula igualmente?")) return;
  router.push("/documentos");
}

function onCambioEnServidor() {
  cargarDocs();
}
</script>

<template>
  <div class="vista-documento">
    <div class="documento-header">
      <button @click="volver">← Documentos</button>
      <strong>{{ docActivoComputado?.codigo_base || route.params.codigo }}</strong>
      <span class="estado">{{ docActivoComputado?.titulo }}</span>
      <span class="status-bar-spacer"></span>
      <button class="primary" :disabled="refDocEditor?.ocupado" @click="refDocEditor?.subirVersion()">Subir versión</button>
      <button :disabled="refDocEditor?.ocupado" @click="refDocEditor?.compilarDoc()">Compilar</button>
      <button :disabled="refDocEditor?.ocupado" @click="refDocEditor?.abrirMetadatos()">Metadatos</button>
    </div>
    <!-- En un refresh directo de /documentos/:codigo, orgSlug todavía es null hasta que
         cargarOrgs() (App.vue: onMounted) resuelve -- sin esta guarda, DocEditor montaba de
         inmediato con slug=null y disparaba "no existe la organización 'null'". -->
    <div v-if="!orgSlug" class="empty-state">Cargando organización…</div>
    <DocEditor
      v-else
      ref="refDocEditor"
      :slug="orgSlug"
      :codigo="route.params.codigo"
      @sucio-cambio="editorSucio = $event"
      @cambio-en-servidor="onCambioEnServidor"
    />
  </div>
</template>
