<script setup>
import { ref } from "vue";
import { urlMiniaturaPlantilla } from "../api.js";

const props = defineProps({
  slug: { type: String, required: true },
  plantillas: { type: Array, required: true },
  cargando: { type: Boolean, default: false },
});

const emit = defineEmits(["seleccionar", "nuevo", "default", "eliminar"]);

const sinMiniatura = ref(new Set());

function onImgError(nombre) {
  sinMiniatura.value = new Set(sinMiniatura.value).add(nombre);
}
</script>

<template>
  <div class="vista-grid">
    <div class="grid-header">
      <button class="primary" @click="emit('nuevo')">+ Nueva plantilla</button>
    </div>
    <div v-if="cargando" class="empty-state">Cargando plantillas…</div>
    <div v-else-if="!plantillas.length" class="empty-state">Sin plantillas en esta organización.</div>
    <div v-else class="grid-documentos">
      <div
        v-for="p in plantillas"
        :key="p.nombre"
        class="tarjeta-doc"
        @click="emit('seleccionar', p.nombre)"
      >
        <div class="tarjeta-miniatura">
          <img
            v-if="!sinMiniatura.has(p.nombre)"
            :src="urlMiniaturaPlantilla(slug, p.nombre)"
            :alt="p.nombre"
            @error="onImgError(p.nombre)"
          />
          <div v-else class="tarjeta-placeholder">Sin vista previa aún</div>
        </div>
        <div class="tarjeta-info">
          <div class="codigo">{{ p.nombre }}</div>
          <div class="titulo">{{ p.default ? "Plantilla por defecto" : "" }}</div>
        </div>
        <div class="tarjeta-acciones" @click.stop>
          <button :disabled="p.default" @click="emit('default', p)">Fijar default</button>
          <button :disabled="p.default" @click="emit('eliminar', p)">Eliminar</button>
        </div>
      </div>
    </div>
  </div>
</template>
