<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { fijarPlantillaDefault, eliminarPlantilla } from "../api.js";
import PlantillaGrid from "../components/PlantillaGrid.vue";
import NewTemplateModal from "../components/NewTemplateModal.vue";
import { useOrgContext } from "../composables/useOrgContext.js";

const router = useRouter();
const { orgSlug, plantillas, cargandoPlantillas, cargarPlantillas, error } = useOrgContext();

const mostrarNuevaPlantilla = ref(false);

function seleccionar(nombre) {
  router.push(`/plantillas/${nombre}`);
}

async function marcarDefault(p) {
  try {
    await fijarPlantillaDefault(orgSlug.value, p.nombre);
    await cargarPlantillas();
  } catch (e) {
    error.value = e.message;
  }
}

async function eliminar(p) {
  if (!window.confirm(`¿Eliminar la plantilla "${p.nombre}"? Los documentos ya creados con ella no se ven afectados.`)) return;
  try {
    await eliminarPlantilla(orgSlug.value, p.nombre);
    await cargarPlantillas();
  } catch (e) {
    error.value = e.message;
  }
}

function onPlantillaCreada() {
  mostrarNuevaPlantilla.value = false;
  cargarPlantillas();
}
</script>

<template>
  <PlantillaGrid
    :slug="orgSlug"
    :plantillas="plantillas"
    :cargando="cargandoPlantillas"
    @seleccionar="seleccionar"
    @nuevo="mostrarNuevaPlantilla = true"
    @default="marcarDefault"
    @eliminar="eliminar"
  />
  <NewTemplateModal
    v-if="mostrarNuevaPlantilla"
    :slug="orgSlug"
    :plantillas="plantillas"
    @creada="onPlantillaCreada"
    @cancelar="mostrarNuevaPlantilla = false"
  />
</template>
