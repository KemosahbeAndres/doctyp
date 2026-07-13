<script setup>
import { ref, computed, watch, onMounted } from "vue";
import {
  getPlantillaLibTyp, guardarPlantillaLibTyp, vistaPreviaPlantilla,
  getHistoriaPlantilla, getVersionContenidoPlantilla,
} from "../api.js";
import VistaPrevia from "./VistaPrevia.vue";

const props = defineProps({
  slug: { type: String, required: true },
  nombre: { type: String, required: true },
});

const emit = defineEmits(["cerrar", "guardado"]);

const texto = ref("");
const original = ref("");
const cargando = ref(false);
const ocupado = ref(false);
const mensaje = ref("");
const mensajeEsError = ref(false);
const versiones = ref([]);

const sucio = computed(() => texto.value !== original.value);
const palabras = computed(() => {
  const t = texto.value.trim();
  return t ? t.split(/\s+/).length : 0;
});
const tamanoKB = computed(() => (new Blob([texto.value]).size / 1024).toFixed(1));

async function cargar() {
  cargando.value = true;
  mensaje.value = "";
  try {
    const contenido = await getPlantillaLibTyp(props.slug, props.nombre);
    texto.value = contenido;
    original.value = contenido;
  } catch (e) {
    mensaje.value = `No se pudo cargar la plantilla: ${e.message}`;
    mensajeEsError.value = true;
  } finally {
    cargando.value = false;
  }
}

async function cargarHistoria() {
  try {
    versiones.value = await getHistoriaPlantilla(props.slug, props.nombre);
  } catch (e) {
    mensaje.value = e.message;
    mensajeEsError.value = true;
  }
}

onMounted(() => {
  cargar();
  cargarHistoria();
});

async function guardar() {
  const msg = window.prompt("Mensaje para la nueva versión (qué cambió en la plantilla):");
  if (!msg) return;
  ocupado.value = true;
  mensaje.value = "";
  try {
    const fila = await guardarPlantillaLibTyp(props.slug, props.nombre, texto.value, msg);
    original.value = texto.value;
    mensaje.value = `Versión guardada: v${fila.version}.`;
    mensajeEsError.value = false;
    await cargarHistoria();
    emit("guardado");
  } catch (e) {
    mensaje.value = `Error al guardar: ${e.message}`;
    mensajeEsError.value = true;
  } finally {
    ocupado.value = false;
  }
}

async function cargarVersionEnEditor(version) {
  try {
    texto.value = await getVersionContenidoPlantilla(props.slug, props.nombre, version);
    mensaje.value = `Versión v${version} cargada en el editor (sin guardar aún).`;
    mensajeEsError.value = false;
  } catch (e) {
    mensaje.value = e.message;
    mensajeEsError.value = true;
  }
}

function onCambioVersion(ev) {
  const version = ev.target.value;
  ev.target.value = "";
  if (version) cargarVersionEnEditor(version);
}

function cerrar() {
  if (sucio.value && !window.confirm("Tienes cambios sin guardar en la plantilla. ¿Cerrar igualmente?")) {
    return;
  }
  emit("cerrar");
}
</script>

<template>
  <div class="modal-backdrop" @click.self="cerrar">
    <div class="modal-box modal-box-editor">
      <div class="org-manager-header">
        <h2>Editar plantilla: {{ nombre }}</h2>
        <button @click="cerrar">Cerrar</button>
      </div>
      <div v-if="cargando" class="empty-state">Cargando…</div>
      <template v-else>
        <div v-if="mensaje" class="estado" :style="{ color: mensajeEsError ? 'var(--danger)' : undefined }">
          {{ mensaje }}
        </div>
        <div class="editor-preview-split template-editor-split">
          <textarea class="editor-textarea" v-model="texto" spellcheck="false"></textarea>
          <VistaPrevia
            :slug="slug"
            :codigo="nombre"
            :texto="texto"
            :compilar-fn="vistaPreviaPlantilla"
          />
        </div>
        <div class="status-bar">
          <div class="status-bar-fila">
            <span class="estado">{{ sucio ? "cambios sin guardar" : "sin cambios pendientes" }}</span>
            <select @change="onCambioVersion">
              <option value="">Ver / cargar versión anterior…</option>
              <option v-for="v in versiones" :key="v.version" :value="v.version" :disabled="!v.snapshot_disponible">
                v{{ v.version }} · {{ v.mensaje }}
              </option>
            </select>
            <span class="estado">{{ palabras }} palabras · {{ tamanoKB }} KB</span>
            <span class="status-bar-spacer"></span>
            <button class="primary" :disabled="ocupado" @click="guardar">Guardar plantilla</button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
