<script setup>
import { ref, computed, onMounted, watch } from "vue";
import {
  getArchivosPlantilla, subirImagenPlantilla, eliminarArchivoPlantilla, renombrarArchivoPlantilla,
  getArchivosDoc, subirImagenDoc, eliminarArchivoDoc, renombrarArchivoDoc,
} from "../api.js";
import FileTreeNode from "./FileTreeNode.vue";

// Reemplaza a SubirImagenesModal.vue (retirado): sidebar de solo lectura/visualización de la
// carpeta del documento/plantilla, que además concentra la única gestión de imágenes permitida
// (subir/renombrar/eliminar), acotada a la carpeta propia -- img/ en documentos, Images/ en
// plantillas (§4 CLAUDE.md). Todo lo demás del árbol (el .typ, lib.typ, Images/ copiada dentro
// de un documento, fonts/) se ve pero no tiene acciones.
const props = defineProps({
  tipo: { type: String, default: "plantilla" }, // "plantilla" | "doc"
  slug: { type: String, required: true },
  nombre: { type: String, required: true },
});

const emit = defineEmits(["cambiado"]);

const CARPETA = props.tipo === "doc" ? "img" : "Images"; // sin "/" final -- se compara contra node.ruta.split("/")[0]
const _getArchivos = props.tipo === "doc" ? getArchivosDoc : getArchivosPlantilla;
const _subirImagen = props.tipo === "doc" ? subirImagenDoc : subirImagenPlantilla;
const _eliminarArchivo = props.tipo === "doc" ? eliminarArchivoDoc : eliminarArchivoPlantilla;
const _renombrarArchivo = props.tipo === "doc" ? renombrarArchivoDoc : renombrarArchivoPlantilla;

const EXTENSIONES_IMAGEN = new Set([".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif"]);

const archivos = ref([]); // rutas planas, tal como las devuelve el backend
const cargando = ref(true);
const subiendo = ref(false);
const error = ref("");
const arrastrando = ref(false);

const arbol = computed(() => construirArbol(archivos.value));

function construirArbol(rutas) {
  const raiz = { nombre: "", ruta: "", tipo: "dir", hijos: [] };
  for (const rutaCompleta of rutas) {
    const partes = rutaCompleta.split("/");
    let actual = raiz;
    let rutaAcum = "";
    partes.forEach((parte, i) => {
      rutaAcum = rutaAcum ? `${rutaAcum}/${parte}` : parte;
      const esArchivo = i === partes.length - 1;
      let hijo = actual.hijos.find((h) => h.nombre === parte);
      if (!hijo) {
        hijo = {
          nombre: parte,
          ruta: rutaAcum,
          tipo: esArchivo ? "file" : "dir",
          mutable: esArchivo && partes[0] === CARPETA,
          hijos: [],
        };
        actual.hijos.push(hijo);
      }
      actual = hijo;
    });
  }
  const ordenar = (nodo) => {
    nodo.hijos.sort((a, b) => {
      if (a.tipo !== b.tipo) return a.tipo === "dir" ? -1 : 1;
      return a.nombre.localeCompare(b.nombre);
    });
    nodo.hijos.forEach(ordenar);
  };
  ordenar(raiz);
  return raiz.hijos;
}

async function cargar() {
  cargando.value = true;
  error.value = "";
  try {
    archivos.value = await _getArchivos(props.slug, props.nombre);
  } catch (e) {
    error.value = e.message;
  } finally {
    cargando.value = false;
  }
}

onMounted(cargar);
watch(() => [props.slug, props.nombre], cargar);

function extensionValida(nombreArchivo) {
  const i = nombreArchivo.lastIndexOf(".");
  return i >= 0 && EXTENSIONES_IMAGEN.has(nombreArchivo.slice(i).toLowerCase());
}

