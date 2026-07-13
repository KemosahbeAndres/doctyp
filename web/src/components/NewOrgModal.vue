<script setup>
import { ref } from "vue";
import { crearOrg } from "../api.js";

const emit = defineEmits(["creada", "cancelar"]);

const slug = ref("");
const nombre = ref("");
const creando = ref(false);
const error = ref("");

async function confirmar() {
  if (!/^[a-z0-9][a-z0-9-]*$/.test(slug.value)) {
    error.value = "El slug solo admite minúsculas, dígitos y guiones (p. ej. 'mi-org').";
    return;
  }
  creando.value = true;
  error.value = "";
  try {
    const org = await crearOrg({ slug: slug.value, nombre: nombre.value || undefined });
    emit("creada", org);
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
      <h2>Nueva organización</h2>
      <div v-if="error" class="error-banner">{{ error }}</div>
      <label>
        Slug
        <input v-model="slug" type="text" placeholder="mi-organizacion" @keyup.enter="confirmar" autofocus />
      </label>
      <label>
        Nombre
        <input v-model="nombre" type="text" placeholder="Nombre completo (opcional)" @keyup.enter="confirmar" />
      </label>
      <div class="modal-acciones">
        <button @click="emit('cancelar')">Cancelar</button>
        <button class="primary" :disabled="creando" @click="confirmar">
          {{ creando ? "Creando…" : "Crear organización" }}
        </button>
      </div>
    </div>
  </div>
</template>
