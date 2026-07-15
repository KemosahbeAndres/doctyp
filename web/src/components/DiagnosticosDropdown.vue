<script setup>
import { ref, onUnmounted } from "vue";

const props = defineProps({
  lista: { type: Array, required: true }, // [{linea, columna, severidad, severidadTexto, mensaje}]
  resumenTexto: { type: String, required: true },
  tieneErrores: { type: Boolean, default: false },
});

const emit = defineEmits(["seleccionar"]);

const abierto = ref(false);
const botonRef = ref(null);
// Teleport a <body> + posición fija calculada del botón: la barra de estado vive dentro de
// .panel-editor/.panel, que tienen overflow-y: auto (necesario para el resto del layout) -- un
// <div> absolute anidado ahí queda recortado por ese overflow en vez de flotar "por encima de
// todo", que es justo lo pedido. Con position:fixed + teleport el menú no depende del overflow
// de ningún ancestro.
const posicion = ref({ top: 0, left: 0 });

function calcularPosicion() {
  const r = botonRef.value?.getBoundingClientRect();
  if (!r) return;
  // El botón vive en la barra de estado, al fondo del panel -- el menú se abre HACIA ARRIBA
  // (bottom del menú = top del botón), igual que el comportamiento original.
  posicion.value = { bottom: window.innerHeight - r.top + 4, left: r.left };
}

function alternar() {
  if (!props.lista.length) return;
  if (!abierto.value) calcularPosicion();
  abierto.value = !abierto.value;
}

function cerrar() {
  abierto.value = false;
}

function elegir(d) {
  cerrar();
  emit("seleccionar", d);
}

// Cierra ante cualquier scroll/resize (la posición calculada quedaría obsoleta) y ante un clic
// fuera del menú -- captura en fase de captura para adelantarse a otros handlers de clic.
function onScrollOResize() {
  if (abierto.value) cerrar();
}
function onClickFuera(ev) {
  if (!abierto.value) return;
  if (botonRef.value?.contains(ev.target)) return;
  cerrar();
}

window.addEventListener("scroll", onScrollOResize, { capture: true, passive: true });
window.addEventListener("resize", onScrollOResize, { passive: true });
window.addEventListener("click", onClickFuera, { capture: true });

onUnmounted(() => {
  window.removeEventListener("scroll", onScrollOResize, { capture: true });
  window.removeEventListener("resize", onScrollOResize);
  window.removeEventListener("click", onClickFuera, { capture: true });
});
</script>

<template>
  <div class="diagnosticos-dropdown">
    <button
      ref="botonRef"
      type="button"
      class="estado diagnosticos-boton"
      :disabled="!lista.length"
      :style="{ color: tieneErrores ? 'var(--danger)' : undefined }"
      @click="alternar"
    >{{ resumenTexto }}</button>
    <Teleport to="body">
      <div
        v-if="abierto"
        class="diagnosticos-menu"
        :style="{ bottom: posicion.bottom + 'px', left: posicion.left + 'px' }"
      >
        <button
          v-for="(d, i) in lista"
          :key="i"
          type="button"
          class="diagnostico-item"
          :class="{ 'diagnostico-error': d.severidad === 1 }"
          @click="elegir(d)"
        >
          <span class="diagnostico-pos">{{ d.linea }}:{{ d.columna }}</span>
          <span class="diagnostico-sev">{{ d.severidadTexto }}</span>
          <span class="diagnostico-msg">{{ d.mensaje }}</span>
        </button>
      </div>
    </Teleport>
  </div>
</template>

<style>
.diagnosticos-dropdown { position: relative; }
.diagnosticos-boton {
  background: none;
  border: none;
  cursor: pointer;
  font: inherit;
  padding: 0;
}
.diagnosticos-boton:disabled { cursor: default; }
.diagnosticos-menu {
  position: fixed;
  background: var(--bg, #fff);
  border: 1px solid var(--gris-borde, #ccc);
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  max-height: 16em;
  overflow-y: auto;
  z-index: 1000;
  min-width: 22em;
  max-width: min(32em, calc(100vw - 2em));
}
.diagnostico-item {
  display: flex;
  gap: 0.5em;
  width: 100%;
  text-align: left;
  padding: 0.35em 0.6em;
  background: none;
  border: none;
  border-bottom: 1px solid var(--gris-borde, #eee);
  cursor: pointer;
  font-size: 0.85em;
}
.diagnostico-item:last-child { border-bottom: none; }
.diagnostico-item:hover { background: var(--fondo-cebra, rgba(0, 0, 0, 0.05)); }
.diagnostico-pos { opacity: 0.7; white-space: nowrap; }
.diagnostico-sev { white-space: nowrap; font-weight: 600; }
.diagnostico-error .diagnostico-sev { color: var(--danger, #c0392b); }
.diagnostico-msg { flex: 1; word-break: break-word; }
</style>
