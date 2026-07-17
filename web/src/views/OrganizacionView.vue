<script setup>
import { ref, watch, onMounted } from "vue";
import {
  listEquipos, crearEquipo, editarEquipo, eliminarEquipo,
} from "../api.js";
import NewOrgModal from "../components/NewOrgModal.vue";
import { useOrgContext } from "../composables/useOrgContext.js";
import { useAuth } from "../composables/useAuth.js";

const {
  orgs, orgSlug, cargarOrgs, cambiarOrgActiva, error,
} = useOrgContext();
const { usuario, actualizarPerfil, cambiarPassword } = useAuth();

const seccion = ref("perfil"); // "perfil" | "organizaciones" | "equipos"
const equipos = ref([]);
const equipoForm = ref(null); // null | { id?, idOriginal?, nombre }
const mostrarNuevaOrg = ref(false);

// ── Mi perfil ────────────────────────────────────────────────────────────
const perfilForm = ref({ nombre: "", cargo: "", correo: "" });
const perfilGuardando = ref(false);
const perfilMensaje = ref("");
const perfilError = ref("");

function cargarPerfilForm() {
  if (!usuario.value) return;
  perfilForm.value = {
    nombre: usuario.value.nombre || "", cargo: usuario.value.cargo || "",
    correo: usuario.value.correo || "",
  };
}
onMounted(cargarPerfilForm);
watch(usuario, cargarPerfilForm);

async function guardarPerfil() {
  perfilError.value = "";
  perfilMensaje.value = "";
  perfilGuardando.value = true;
  try {
    await actualizarPerfil(perfilForm.value);
    perfilMensaje.value = "Perfil actualizado.";
  } catch (e) {
    perfilError.value = e.message;
  } finally {
    perfilGuardando.value = false;
  }
}

const passwordActual = ref("");
const passwordNueva = ref("");
const passwordNueva2 = ref("");
const passwordGuardando = ref(false);
const passwordMensaje = ref("");
const passwordError = ref("");

async function guardarPassword() {
  passwordError.value = "";
  passwordMensaje.value = "";
  if (passwordNueva.value !== passwordNueva2.value) {
    passwordError.value = "Las contraseñas nuevas no coinciden.";
    return;
  }
  passwordGuardando.value = true;
  try {
    await cambiarPassword(passwordActual.value, passwordNueva.value);
    passwordMensaje.value = "Contraseña actualizada.";
    passwordActual.value = "";
    passwordNueva.value = "";
    passwordNueva2.value = "";
  } catch (e) {
    passwordError.value = e.message;
  } finally {
    passwordGuardando.value = false;
  }
}

// ── Organizaciones ──────────────────────────────────────────────────────
async function onOrgCreada(org) {
  mostrarNuevaOrg.value = false;
  await cargarOrgs();
  cambiarOrgActiva(org.slug);
}

// ── Equipos ──────────────────────────────────────────────────────────────
async function cargarEquipos() {
  if (!orgSlug.value) {
    equipos.value = [];
    return;
  }
  try {
    equipos.value = await listEquipos(orgSlug.value);
  } catch (e) {
    error.value = e.message;
  }
}

onMounted(cargarEquipos);
// En un refresh directo de /organizacion, orgSlug todavía es null al montar (cargarOrgs() de
// App.vue: onMounted resuelve después) -- sin este watch, equipos quedaba vacío para siempre.
watch(orgSlug, cargarEquipos);

function nuevoEquipo() {
  equipoForm.value = { nombre: "" };
}

function editarEquipoForm(e) {
  equipoForm.value = { idOriginal: e.id, nombre: e.nombre };
}

async function guardarEquipo() {
  error.value = "";
  try {
    const f = equipoForm.value;
    if (f.idOriginal) {
      await editarEquipo(orgSlug.value, f.idOriginal, { nombre: f.nombre });
    } else {
      await crearEquipo(orgSlug.value, { id: f.id, nombre: f.nombre });
    }
    equipoForm.value = null;
    await cargarEquipos();
  } catch (e) {
    error.value = e.message;
  }
}

async function borrarEquipo(e) {
  if (!window.confirm(`¿Eliminar el equipo "${e.nombre}"?`)) return;
  error.value = "";
  try {
    await eliminarEquipo(orgSlug.value, e.id);
    await cargarEquipos();
  } catch (err) {
    error.value = err.message;
  }
}
</script>

