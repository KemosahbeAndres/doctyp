import { createRouter, createWebHistory } from "vue-router";
import DocumentosGridView from "./views/DocumentosGridView.vue";
import DocumentoEditorView from "./views/DocumentoEditorView.vue";
import PlantillasGridView from "./views/PlantillasGridView.vue";
import PlantillaEditorView from "./views/PlantillaEditorView.vue";
import OrganizacionView from "./views/OrganizacionView.vue";
import LoginView from "./views/LoginView.vue";
import { useAuth } from "./composables/useAuth.js";

const routes = [
  { path: "/", redirect: "/documentos" },
  { path: "/login", name: "login", component: LoginView },
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

// Guard de sesión (Etapa 20): main.js espera a useAuth().iniciar() antes de montar la app y el
// router, así que `usuario` ya refleja el estado real de la cookie para cuando se evalúa la
// primera navegación -- no hace falta volver a pedir /api/auth/yo en cada cambio de ruta.
router.beforeEach((to) => {
  const { usuario } = useAuth();
  if (to.name !== "login" && !usuario.value) return { name: "login" };
  if (to.name === "login" && usuario.value) return { name: "documentos" };
  return true;
});
