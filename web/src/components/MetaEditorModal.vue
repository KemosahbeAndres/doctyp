<script setup>
import { ref, onMounted } from "vue";
import { getMetaDoc, putMetaDoc, getTiposDocumento } from "../api.js";

const props = defineProps({
  slug: { type: String, required: true },
  codigo: { type: String, required: true },
});

const emit = defineEmits(["guardado", "cancelar"]);

const form = ref(null); // null mientras carga
const estados = ref([]);
const clasificaciones = ref([]);
const cargando = ref(true);
const guardando = ref(false);
const error = ref("");

onMounted(async () => {
  try {
    const [meta, tipos] = await Promise.all([
      getMetaDoc(props.slug, props.codigo),
      getTiposDocumento(),
    ]);
    form.value = { ...meta };
    estados.value = tipos.estados;
    clasificaciones.value = tipos.clasificaciones;
  } catch (e) {
    error.value = e.message;
  } finally {
    cargando.value = false;
  }
});

async function guardar() {
  if (!form.value.titulo.trim()) {
    error.value = "El título es obligatorio.";
    return;
  }
  guardando.value = true;
  error.value = "";
  try {
    const res = await putMetaDoc(props.slug, props.codigo, form.value);
    emit("guardado", res);
  } catch (e) {
    error.value = e.message;
  } finally {
    guardando.value = false;
  }
}
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('cancelar')">
    <div class="modal-box modal-box-grande">
      <div class="org-manager-header">
        <h2>Metadatos del documento</h2>
        <button @click="emit('cancelar')">Cerrar</button>
      </div>
      <div v-if="error" class="error-banner">{{ error }}</div>
      <div v-if="cargando" class="empty-state">Cargando…</div>
      <template v-else-if="form">
        <div class="crud-form">
          <h3>Portada</h3>
          <label>Título <input v-model="form.titulo" type="text" /></label>
          <label>Subtítulo <input v-model="form.subtitulo" type="text" /></label>
          <label>Rótulo de portada (tipo largo) <input v-model="form['tipo-largo']" type="text" /></label>
        </div>

        <div class="crud-form">
          <h3>Estado</h3>
          <label>
            Estado
            <select v-model="form.estado">
              <option v-for="e in estados" :key="e" :value="e">{{ e }}</option>
            </select>
          </label>
          <label>
            Clasificación
            <select v-model="form.clasificacion">
              <option v-for="c in clasificaciones" :key="c" :value="c">{{ c }}</option>
            </select>
          </label>
        </div>

        <div class="crud-form">
          <h3>Firmas</h3>
          <label>Autor <input v-model="form.autor" type="text" /></label>
          <label>Cargo del autor <input v-model="form['cargo-autor']" type="text" /></label>
          <label>Correo del autor <input v-model="form['correo-autor']" type="email" /></label>
          <label>Revisor <input v-model="form.revisor" type="text" /></label>
          <label>Cargo del revisor <input v-model="form['cargo-revisor']" type="text" /></label>
          <label>Aprobador <input v-model="form.aprobador" type="text" /></label>
          <label>Cargo del aprobador <input v-model="form['cargo-aprob']" type="text" /></label>
          <p class="estado">Revisor y aprobador: si se dejan vacíos, se usa el valor por defecto de la plantilla.</p>
        </div>

        <div class="modal-acciones">
          <button @click="emit('cancelar')">Cancelar</button>
          <button class="primary" :disabled="guardando" @click="guardar">
            {{ guardando ? "Guardando…" : "Guardar metadatos" }}
          </button>
        </div>
      </template>
    </div>
  </div>
</template>
