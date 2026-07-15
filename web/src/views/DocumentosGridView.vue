<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import DocumentGrid from "../components/DocumentGrid.vue";
import NewDocumentModal from "../components/NewDocumentModal.vue";
import { useOrgContext } from "../composables/useOrgContext.js";

const router = useRouter();
const { orgSlug, docsFiltrados, cargandoDocs, cargarDocs } = useOrgContext();

const mostrarNuevo = ref(false);

function seleccionar(codigo) {
  router.push(`/documentos/${codigo}`);
}

async function onDocumentoCreado(doc) {
  mostrarNuevo.value = false;
  await cargarDocs();
  router.push(`/documentos/${doc.codigo_base}`);
}
</script>

<template>
  <DocumentGrid
    :slug="orgSlug"
    :docs="docsFiltrados"
    :cargando="cargandoDocs"
    @seleccionar="seleccionar"
    @nuevo="mostrarNuevo = true"
  />
  <NewDocumentModal
    v-if="mostrarNuevo"
    :slug="orgSlug"
    @creado="onDocumentoCreado"
    @cancelar="mostrarNuevo = false"
  />
</template>