async function subirArchivos(files) {
  const lista = Array.from(files || []);
  if (!lista.length) return;
  const invalidos = lista.filter((f) => !extensionValida(f.name));
  if (invalidos.length) {
    error.value = `Formato no admitido: ${invalidos.map((f) => f.name).join(", ")} (usa png/jpg/jpeg/svg/webp/gif).`;
    return;
  }
  subiendo.value = true;
  error.value = "";
  try {
    for (const file of lista) {
      await _subirImagen(props.slug, props.nombre, file);
    }
    await cargar();
    emit("cambiado");
  } catch (e) {
    error.value = e.message;
  } finally {
    subiendo.value = false;
  }
}

function onInputFile(ev) {
  subirArchivos(ev.target.files);
  ev.target.value = "";
}

function onDrop(ev) {
  arrastrando.value = false;
  subirArchivos(ev.dataTransfer?.files);
}

async function onRenombrar(nodo) {
  const nombreNuevo = window.prompt(`Nuevo nombre para "${nodo.nombre}":`, nodo.nombre);
  if (!nombreNuevo || nombreNuevo === nodo.nombre) return;
  if (!extensionValida(nombreNuevo)) {
    error.value = `Formato no admitido: '${nombreNuevo}' (usa png/jpg/jpeg/svg/webp/gif).`;
    return;
  }
  error.value = "";
  try {
    await _renombrarArchivo(props.slug, props.nombre, nodo.ruta, nombreNuevo);
    await cargar();
    emit("cambiado");
  } catch (e) {
    error.value = e.message;
  }
}

async function onEliminar(nodo) {
  if (!window.confirm(`¿Eliminar '${nodo.ruta}'? Esto no se puede deshacer.`)) return;
  error.value = "";
  try {
    await _eliminarArchivo(props.slug, props.nombre, nodo.ruta);
    await cargar();
    emit("cambiado");
  } catch (e) {
    error.value = e.message;
  }
}
</script>

<template>
  <div
    class="sidebar-archivos"
    :class="{ arrastrando }"
    @dragover.prevent="arrastrando = true"
    @dragleave.prevent="arrastrando = false"
    @drop.prevent="onDrop"
  >
    <div class="sidebar-archivos-header">
      <strong>Archivos</strong>
      <label class="sidebar-archivos-subir" :title="`Subir imagen a ${CARPETA}/`">
        {{ subiendo ? "…" : "+" }}
        <input type="file" accept="image/png,image/jpeg,image/svg+xml,image/webp,image/gif" multiple :disabled="subiendo" @change="onInputFile" hidden />
      </label>
    </div>
    <div v-if="error" class="error-banner">{{ error }}</div>
    <div v-if="cargando" class="empty-state">Cargando…</div>
    <div v-else-if="!arbol.length" class="empty-state">Sin archivos.</div>
    <div v-else class="sidebar-archivos-arbol">
      <FileTreeNode
        v-for="nodo in arbol"
        :key="nodo.ruta"
        :node="nodo"
        :on-renombrar="onRenombrar"
        :on-eliminar="onEliminar"
      />
    </div>
    <p class="sidebar-archivos-ayuda">
      Arrastra una imagen acá para subirla a <code>{{ CARPETA }}/</code>. Solo lectura para el resto.
    </p>
  </div>
</template>

<style>
.sidebar-archivos {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-right: 1px solid var(--border);
  background: var(--bg-panel);
}

.sidebar-archivos.arrastrando {
  outline: 2px dashed var(--accent);
  outline-offset: -2px;
}

.sidebar-archivos-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5em 0.7em;
  border-bottom: 1px solid var(--border);
}

.sidebar-archivos-subir {
  cursor: pointer;
  font-weight: 600;
  line-height: 1;
  padding: 0.15em 0.55em;
  border-radius: 6px;
  background: var(--accent);
  color: #fff;
}

.sidebar-archivos-arbol {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding: 0.3em 0;
}

.sidebar-archivos-ayuda {
  font-size: 0.72em;
  color: var(--text-dim);
  padding: 0.5em 0.7em;
  border-top: 1px solid var(--border);
  margin: 0;
}

.sidebar-archivos-ayuda code {
  font-family: var(--mono);
}
</style>
