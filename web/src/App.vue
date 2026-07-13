<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import {
  listOrgs, listDocs, listAutores, activarOrg, activarAutor, suscribirEventos,
  listPlantillas, fijarPlantillaDefault, eliminarPlantilla,
} from "./api.js";
import DocumentGrid from "./components/DocumentGrid.vue";
import DocEditor from "./components/DocEditor.vue";
import NewDocumentModal from "./components/NewDocumentModal.vue";
import NewOrgModal from "./components/NewOrgModal.vue";
import OrgManager from "./components/OrgManager.vue";
import PlantillaGrid from "./components/PlantillaGrid.vue";
import TemplateEditor from "./components/TemplateEditor.vue";
import NewTemplateModal from "./components/NewTemplateModal.vue";

const orgs = ref([]);
const orgSlug = ref(null);
const docs = ref([]);
const autores = ref([]);
const autorActivoId = ref(null);
const cargandoDocs = ref(false);
const docSeleccionado = ref(null);
const vista = ref("grid"); // "grid" | "documento" | "plantillas" | "plantilla"
const error = ref("");
const editorSucio = ref(false);
const mostrarNuevo = ref(false);
const mostrarNuevaOrg = ref(false);
const mostrarGestor = ref(false);
const plantillas = ref([]);
const cargandoPlantillas = ref(false);
const plantillaSeleccionada = ref(null);
const plantillaEditorSucio = ref(false);
const mostrarNuevaPlantilla = ref(false);

const docActivo = computed(() => docs.value.find((d) => d.codigo_base === docSeleccionado.value) || null);
const docsFiltrados = computed(() =>
  autorActivoId.value ? docs.value.filter((d) => d.autor_id === autorActivoId.value) : docs.value,
);

async function cargarOrgs() {
  try {
    orgs.value = await listOrgs();
    if (!orgSlug.value) {
      const activa = orgs.value.find((o) => o.activa);
      orgSlug.value = activa ? activa.slug : orgs.value[0]?.slug ?? null;
    }
  } catch (e) {
    error.value = `No se pudieron cargar las organizaciones: ${e.message}`;
  }
}

async function cargarDocs() {
  if (!orgSlug.value) {
    docs.value = [];
    return;
  }
  cargandoDocs.value = true;
  try {
    docs.value = await listDocs(orgSlug.value);
  } catch (e) {
    error.value = `No se pudieron cargar los documentos: ${e.message}`;
  } finally {
    cargandoDocs.value = false;
  }
}

async function cargarAutores() {
  if (!orgSlug.value) {
    autores.value = [];
    autorActivoId.value = null;
    return;
  }
  try {
    autores.value = await listAutores(orgSlug.value);
    const activo = autores.value.find((a) => a.activo);
    autorActivoId.value = activo ? activo.id : null;
  } catch (e) {
    error.value = `No se pudieron cargar los autores: ${e.message}`;
  }
}

async function cargarPlantillas() {
  if (!orgSlug.value) {
    plantillas.value = [];
    return;
  }
  cargandoPlantillas.value = true;
  try {
    plantillas.value = await listPlantillas(orgSlug.value);
  } catch (e) {
    error.value = `No se pudieron cargar las plantillas: ${e.message}`;
  } finally {
    cargandoPlantillas.value = false;
  }
}

watch(orgSlug, (slug) => {
  docSeleccionado.value = null;
  plantillaSeleccionada.value = null;
  vista.value = "grid";
  cargarDocs();
  cargarAutores();
  cargarPlantillas();
  if (slug) activarOrg(slug).catch(() => {});
});

function seleccionarDoc(codigo) {
  if (codigo !== docSeleccionado.value) {
    if (editorSucio.value && !window.confirm("Tienes cambios sin guardar en el editor. ¿Descartarlos y cambiar de documento?")) {
      return;
    }
    docSeleccionado.value = codigo;
  }
  vista.value = "documento";
}

function volverAGrid() {
  if (editorSucio.value && !window.confirm("Tienes cambios sin guardar en el editor. ¿Volver a la cuadrícula igualmente?")) {
    return;
  }
  vista.value = "grid";
}

function irADocumentos() {
  if (vista.value === "documento" && editorSucio.value
    && !window.confirm("Tienes cambios sin guardar en el editor. ¿Salir igualmente?")) {
    return;
  }
  if (vista.value === "plantilla" && plantillaEditorSucio.value
    && !window.confirm("Tienes cambios sin guardar en la plantilla. ¿Salir igualmente?")) {
    return;
  }
  vista.value = "grid";
  cargarDocs();
}

function irAPlantillas() {
  if (vista.value === "documento" && editorSucio.value
    && !window.confirm("Tienes cambios sin guardar en el editor. ¿Salir igualmente?")) {
    return;
  }
  if (vista.value === "plantilla" && plantillaEditorSucio.value
    && !window.confirm("Tienes cambios sin guardar en la plantilla. ¿Salir igualmente?")) {
    return;
  }
  vista.value = "plantillas";
  cargarPlantillas();
}

function seleccionarPlantilla(nombre) {
  if (nombre !== plantillaSeleccionada.value) {
    if (plantillaEditorSucio.value && !window.confirm("Tienes cambios sin guardar en la plantilla. ¿Descartarlos y cambiar de plantilla?")) {
      return;
    }
    plantillaSeleccionada.value = nombre;
  }
  vista.value = "plantilla";
}

