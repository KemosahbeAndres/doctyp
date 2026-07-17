<script setup>
import { ref, computed, watch, onUnmounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import NewOrgModal from "./components/NewOrgModal.vue";
import { useOrgContext } from "./composables/useOrgContext.js";
import { useAuth } from "./composables/useAuth.js";

const router = useRouter();
const route = useRoute();
const {
  orgs, orgSlug, autores, autorActivoId, error,
  cambiarOrgActiva, cambiarAutorActivo, cargarOrgs, iniciar, detener,
} = useOrgContext();
const { usuario, logout } = useAuth();

const mostrarNuevaOrg = ref(false);
const enSesion = computed(() => route.name !== "login" && !!usuario.value);

// Cambiar de organización activa deja atrás cualquier documento/plantilla que se estuviera
// editando (era de la org anterior) -- mismo criterio que el `vista.value = "grid"`
// incondicional que hacía el watch(orgSlug) original en App.vue.
function onCambioOrg(slug) {
  cambiarOrgActiva(slug);
  router.push("/documentos");
}

async function onOrgCreada(org) {
  mostrarNuevaOrg.value = false;
  await cargarOrgs();
  onCambioOrg(org.slug);
}

async function onLogout() {
  detener();
  await logout();
  router.push("/login");
}

// useOrgContext().iniciar() llama /api/orgs de inmediato -- solo tiene sentido pedirlo una vez
// que hay sesión (en /login no hay cookie todavía). enSesion pasa de false a true justo después
// del login exitoso (LoginView redirige, el guard dejó pasar la navegación).
watch(enSesion, (activa) => {
  if (activa) iniciar();
  else detener();
}, { immediate: true });
onUnmounted(detener);
</script>

<template>
  <div class="app-shell">
    <div v-if="enSesion" class="topbar">
      <h1>doctyp</h1>
      <div class="topbar-group">
        <select :value="orgSlug" @change="onCambioOrg($event.target.value)">
          <option v-for="o in orgs" :key="o.slug" :value="o.slug">
            {{ o.nombre }}{{ o.activa ? " (activa)" : "" }}
          </option>
        </select>
        <button title="Nueva organización" @click="mostrarNuevaOrg = true">+</button>
      </div>
      <select :value="autorActivoId" @change="cambiarAutorActivo($event.target.value)">
        <option v-for="a in autores" :key="a.id" :value="a.id">
          {{ a.nombre }}{{ a.activo ? " (yo)" : "" }}
        </option>
      </select>
      <router-link to="/documentos" title="Documentos">Documentos</router-link>
      <router-link to="/plantillas" title="Editor de plantillas">Plantillas</router-link>
      <router-link to="/organizacion" title="Gestionar organización">⚙ Organización</router-link>
      <span class="topbar-usuario" :title="usuario.email">{{ usuario.nombre }}</span>
      <button title="Cerrar sesión" @click="onLogout">Salir</button>
    </div>
    <div v-if="error" class="error-banner">{{ error }}</div>

    <router-view />

    <NewOrgModal v-if="mostrarNuevaOrg" @creada="onOrgCreada" @cancelar="mostrarNuevaOrg = false" />
  </div>
</template>
