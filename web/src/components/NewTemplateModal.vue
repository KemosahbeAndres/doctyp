<script setup>
import { ref } from "vue";
import { crearPlantilla } from "../api.js";

const props = defineProps({
  slug: { type: String, required: true },
  plantillas: { type: Array, required: true },
});

const emit = defineEmits(["creada", "cancelar"]);

const nombre = ref("");
const clonarDe = ref(props.plantillas.find((p) => p.default)?.nombre || props.plantillas[0]?.nombre || "");
const creando = ref(false);
const error = ref("");

async function confirmar() {
  if (!/^[a-z0-9][a-z0-9-]*$/.test(nombre.value)) {
    error.value = "El nombre solo admite minúsculas, dígitos y guiones (p. ej. 'informe-ti-v2').";
    return;
  }
  creando.value = true;
  error.value = "";
  try {
    const plantilla = await crearPlantilla(props.slug, {
      nombre: nombre.value,
      clonar_de: clonarDe.value || undefined,
    });
    emit("creada", plantilla);
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
      <h2>Nueva plantilla</h2>
      <div v-if="error" class="error-banner">{{ error }}</div>
      <label>
        Nombre
        <input v-model="nombre" type="text" placeholder="informe-ti-v2" @keyup.enter="confirmar" autofocus />
      </label>
      <label>
        Clonar de
        <select v-model="clonarDe">
          <option value="">En blanco (esqueleto mínimo)</option>
          <option v-for="p in plantillas" :key="p.nombre" :value="p.nombre">
            {{ p.nombre }}{{ p.default ? " (por defecto)" : "" }}
          </option>
        </select>
      </label>
      <div class="modal-acciones">
        <button @click="emit('cancelar')">Cancelar</button>
        <button class="primary" :disabled="creando" @click="confirmar">
          {{ creando ? "Creando…" : "Crear plantilla" }}
        </button>
      </div>
    </div>
  </div>
</template>
