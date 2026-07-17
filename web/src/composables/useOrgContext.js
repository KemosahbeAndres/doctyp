import { ref, computed, watch } from "vue";
import { listOrgs, listDocs, listAutores, activarOrg, listPlantillas, suscribirEventos } from "../api.js";
import { emitirEditorScrollTo } from "./editorScrollToBus.js";
import { emitirCompileStatus } from "./compileStatusBus.js";

// Estado compartido entre App.vue (topbar, fuera del router-view) y las vistas (dentro del
// router-view) -- mismo patrón "bus" de módulo-singleton que editorScrollToBus.js/
// compileStatusBus.js (el proyecto no usa store, ver nota Etapa 5 en CLAUDE.md). Antes vivía
// todo en App.vue; con el router, las vistas necesitan el mismo estado sin prop-drilling a
// través de <router-view>.
const orgs = ref([]);
const orgSlug = ref(null);
const docs = ref([]);
const autores = ref([]);
const autorActivoId = ref(null);
const cargandoDocs = ref(false);
const plantillas = ref([]);
const cargandoPlantillas = ref(false);
const error = ref("");

// Cambios sin guardar en el editor de documento/plantilla activo -- lo setean
// DocumentoEditorView.vue/PlantillaEditorView.vue vía @sucio-cambio; App.vue los consulta antes
// de cambiar de autor activo (cambiarAutorActivo, abajo).
const editorSucio = ref(false);
const plantillaEditorSucio = ref(false);

// Función simple, no computed -- se usa dentro de un computed local en las vistas que la
// necesitan (p. ej. `computed(() => docActivo(route.params.codigo))`), donde sí se trackea.
function docActivo(codigo) {
  return docs.value.find((d) => d.codigo_base === codigo) || null;
}
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

// Recarga docs/autores/plantillas cada vez que cambia la org activa -- sea por el selector del
// topbar (cambiarOrgActiva) o por crear una org nueva (App.vue asigna orgSlug directo tras
// crearla). Antes esto vivía en un watch(orgSlug, ...) dentro de App.vue.
watch(orgSlug, () => {
  cargarDocs();
  cargarAutores();
  cargarPlantillas();
});

async function cambiarOrgActiva(slug) {
  if (slug === orgSlug.value) return;
  orgSlug.value = slug;
  if (slug) activarOrg(slug).catch(() => {});
}

let cancelarEventos = null;
let iniciado = false;

/** Llamado una sola vez desde App.vue: onMounted -- carga todo y arma la suscripción SSE. */
function iniciar() {
  if (iniciado) return;
  iniciado = true;
  cargarOrgs();
  cancelarEventos = suscribirEventos((evento) => {
    if (evento.tipo === "docs-changed") {
      cargarDocs();
    } else if (evento.tipo === "org-changed") {
      cargarOrgs();
      cargarAutores();
    } else if (evento.tipo === "editor-scroll-to") {
      emitirEditorScrollTo(evento);
    } else if (evento.tipo === "compile-status") {
      emitirCompileStatus(evento);
    } else if (evento.tipo === "doc-saved") {
      cargarDocs();
    } else if (evento.tipo === "plantilla-guardada") {
      cargarPlantillas();
    }
  });
}

function detener() {
  if (cancelarEventos) cancelarEventos();
  cancelarEventos = null;
  iniciado = false;
}

export function useOrgContext() {
  return {
    orgs, orgSlug, docs, docsFiltrados, docActivo, autores, autorActivoId,
    cargandoDocs, plantillas, cargandoPlantillas, error, editorSucio, plantillaEditorSucio,
    cargarOrgs, cargarDocs, cargarAutores, cargarPlantillas, cambiarOrgActiva,
    iniciar, detener,
  };
}
