<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useAuth } from "../composables/useAuth.js";

const router = useRouter();
const { bootstrapInfo, crearPrimerUsuario, fijarPasswordInicial, login } = useAuth();

const email = ref("");
const nombre = ref("");
const password = ref("");
const password2 = ref("");
const enviando = ref(false);
const error = ref("");

// Tres pantallas posibles según el bootstrap (PLAN-V4.md §4):
//  - sin_usuarios: alta del primer usuario (queda como admin).
//  - usuario_unico_sin_password: fijar contraseña en el primer login, sin token de
//    invitación (no hay nadie más en el sistema que se la envíe).
//  - ninguno de los dos: login normal.
const modo = computed(() => {
  if (bootstrapInfo.value?.sin_usuarios) return "primer-usuario";
  if (bootstrapInfo.value?.usuario_unico_sin_password) return "fijar-password";
  return "login";
});

onMounted(() => {
  if (bootstrapInfo.value?.usuario_unico_sin_password) {
    email.value = bootstrapInfo.value.usuario_unico_sin_password.email;
  }
});

async function enviar() {
  error.value = "";
  if (modo.value !== "login" && password.value !== password2.value) {
    error.value = "Las contraseñas no coinciden.";
    return;
  }
  enviando.value = true;
  try {
    if (modo.value === "primer-usuario") {
      await crearPrimerUsuario(email.value, nombre.value, password.value);
    } else if (modo.value === "fijar-password") {
      await fijarPasswordInicial(bootstrapInfo.value.usuario_unico_sin_password.id, password.value);
      await login(email.value, password.value);
    } else {
      await login(email.value, password.value);
    }
    router.push("/documentos");
  } catch (e) {
    error.value = e.message;
  } finally {
    enviando.value = false;
  }
}
</script>

<template>
  <div class="pagina-login">
    <div class="modal-box">
      <h2>doctyp</h2>

      <p v-if="modo === 'primer-usuario'" class="login-subtitulo">
        Primer arranque: crea el primer usuario (quedará como administrador).
      </p>
      <p v-else-if="modo === 'fijar-password'" class="login-subtitulo">
        Bienvenido de nuevo. Este equipo aún no tiene contraseña configurada — créala para continuar.
      </p>

      <div v-if="error" class="error-banner">{{ error }}</div>

      <label>
        Email
        <input v-model="email" type="email" :readonly="modo === 'fijar-password'"
               placeholder="tu@correo.cl" @keyup.enter="enviar" autofocus />
      </label>

      <label v-if="modo === 'primer-usuario'">
        Nombre
        <input v-model="nombre" type="text" placeholder="Nombre completo" @keyup.enter="enviar" />
      </label>

      <label>
        {{ modo === "login" ? "Contraseña" : "Nueva contraseña" }}
        <input v-model="password" type="password" placeholder="••••••••" @keyup.enter="enviar" />
      </label>

      <label v-if="modo !== 'login'">
        Confirmar contraseña
        <input v-model="password2" type="password" placeholder="••••••••" @keyup.enter="enviar" />
      </label>

      <div class="modal-acciones">
        <button class="primary" :disabled="enviando" @click="enviar">
          {{ enviando ? "…" : (modo === "login" ? "Iniciar sesión" : "Continuar") }}
        </button>
      </div>
    </div>
  </div>
</template>
