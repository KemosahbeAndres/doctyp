import { createRouter, createWebHistory } from "vue-router";
import DocumentosGridView from "./views/DocumentosGridView.vue";
import DocumentoEditorView from "./views/DocumentoEditorView.vue";
import PlantillasGridView from "./views/PlantillasGridView.vue";
import PlantillaEditorView from "./views/PlantillaEditorView.vue";
import OrganizacionView from "./views/OrganizacionView.vue";

const routes = [
  { path: "/", redirect: "/documentos" },
  { path: "/documentos", name: "documentos", component: DocumentosGridView },
  { path: "/documentos/:codigo", name: "documento", component: DocumentoEditorView, props: true },
  { path: "/plantillas", name: "plantillas", component: PlantillasGridView },
  { path: "/plantillas/:nombre", name: "plantilla", component: PlantillaEditorView, props: true },
  { path: "/organizacion", name: "organizacion", component: OrganizacionView },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});
