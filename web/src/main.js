import { createApp } from "vue";
import App from "./App.vue";
import { router } from "./router.js";
import "./style.css";
import { precargarWasm } from "./typst-wasm/client.js";
import { useAuth } from "./composables/useAuth.js";

// La sesión se resuelve ANTES de montar la app: el guard de navegación (router.js) decide si
// la primera ruta pedida requiere login, y necesita saber ya si hay sesión o no (evita un
// parpadeo hacia /login en cada recarga de página mientras se resuelve /api/auth/yo).
useAuth().iniciar().finally(() => {
  createApp(App).use(router).mount("#app");
});

// Calienta el compiler/renderer Typst-WASM en background, en tiempo ocioso, para que ya estén
// listos cuando el usuario abra el primer documento o plantilla (ver typst-wasm/client.js).
if ("requestIdleCallback" in window) {
  requestIdleCallback(() => precargarWasm());
} else {
  setTimeout(() => precargarWasm(), 300);
}
