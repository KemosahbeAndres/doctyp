<script setup>
import { ref, onMounted } from "vue";
import { crearDocumento, getTiposDocumento, listPlantillas } from "../api.js";

const props = defineProps({
  slug: { type: String, required: true },
});

const emit = defineEmits(["creado", "cancelar"]);

const titulo = ref("");
const tipo = ref("INF");
const categoria = ref("SFW");
const plantilla = ref("");
const tipos = ref({});
const categorias = ref([]);
const plantillas = ref([]);
const creando = ref(false);
const error = ref("");

onMounted(async () => {
  try {
    const [td, pl] = await Promise.all([getTiposDocumento(), listPlantillas(props.slug)]);
    tipos.value = td.tipos;
    categorias.value = td.categorias;
    plantillas.value = pl;
    const porDefecto = pl.find((p) => p.default);
    plantilla.value = porDefecto ? porDefecto.nombre : pl[0]?.nombre ?? "";
  } catch (e) {
    error.value = e.message;
  }
});

async function confirmar() {
  if (!titulo.value.trim()) {
    error.value = "El título es obligatorio.";
    return;
  }
  creando.value = true;
  error.value = "";
  try {
    const doc = await crearDocumento(props.slug, {
      titulo: titulo.value.trim(),
      tipo: tipo.value,
      categoria: categoria.value,
      plantilla: plantilla.value || undefined,
    });
    emit("creado", doc);
  } catch (e) {
    error.value = e.message;
  } finally {
    creando.value = false;
  }
}
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('cancelar')">
    <div class="modal-box">
      <h2>Nuevo documento</h2>
      <div v-if="error" class="error-banner">{{ error }}</div>
      <label>
        Título
        <input v-model="titulo" type="text" placeholder="Título del documento" @keyup.enter="confirmar" autofocus />
      </label>
      <label>
        Tipo
        <select v-model="tipo">
          <option v-for="(nombre, codigo) in tipos" :key="codigo" :value="codigo">{{ nombre }} ({{ codigo }})</option>
        </select>
      </label>
      <label>
        Categoría
        <select v-model="categoria">
          <option v-for="c in categorias" :key="c" :value="c">{{ c }}</option>
        </select>
      </label>
      <label v-if="plantillas.length > 1">
        Plantilla
        <select v-model="plantilla">
          <option v-for="p in plantillas" :key="p.nombre" :value="p.nombre">
            {{ p.nombre }}{{ p.default ? " (por defecto)" : "" }}
          </option>
        </select>
      </label>
      <div class="modal-acciones">
        <button @click="emit('cancelar')">Cancelar</button>
        <button class="primary" :disabled="creando" @click="confirmar">
          {{ creando ? "Creando…" : "Crear documento" }}
        </button>
      </div>
    </div>
  </div>
</template>
