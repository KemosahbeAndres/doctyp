<script setup>
import { ref, computed, onMounted } from "vue";
import {
  listAutores, crearAutor, editarAutor, eliminarAutor, activarAutor,
  listEquipos, crearEquipo, editarEquipo, eliminarEquipo,
  listPlantillas, fijarPlantillaDefault,
} from "../api.js";

const props = defineProps({
  slug: { type: String, required: true },
});

const emit = defineEmits(["cerrar", "cambio"]);

const tab = ref("autores");
const autores = ref([]);
const equipos = ref([]);
const plantillas = ref([]);
const error = ref("");
const autorForm = ref(null); // null | { id?, nombre, cargo, correo, equipos: [] }
const equipoForm = ref(null); // null | { id?, idOriginal?, nombre }

function equipoNombre(id) {
  return equipos.value.find((e) => e.id === id)?.nombre || id;
}

async function cargarTodo() {
  error.value = "";
  try {
    [autores.value, equipos.value, plantillas.value] = await Promise.all([
      listAutores(props.slug),
      listEquipos(props.slug),
      listPlantillas(props.slug),
    ]);
  } catch (e) {
    error.value = e.message;
  }
}

onMounted(cargarTodo);

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
      await editarAutor(props.slug, f.id, { nombre: f.nombre, cargo: f.cargo, correo: f.correo, equipos: f.equipos });
    } else {
      await crearAutor(props.slug, f);
    }
    autorForm.value = null;
    await cargarTodo();
    emit("cambio");
  } catch (e) {
    error.value = e.message;
  }
}

async function borrarAutor(a) {
  if (!window.confirm(`¿Eliminar al autor "${a.nombre}"?`)) return;
  error.value = "";
  try {
    await eliminarAutor(props.slug, a.id);
    await cargarTodo();
    emit("cambio");
  } catch (e) {
    error.value = e.message;
  }
}

async function marcarAutorActivo(a) {
  error.value = "";
  try {
    await activarAutor(props.slug, a.id);
    await cargarTodo();
    emit("cambio");
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
      await editarEquipo(props.slug, f.idOriginal, { nombre: f.nombre });
    } else {
      await crearEquipo(props.slug, { id: f.id, nombre: f.nombre });
    }
    equipoForm.value = null;
    await cargarTodo();
    emit("cambio");
  } catch (e) {
    error.value = e.message;
  }
}

async function borrarEquipo(e) {
  if (!window.confirm(`¿Eliminar el equipo "${e.nombre}"?`)) return;
  error.value = "";
  try {
    await eliminarEquipo(props.slug, e.id);
    await cargarTodo();
    emit("cambio");
  } catch (err) {
    error.value = err.message;
  }
}

// ── Plantillas ───────────────────────────────────────────────────────────
async function marcarDefault(p) {
  error.value = "";
  try {
    await fijarPlantillaDefault(props.slug, p.nombre);
    await cargarTodo();
  } catch (e) {
    error.value = e.message;
  }
}
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('cerrar')">
    <div class="modal-box modal-box-grande">
      <div class="org-manager-header">
        <h2>Gestionar organización</h2>
        <button @click="emit('cerrar')">Cerrar</button>
      </div>
      <div v-if="error" class="error-banner">{{ error }}</div>
      <div class="tabs">
        <button :class="{ activo: tab === 'autores' }" @click="tab = 'autores'">Autores</button>
        <button :class="{ activo: tab === 'equipos' }" @click="tab = 'equipos'">Equipos</button>
        <button :class="{ activo: tab === 'plantillas' }" @click="tab = 'plantillas'">Plantillas</button>
      </div>

      <div v-if="tab === 'autores'" class="tab-panel">
        <button class="primary" @click="nuevoAutor">+ Nuevo autor</button>
        <table class="crud-table">
          <thead>
            <tr><th></th><th>Nombre</th><th>Cargo</th><th>Correo</th><th>Equipos</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="a in autores" :key="a.id">
              <td><span v-if="a.activo" class="badge-activo" title="Autor activo">●</span></td>
              <td>{{ a.nombre }}</td>
              <td>{{ a.cargo }}</td>
              <td>{{ a.correo }}</td>
              <td>{{ (a.equipos || []).map(equipoNombre).join(", ") }}</td>
              <td class="acciones">
                <button v-if="!a.activo" @click="marcarAutorActivo(a)">Activar</button>
                <button @click="editarAutorForm(a)">Editar</button>
                <button @click="borrarAutor(a)">Eliminar</button>
              </td>
            </tr>
          </tbody>
        </table>

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

      <div v-if="tab === 'plantillas'" class="tab-panel">
        <table class="crud-table">
          <thead><tr><th></th><th>Nombre</th><th></th></tr></thead>
          <tbody>
            <tr v-for="p in plantillas" :key="p.nombre">
              <td><span v-if="p.default" class="badge-activo" title="Plantilla por defecto">●</span></td>
              <td>{{ p.nombre }}</td>
              <td class="acciones">
                <button :disabled="p.default" @click="marcarDefault(p)">Fijar como default</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p class="estado">Importar plantillas nuevas sigue siendo solo por CLI (`doctyp template add`).</p>
      </div>
    </div>
  </div>
</template>