function volverAPlantillas() {
  if (plantillaEditorSucio.value && !window.confirm("Tienes cambios sin guardar en la plantilla. ¿Volver a la cuadrícula igualmente?")) {
    return;
  }
  vista.value = "plantillas";
}

async function marcarDefaultPlantilla(p) {
  try {
    await fijarPlantillaDefault(orgSlug.value, p.nombre);
    await cargarPlantillas();
  } catch (e) {
    error.value = e.message;
  }
}

async function eliminarPlantillaGrid(p) {
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

async function cambiarAutorActivo(id) {
  if (id === autorActivoId.value) return;
  if (editorSucio.value && !window.confirm("Tienes cambios sin guardar en el editor. ¿Descartarlos y cambiar de autor activo?")) {
    return;
  }
  try {
    await activarAutor(orgSlug.value, id);
  } catch (e) {
    error.value = `No se pudo activar el autor: ${e.message}`;
    return;
  }
  autorActivoId.value = id;
  if (docActivo.value && docActivo.value.autor_id !== id) {
    docSeleccionado.value = null;
    vista.value = "grid";
  }
}

function onCambioEnServidor() {
  cargarDocs();
}

async function onDocumentoCreado(doc) {
  mostrarNuevo.value = false;
  await cargarDocs();
  seleccionarDoc(doc.codigo_base);
}

async function onOrgCreada(org) {
  mostrarNuevaOrg.value = false;
  await cargarOrgs();
  orgSlug.value = org.slug;
}

async function onCambioOrgManager() {
  await cargarAutores();
  await cargarDocs();
}

let cancelarEventos = null;

onMounted(() => {
  cargarOrgs();
  cancelarEventos = suscribirEventos((evento) => {
    if (evento.tipo === "docs-changed") {
      cargarDocs();
    } else if (evento.tipo === "org-changed") {
      cargarOrgs();
      cargarAutores();
    }
  });
});

onUnmounted(() => {
  if (cancelarEventos) cancelarEventos();
});
</script>

<template>
  <div class="app-shell">
    <div class="topbar">
      <h1>doctyp</h1>
      <div class="topbar-group">
        <select v-model="orgSlug">
          <option v-for="o in orgs" :key="o.slug" :value="o.slug">
            {{ o.nombre }}{{ o.activa ? " (activa)" : "" }}
          </option>
        </select>
        <button title="Nueva organización" @click="mostrarNuevaOrg = true">+</button>
      </div>
      <select :value="autorActivoId" @change="cambiarAutorActivo($event.target.value)">
        <option v-for="a in autores" :key="a.id" :value="a.id">
          {{ a.nombre }}{{ a.activo ? " (yo)" : "" }}
        </option>
      </select>
      <button title="Documentos" @click="irADocumentos">Documentos</button>
      <button title="Editor de plantillas" @click="irAPlantillas">Plantillas</button>
      <button title="Gestionar organización" @click="mostrarGestor = true">⚙ Organización</button>
    </div>
    <div v-if="error" class="error-banner">{{ error }}</div>

    <DocumentGrid
      v-if="vista === 'grid'"
      :slug="orgSlug"
      :docs="docsFiltrados"
      :cargando="cargandoDocs"
      @seleccionar="seleccionarDoc"
      @nuevo="mostrarNuevo = true"
    />
    <div v-else-if="vista === 'documento'" class="vista-documento">
      <div class="documento-header">
        <button @click="volverAGrid">← Documentos</button>
        <strong>{{ docActivo?.codigo_base || docSeleccionado }}</strong>
        <span class="estado">{{ docActivo?.titulo }}</span>
      </div>
      <DocEditor
        :slug="orgSlug"
        :codigo="docSeleccionado"
        @sucio-cambio="editorSucio = $event"
        @cambio-en-servidor="onCambioEnServidor"
      />
    </div>
    <PlantillaGrid
      v-else-if="vista === 'plantillas'"
      :slug="orgSlug"
      :plantillas="plantillas"
      :cargando="cargandoPlantillas"
      @seleccionar="seleccionarPlantilla"
      @nuevo="mostrarNuevaPlantilla = true"
      @default="marcarDefaultPlantilla"
      @eliminar="eliminarPlantillaGrid"
    />
    <div v-else-if="vista === 'plantilla'" class="vista-documento">
      <div class="documento-header">
        <button @click="volverAPlantillas">← Plantillas</button>
        <strong>{{ plantillaSeleccionada }}</strong>
      </div>
      <TemplateEditor
        :slug="orgSlug"
        :nombre="plantillaSeleccionada"
        @sucio-cambio="plantillaEditorSucio = $event"
        @guardado="cargarPlantillas"
      />
    </div>

    <NewDocumentModal
      v-if="mostrarNuevo"
      :slug="orgSlug"
      @creado="onDocumentoCreado"
      @cancelar="mostrarNuevo = false"
    />
    <NewOrgModal v-if="mostrarNuevaOrg" @creada="onOrgCreada" @cancelar="mostrarNuevaOrg = false" />
    <OrgManager
      v-if="mostrarGestor"
      :slug="orgSlug"
      @cerrar="mostrarGestor = false"
      @cambio="onCambioOrgManager"
    />
    <NewTemplateModal
      v-if="mostrarNuevaPlantilla"
      :slug="orgSlug"
      :plantillas="plantillas"
      @creada="onPlantillaCreada"
      @cancelar="mostrarNuevaPlantilla = false"
    />
  </div>
</template>
