<script setup>
import { ref } from "vue";
import { invitarMiembro } from "../api.js";

const props = defineProps({ orgSlug: { type: String, required: true }, orgNombre: { type: String, default: "" } });
const emit = defineEmits(["invitado", "cancelar"]);

const email = ref("");
const role = ref("member");
const enviando = ref(false);
const error = ref("");

async function confirmar() {
  if (!email.value.trim()) {
    error.value = "El correo es obligatorio.";
    return;
  }
  enviando.value = true;
  error.value = "";
  try {
    await invitarMiembro(props.orgSlug, email.value.trim(), role.value);
    emit("invitado");
  } catch (e) {
    error.value = e.message;
  } finally {
    enviando.value = false;
  }
}
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('cancelar')">
    <div class="modal-box">
      <h2>Invitar usuario{{ orgNombre ? ` a ${orgNombre}` : "" }}</h2>
      <p class="login-subtitulo">
        Debe ser el correo de una cuenta que ya exista en doctyp — queda agregada de inmediato,
        sin correo de invitación.
      </p>
      <div v-if="error" class="error-banner">{{ error }}</div>
      <label>
        Correo
        <input v-model="email" type="email" placeholder="usuario@correo.cl" @keyup.enter="confirmar" autofocus />
      </label>
      <label>
        Rol
        <select v-model="role">
          <option value="member">Miembro</option>
          <option value="admin">Administrador</option>
        </select>
      </label>
      <div class="modal-acciones">
        <button @click="emit('cancelar')">Cancelar</button>
        <button class="primary" :disabled="enviando" @click="confirmar">
          {{ enviando ? "Invitando…" : "Invitar" }}
        </button>
      </div>
    </div>
  </div>
</template>
