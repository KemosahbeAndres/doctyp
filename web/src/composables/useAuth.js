import { ref } from "vue";
import { authBootstrap, authCrearPrimerUsuario, authRegistrar, authFijarPasswordInicial, authLogin, authLogout, authYo } from "../api.js";

// Mismo patrón "bus" de módulo-singleton que useOrgContext.js/editorScrollToBus.js (el
// proyecto no usa store, ver nota Etapa 5 en CLAUDE.md) -- App.vue y el guard del router
// necesitan el mismo estado de sesión.
const usuario = ref(null);
const cargando = ref(true);
const bootstrapInfo = ref(null); // {sin_usuarios, usuario_unico_sin_password} mientras no hay sesión

/** Se llama una vez al arrancar la app: intenta recuperar la sesión (cookie ya presente si el
 * usuario recarga la página) y, si no hay, consulta el estado de bootstrap para decidir qué
 * pantalla mostrar (alta del primer usuario vs. login normal vs. "fija tu password"). */
async function iniciar() {
  cargando.value = true;
  try {
    const { usuario: u } = await authYo();
    usuario.value = u;
  } catch {
    usuario.value = null;
    try {
      bootstrapInfo.value = await authBootstrap();
    } catch {
      bootstrapInfo.value = null;
    }
  } finally {
    cargando.value = false;
  }
}

async function crearPrimerUsuario(email, nombre, password) {
  const { usuario: u } = await authCrearPrimerUsuario(email, nombre, password);
  usuario.value = u;
  bootstrapInfo.value = null;
}

async function registrar(email, nombre, password) {
  const { usuario: u } = await authRegistrar(email, nombre, password);
  usuario.value = u;
  bootstrapInfo.value = null;
}

async function fijarPasswordInicial(userId, password) {
  await authFijarPasswordInicial(userId, password);
  bootstrapInfo.value = null;
}

async function login(email, password) {
  const { usuario: u } = await authLogin(email, password);
  usuario.value = u;
}

async function logout() {
  await authLogout().catch(() => {});
  usuario.value = null;
  bootstrapInfo.value = await authBootstrap().catch(() => null);
}

export function useAuth() {
  return { usuario, cargando, bootstrapInfo, iniciar, crearPrimerUsuario, registrar, fijarPasswordInicial, login, logout };
}
