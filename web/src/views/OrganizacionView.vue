<script setup>
import { ref, watch, onMounted } from "vue";
import {
  crearAutor, editarAutor, eliminarAutor, invitarMiembro,
  listEquipos, crearEquipo, editarEquipo, eliminarEquipo,
} from "../api.js";
import NewOrgModal from "../components/NewOrgModal.vue";
import { useOrgContext } from "../composables/useOrgContext.js";

const {
  orgs, orgSlug, autores, cargarOrgs, cargarAutores, cargarDocs, cambiarOrgActiva, error,
} = useOrgContext();

const tab = ref("organizacion");
const equipos = ref([]);
const autorForm = ref(null); // null | { id?, nombre, cargo, correo, equipos: [] }
const invitarForm = ref(null); // null | { email, role }
const equipoForm = ref(null); // null | { id?, idOriginal?, nombre }
const mostrarNuevaOrg = ref(false);

function equipoNombre(id) {
  return equipos.value.find((e) => e.id === id)?.nombre || id;
}

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

// ── Organización ─────────────────────────────────────────────────────────
async function onOrgCreada(org) {
  mostrarNuevaOrg.value = false;
  await cargarOrgs();
  cambiarOrgActiva(org.slug);
}

// ── Autores ──────────────────────────────────────────────────────────────
function nuevoAutor() {
  autorForm.value = { nombre: "", cargo: "", correo: "", equipos: [] };
}

function editarAutorForm(a) {
  autorForm.value = { id: a.id, nombre: a.nombre, cargo: a.cargo, correo: a.correo, equipos: [...(a.equipos || [])] };
}

async function guardarAutor() {
  error.value = "";
  try {
    const f = autorForm.value;
    if (f.id) {
      await editarAutor(orgSlug.value, f.id, { nombre: f.nombre, cargo: f.cargo, correo: f.correo, equipos: f.equipos });
    } else {
      await crearAutor(orgSlug.value, f);
    }
    autorForm.value = null;
    await cargarAutores();
    await cargarDocs();
  } catch (e) {
    error.value = e.message;
  }
}

async function borrarAutor(a) {
  if (!window.confirm(`¿Eliminar al autor "${a.nombre}"?`)) return;
  error.value = "";
  try {
    await eliminarAutor(orgSlug.value, a.id);
    await cargarAutores();
    await cargarDocs();
  } catch (e) {
    error.value = e.message;
  }
}

// Invitar = agregar directo a un usuario que YA existe en el sistema (sin correo, sin paso de
// aceptación) -- distinto de "Nuevo autor", que crea metadata sin cuenta de login.
function abrirInvitar() {
  invitarForm.value = { email: "", role: "member" };
}

async function enviarInvitacion() {
  error.value = "";
  try {
    await invitarMiembro(orgSlug.value, invitarForm.value.email, invitarForm.value.role);
    invitarForm.value = null;
    await cargarAutores();
  } catch (e) {
    error.value = e.message;
  }
}

// ── Equipos ──────────────────────────────────────────────────────────────
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
    await cargarAutores();
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
    await cargarAutores();
  } catch (err) {
    error.value = err.message;
  }
}
</script>

<template>
  <div class="panel panel-organizacion">
    <h2>Gestionar organización</h2>
    <div v-if="error" class="error-banner">{{ error }}</div>
    <div class="tabs">
      <button :class="{ activo: tab === 'organizacion' }" @click="tab = 'organizacion'">Organización</button>
      <button :class="{ activo: tab === 'autores' }" @click="tab = 'autores'">Autores</button>
      <button :class="{ activo: tab === 'equipos' }" @click="tab = 'equipos'">Equipos</button>
    </div>

    <div v-if="tab === 'organizacion'" class="tab-panel">
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
    </div>

    <div v-if="tab === 'autores'" class="tab-panel">
      <button class="primary" @click="nuevoAutor">+ Nuevo autor</button>
      <button @click="abrirInvitar">Invitar usuario</button>
      <table class="crud-table">
        <thead>
          <tr><th></th><th>Nombre</th><th>Cargo</th><th>Correo</th><th>Equipos</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="a in autores" :key="a.id">
            <td><span v-if="a.activo" class="badge-activo" title="Eres tú">●</span></td>
            <td>{{ a.nombre }}</td>
            <td>{{ a.cargo }}</td>
            <td>{{ a.correo }}</td>
            <td>{{ (a.equipos || []).map(equipoNombre).join(", ") }}</td>
            <td class="acciones">
              <button @click="editarAutorForm(a)">Editar</button>
              <button @click="borrarAutor(a)">Eliminar</button>
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="invitarForm" class="crud-form">
        <h3>Invitar usuario</h3>
        <p class="login-subtitulo">
          Debe ser un correo de una cuenta que ya exista en doctyp — queda agregado de inmediato,
          sin correo de invitación.
        </p>
        <label>Correo <input v-model="invitarForm.email" type="email" placeholder="usuario@correo.cl" /></label>
        <label>
          Rol
          <select v-model="invitarForm.role">
            <option value="member">Miembro</option>
            <option value="admin">Administrador</option>
          </select>
        </label>
        <div class="modal-acciones">
          <button @click="invitarForm = null">Cancelar</button>
          <button class="primary" @click="enviarInvitacion">Invitar</button>
        </div>
      </div>

      <div v-if="autorForm" class="crud-form">
        <h3>{{ autorForm.id ? "Editar autor" : "Nuevo autor" }}</h3>
        <label>Nombre <input v-model="autorForm.nombre" type="text" /></label>
        <label>Cargo <input v-model="autorForm.cargo" type="text" /></label>
        <label>Correo <input v-model="autorForm.correo" type="email" /></label>
        <label>
          Equipos
          <select v-model="autorForm.equipos" multiple size="4">
            <option v-for="e in equipos" :key="e.id" :value="e.id">{{ e.nombre }}</option>
          </select>
        </label>
        <div class="modal-acciones">
          <button @click="autorForm = null">Cancelar</button>
          <button class="primary" @click="guardarAutor">Guardar</button>
        </div>
      </div>
    </div>

    <div v-if="tab === 'equipos'" class="tab-panel">
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
    </div>

    <NewOrgModal v-if="mostrarNuevaOrg" @creada="onOrgCreada" @cancelar="mostrarNuevaOrg = false" />
  </div>
</template>

<style>
.panel-organizacion {
  padding: 1.2em;
  max-width: 60em;
  margin: 0 auto;
  overflow-y: auto;
}
.panel-organizacion h2 {
  margin-top: 0;
}
</style>
