import { createApp } from "vue";
import App from "./App.vue";
import "./style.css";
import { precargarWasm } from "./typst-wasm/client.js";

createApp(App).mount("#app");

// Calienta el compiler/renderer Typst-WASM en background, en tiempo ocioso, para que ya estén
// listos cuando el usuario abra el primer documento o plantilla (ver typst-wasm/client.js).
if ("requestIdleCallback" in window) {
  requestIdleCallback(() => precargarWasm());
} else {
  setTimeout(() => precargarWasm(), 300);
}
