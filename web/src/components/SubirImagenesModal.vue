<script setup>
import { ref, computed, onMounted } from "vue";
import {
  getArchivosPlantilla, subirImagenPlantilla, eliminarArchivoPlantilla,
  getArchivosDoc, subirImagenDoc, eliminarArchivoDoc,
} from "../api.js";

const props = defineProps({
  // "plantilla" -> Images/ (assets de la plantilla); "doc" -> img/ (imágenes propias del
  // documento, §4 CLAUDE.md). `nombre` es el nombre de la plantilla o el código del documento.
  tipo: { type: String, default: "plantilla" }, // "plantilla" | "doc"
  slug: { type: String, required: true },
  nombre: { type: String, required: true },
});

const emit = defineEmits(["cerrar", "cambiado"]);

const CARPETA = props.tipo === "doc" ? "img/" : "Images/";
const _getArchivos = props.tipo === "doc" ? getArchivosDoc : getArchivosPlantilla;
const _subirImagen = props.tipo === "doc" ? subirImagenDoc : subirImagenPlantilla;
const _eliminarArchivo = props.tipo === "doc" ? eliminarArchivoDoc : eliminarArchivoPlantilla;
const _titulo = props.tipo === "doc" ? "Imágenes del documento" : "Imágenes de la plantilla";

const archivos = ref([]); // rutas relativas dentro de la plantilla/documento, p. ej. "Images/logo.png" o "img/foto.png"
const cargando = ref(true);
const subiendo = ref(false);
const error = ref("");
const arrastrando = ref(false);

// Solo la carpeta de imágenes propia (Images/ o img/), y solo lo que #image() de Typst puede
// abrir -- mismo criterio que la validación del backend, acá para no ofrecer subir algo que el
// servidor va a rechazar de todas formas.
const EXTENSIONES_IMAGEN = new Set([".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif"]);

const imagenes = computed(() => archivos.value.filter((r) => r.startsWith(CARPETA)));

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

function urlImagen(ruta) {
  const recurso = props.tipo === "doc" ? "documentos" : "plantillas";
  return `/api/orgs/${encodeURIComponent(props.slug)}/${recurso}/${encodeURIComponent(props.nombre)}/archivo/${ruta.split("/").map(encodeURIComponent).join("/")}`;
}

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
  ev.target.value = ""; // permite volver a elegir el mismo archivo dos veces seguidas
}

function onDrop(ev) {
  arrastrando.value = false;
  subirArchivos(ev.dataTransfer?.files);
}

async function eliminar(ruta) {
  if (!window.confirm(`¿Eliminar '${ruta}'? Esto no se puede deshacer.`)) return;
  error.value = "";
  try {
    await _eliminarArchivo(props.slug, props.nombre, ruta);
    archivos.value = archivos.value.filter((r) => r !== ruta);
    emit("cambiado");
  } catch (e) {
    error.value = e.message;
  }
}

async function copiarReferencia(ruta) {
  const codigo = `#image("${ruta}")`;
  try {
    await navigator.clipboard.writeText(codigo);
  } catch {
    window.prompt("Copia el código para usar la imagen:", codigo);
  }
}
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('cerrar')">
    <div class="modal-box">
      <h2>{{ _titulo }}</h2>
      <div v-if="error" class="error-banner">{{ error }}</div>

      <div
        class="zona-subida"
        :class="{ arrastrando }"
        @dragover.prevent="arrastrando = true"
        @dragleave.prevent="arrastrando = false"
        @drop.prevent="onDrop"
      >
        <p>Arrastra imágenes acá, o</p>
        <label class="boton-elegir-archivo">
          {{ subiendo ? "Subiendo…" : "Elegir archivos…" }}
          <input type="file" accept="image/png,image/jpeg,image/svg+xml,image/webp,image/gif" multiple :disabled="subiendo" @change="onInputFile" hidden />
        </label>
        <p class="ayuda">png, jpg, jpeg, svg, webp, gif — se guardan en {{ CARPETA }} {{ tipo === "doc" ? "del documento" : "de la plantilla" }}.</p>
      </div>

      <div v-if="cargando" class="empty-state">Cargando…</div>
      <div v-else-if="!imagenes.length" class="empty-state">Sin imágenes todavía.</div>
      <ul v-else class="lista-imagenes">
        <li v-for="ruta in imagenes" :key="ruta" class="item-imagen">
          <img :src="urlImagen(ruta)" :alt="ruta" />
          <span class="nombre-imagen" :title="ruta">{{ ruta }}</span>
          <div class="acciones-imagen">
            <button type="button" title="Copiar código #image(...)" @click="copiarReferencia(ruta)">Copiar código</button>
            <button type="button" class="danger" title="Eliminar" @click="eliminar(ruta)">Eliminar</button>
          </div>
        </li>
      </ul>

      <div class="modal-acciones">
        <button class="primary" @click="emit('cerrar')">Cerrar</button>
      </div>
    </div>
  </div>
</template>

<style>
.zona-subida {
  border: 2px dashed var(--border);
  border-radius: 8px;
  padding: 1.2em;
  text-align: center;
  margin: 0.8em 0;
}
.zona-subida.arrastrando {
  border-color: var(--accent);
  background: var(--bg);
}
.zona-subida p {
  margin: 0.3em 0;
}
.zona-subida .ayuda {
  font-size: 0.8em;
  color: var(--text-dim);
}
.boton-elegir-archivo {
  display: inline-block;
  cursor: pointer;
  padding: 0.4em 0.9em;
  border-radius: 6px;
  background: var(--accent);
  color: #fff;
}

.lista-imagenes {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(9em, 1fr));
  gap: 0.8em;
  max-height: 24em;
  overflow-y: auto;
}
.item-imagen {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.5em;
  display: flex;
  flex-direction: column;
  gap: 0.3em;
}
.item-imagen img {
  width: 100%;
  height: 6em;
  object-fit: contain;
  background: repeating-conic-gradient(#0000 0% 25%, #0000000a 0% 50%) 0 0 / 12px 12px;
}
.nombre-imagen {
  font-size: 0.75em;
  color: var(--text-dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.acciones-imagen {
  display: flex;
  gap: 0.3em;
}
.acciones-imagen button {
  flex: 1;
  font-size: 0.75em;
  padding: 0.25em 0.4em;
}
.acciones-imagen button.danger {
  color: var(--danger, #c0392b);
}
</style>