<template>
  <div class="panel-cuenta">
    <div class="cuenta-sidebar">
      <button :class="{ activo: seccion === 'perfil' }" @click="seccion = 'perfil'">Mi perfil</button>
      <button :class="{ activo: seccion === 'organizaciones' }" @click="seccion = 'organizaciones'">
        Organizaciones
      </button>
      <button :class="{ activo: seccion === 'equipos' }" @click="seccion = 'equipos'">Equipos</button>
    </div>

    <div class="cuenta-contenido">
      <div v-if="error" class="error-banner">{{ error }}</div>

      <section v-if="seccion === 'perfil'">
        <h2>Mi perfil</h2>
        <div v-if="perfilError" class="error-banner">{{ perfilError }}</div>
        <p v-if="perfilMensaje" class="login-subtitulo">{{ perfilMensaje }}</p>
        <div class="crud-form">
          <label>Nombre <input v-model="perfilForm.nombre" type="text" /></label>
          <label>Cargo <input v-model="perfilForm.cargo" type="text" /></label>
          <label>Correo <input v-model="perfilForm.correo" type="email" /></label>
          <label>Email de acceso <input :value="usuario?.email" type="email" readonly /></label>
          <div class="modal-acciones">
            <button class="primary" :disabled="perfilGuardando" @click="guardarPerfil">
              {{ perfilGuardando ? "Guardando…" : "Guardar" }}
            </button>
          </div>
        </div>

        <h3 class="cuenta-subtitulo">Cambiar contraseña</h3>
        <div v-if="passwordError" class="error-banner">{{ passwordError }}</div>
        <p v-if="passwordMensaje" class="login-subtitulo">{{ passwordMensaje }}</p>
        <div class="crud-form">
          <label>Contraseña actual <input v-model="passwordActual" type="password" /></label>
          <label>Contraseña nueva <input v-model="passwordNueva" type="password" /></label>
          <label>Confirmar contraseña nueva <input v-model="passwordNueva2" type="password" /></label>
          <div class="modal-acciones">
            <button class="primary" :disabled="passwordGuardando" @click="guardarPassword">
              {{ passwordGuardando ? "Guardando…" : "Cambiar contraseña" }}
            </button>
          </div>
        </div>
      </section>

      <section v-if="seccion === 'organizaciones'">
        <h2>Organizaciones</h2>
        <button class="primary" @click="mostrarNuevaOrg = true">+ Nueva organización</button>
        <table class="crud-table">
          <thead><tr><th></th><th>Nombre</th><th>Slug</th><th>Documentos</th><th></th></tr></thead>
          <tbody>
            <tr v-for="o in orgs" :key="o.slug">
              <td><span v-if="o.slug === orgSlug" class="badge-activo" title="Organización activa">●</span></td>
              <td>{{ o.nombre }}</td>
              <td>{{ o.slug }}</td>
              <td>{{ o.documentos }}</td>
              <td class="acciones">
                <button v-if="o.slug !== orgSlug" @click="cambiarOrgActiva(o.slug)">Usar</button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section v-if="seccion === 'equipos'">
        <h2>Equipos</h2>
        <button class="primary" @click="nuevoEquipo">+ Nuevo equipo</button>
        <table class="crud-table">
          <thead><tr><th>Id</th><th>Nombre</th><th></th></tr></thead>
          <tbody>
            <tr v-for="e in equipos" :key="e.id">
              <td>{{ e.id }}</td>
              <td>{{ e.nombre }}</td>
              <td class="acciones">
                <button @click="editarEquipoForm(e)">Editar</button>
                <button @click="borrarEquipo(e)">Eliminar</button>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="equipoForm" class="crud-form">
          <h3>{{ equipoForm.idOriginal ? "Editar equipo" : "Nuevo equipo" }}</h3>
          <label v-if="!equipoForm.idOriginal">Id <input v-model="equipoForm.id" type="text" placeholder="p. ej. ti" /></label>
          <label>Nombre <input v-model="equipoForm.nombre" type="text" /></label>
          <div class="modal-acciones">
            <button @click="equipoForm = null">Cancelar</button>
            <button class="primary" @click="guardarEquipo">Guardar</button>
          </div>
        </div>
      </section>
    </div>

    <NewOrgModal v-if="mostrarNuevaOrg" @creada="onOrgCreada" @cancelar="mostrarNuevaOrg = false" />
  </div>
</template>
