<script setup>
import { ref } from "vue";
import { urlMiniatura } from "../api.js";

const props = defineProps({
  slug: { type: String, required: true },
  docs: { type: Array, required: true },
  cargando: { type: Boolean, default: false },
});

const emit = defineEmits(["seleccionar", "nuevo"]);

const sinMiniatura = ref(new Set());

function onImgError(codigo) {
  sinMiniatura.value = new Set(sinMiniatura.value).add(codigo);
}
</script>

<template>
  <div class="vista-grid">
    <div class="grid-header">
      <button class="primary" @click="emit('nuevo')">+ Nuevo documento</button>
    </div>
    <div v-if="cargando" class="empty-state">Cargando documentos…</div>
    <div v-else-if="!docs.length" class="empty-state">Sin documentos en esta organización.</div>
    <div v-else class="grid-documentos">
      <div
        v-for="doc in docs"
        :key="doc.codigo_base"
        class="tarjeta-doc"
        @click="emit('seleccionar', doc.codigo_base)"
      >
        <div class="tarjeta-miniatura">
          <img
            v-if="!sinMiniatura.has(doc.codigo_base)"
            :src="urlMiniatura(slug, doc.codigo_base)"
            :alt="doc.titulo"
            @error="onImgError(doc.codigo_base)"
          />
          <div v-else class="tarjeta-placeholder">Sin compilar aún</div>
        </div>
        <div class="tarjeta-info">
          <div class="codigo">{{ doc.codigo_base }}</div>
          <div class="titulo">{{ doc.titulo }}</div>
        </div>
      </div>
    </div>
  </div>
</template>
