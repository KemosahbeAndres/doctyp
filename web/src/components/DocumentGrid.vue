<script setup>
import { ref } from "vue";
import { urlMiniatura, getArchivosDoc, getArchivoDoc, getTyp } from "../api.js";
import { prefetch } from "../typst-wasm/client.js";

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

// Al pasar el mouse sobre una tarjeta, compila el documento en background (WASM) y lo deja en
// cache: para cuando el usuario hace click y el editor monta la vista previa, ya está listo.
const prefetchedos = new Set();
async function onHoverDoc(codigo) {
  if (prefetchedos.has(codigo)) return;
  prefetchedos.add(codigo);
  try {
    const [texto, rutas] = await Promise.all([
      getTyp(props.slug, codigo),
      getArchivosDoc(props.slug, codigo),
    ]);
    const archivos = await Promise.all(
      rutas
        .filter((r) => !r.startsWith("fonts/"))
        .map(async (ruta) => ({ ruta, bytes: await getArchivoDoc(props.slug, codigo, ruta) })),
    );
    await prefetch(props.slug, codigo, texto, archivos);
  } catch {
    prefetchedos.delete(codigo); // permite reintentar en un hover posterior
  }
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
        @mouseenter="onHoverDoc(doc.codigo_base)"
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
