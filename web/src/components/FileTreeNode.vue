<script setup>
import { ref } from "vue";

// Nodo recursivo del árbol de archivos (FileTreeSidebar.vue) -- solo lectura salvo para
// archivos marcados `mutable` (imágenes dentro de img/ o Images/, ver §4 CLAUDE.md), donde se
// ofrecen Renombrar/Eliminar. `onRenombrar`/`onEliminar` se pasan como funciones (no eventos)
// para no tener que reemitirlas en cada nivel de la recursión.
const props = defineProps({
  node: { type: Object, required: true }, // { nombre, ruta, tipo: "dir"|"file", mutable, hijos }
  depth: { type: Number, default: 0 },
  onRenombrar: { type: Function, required: true },
  onEliminar: { type: Function, required: true },
});

const abierto = ref(true);

const EXTENSIONES_IMAGEN = new Set([".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif"]);

function icono(nodo) {
  if (nodo.tipo === "dir") return "📁";
  const i = nodo.nombre.lastIndexOf(".");
  const ext = i >= 0 ? nodo.nombre.slice(i).toLowerCase() : "";
  if (EXTENSIONES_IMAGEN.has(ext)) return "🖼";
  if (ext === ".typ") return "📄";
  return "📄";
}
</script>

<template>
  <div class="file-tree-node">
    <div
      class="file-tree-fila"
      :style="{ paddingLeft: `${0.5 + depth * 1.1}em` }"
      :class="{ 'file-tree-dir': node.tipo === 'dir' }"
      @click="node.tipo === 'dir' ? (abierto = !abierto) : null"
    >
      <span v-if="node.tipo === 'dir'" class="file-tree-caret">{{ abierto ? "▾" : "▸" }}</span>
      <span class="file-tree-icono">{{ icono(node) }}</span>
      <span class="file-tree-nombre" :title="node.ruta">{{ node.nombre }}</span>
      <span v-if="node.mutable" class="file-tree-acciones">
        <button type="button" title="Renombrar" @click.stop="onRenombrar(node)">✎</button>
        <button type="button" class="danger" title="Eliminar" @click.stop="onEliminar(node)">✕</button>
      </span>
    </div>
    <div v-if="node.tipo === 'dir' && abierto">
      <FileTreeNode
        v-for="hijo in node.hijos"
        :key="hijo.ruta"
        :node="hijo"
        :depth="depth + 1"
        :on-renombrar="onRenombrar"
        :on-eliminar="onEliminar"
      />
    </div>
  </div>
</template>

<style>
.file-tree-fila {
  display: flex;
  align-items: center;
  gap: 0.35em;
  padding-top: 0.25em;
  padding-bottom: 0.25em;
  padding-right: 0.4em;
  font-size: 0.85rem;
  white-space: nowrap;
  overflow: hidden;
}

.file-tree-dir {
  cursor: pointer;
}

.file-tree-dir:hover {
  background: var(--bg);
}

.file-tree-caret {
  width: 1em;
  flex-shrink: 0;
  color: var(--text-dim);
  font-size: 0.75em;
}

.file-tree-icono {
  flex-shrink: 0;
}

.file-tree-nombre {
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-tree-acciones {
  margin-left: auto;
  display: none;
  flex-shrink: 0;
  gap: 0.2em;
}

.file-tree-fila:hover .file-tree-acciones {
  display: flex;
}

.file-tree-acciones button {
  font-size: 0.75em;
  padding: 0.1em 0.35em;
  line-height: 1.4;
}

.file-tree-acciones button.danger {
  color: var(--danger, #c0392b);
}
</style>
