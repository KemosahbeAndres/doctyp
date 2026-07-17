<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useAuth } from "../composables/useAuth.js";

const router = useRouter();
const { bootstrapInfo, crearPrimerUsuario, registrar, fijarPasswordInicial, login } = useAuth();

const email = ref("");
const nombre = ref("");
const password = ref("");
const password2 = ref("");
const enviando = ref(false);
const error = ref("");
const quiereRegistrarse = ref(false);

// Cuatro pantallas posibles:
//  - sin_usuarios: alta del primer usuario (queda como admin) -- bootstrap, PLAN-V4.md §4.
//  - usuario_unico_sin_password: fijar contraseña en el primer login, sin token de
//    invitación (no hay nadie más en el sistema que se la envíe).
//  - registro: alta libre de una cuenta nueva (con su propia organización personal) --
//    alternada a mano desde el login normal, no depende del bootstrap.
//  - ninguno de los anteriores: login normal.
const modo = computed(() => {
  if (bootstrapInfo.value?.sin_usuarios) return "primer-usuario";
  if (bootstrapInfo.value?.usuario_unico_sin_password) return "fijar-password";
  if (quiereRegistrarse.value) return "registro";
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
    } else if (modo.value === "registro") {
      await registrar(email.value, nombre.value, password.value);
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
      <p v-else-if="modo === 'registro'" class="login-subtitulo">
        Crea tu cuenta. Empiezas con tu propia organización personal — a la que solo tú tienes
        acceso, hasta que alguien te invite a otra.
      </p>

      <div v-if="error" class="error-banner">{{ error }}</div>

      <label>
        Email
        <input v-model="email" type="email" :readonly="modo === 'fijar-password'"
               placeholder="tu@correo.cl" @keyup.enter="enviar" autofocus />
      </label>

      <label v-if="modo === 'primer-usuario' || modo === 'registro'">
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

      <p v-if="modo === 'login'" class="login-alterno">
        ¿No tienes cuenta?
        <a href="#" @click.prevent="quiereRegistrarse = true; error = ''">Regístrate</a>
      </p>
      <p v-else-if="modo === 'registro'" class="login-alterno">
        ¿Ya tienes cuenta?
        <a href="#" @click.prevent="quiereRegistrarse = false; error = ''">Inicia sesión</a>
      </p>
    </div>
  </div>
</template>

<style>
.login-alterno {
  margin-top: 1em;
  text-align: center;
  font-size: 0.9em;
}
.login-alterno a {
  color: var(--accent);
  text-decoration: underline;
}
</style>
