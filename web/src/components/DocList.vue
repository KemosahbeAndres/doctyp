<script setup>
defineProps({
  docs: { type: Array, required: true },
  seleccionado: { type: String, default: null },
  cargando: { type: Boolean, default: false },
});

const emit = defineEmits(["seleccionar"]);
</script>

<template>
  <div class="panel panel-docs">
    <div v-if="cargando" class="empty-state">Cargando documentos…</div>
    <div v-else-if="!docs.length" class="empty-state">Sin documentos en esta organización.</div>
    <div
      v-for="doc in docs"
      :key="doc.codigo_base"
      class="doc-item"
      :class="{ activo: doc.codigo_base === seleccionado }"
      @click="emit('seleccionar', doc.codigo_base)"
    >
      <div class="codigo">{{ doc.codigo_base }}</div>
      <div class="titulo">{{ doc.titulo }}</div>
    </div>
  </div>
</template>
