import { computed } from "vue";
import { diagnosticosPorUri } from "./lspDiagnosticsBus.js";

// Severidad LSP: 1=Error, 2=Warning, 3=Information, 4=Hint.
const ETIQUETA_SEVERIDAD = { 1: "Error", 2: "Aviso", 3: "Info", 4: "Sugerencia" };

/** Reusado por StatusBar.vue (documentos) y TemplateEditor.vue (plantillas): deriva del bus de
 * diagnósticos LSP (uno por URI, ver lspDiagnosticsBus.js) la lista vigente para el archivo
 * (tipo, slug, codigo) que le interesa a cada editor, ordenada por línea para el desplegable. */
export function useDiagnosticos(tipo, slug, codigo) {
  const entrada = computed(() => {
    for (const v of diagnosticosPorUri.value.values()) {
      if (v.tipo === tipo.value && v.slug === slug.value && v.codigo === codigo.value) return v;
    }
    return null;
  });

  const lista = computed(() => {
    const diags = entrada.value?.diagnosticos || [];
    return diags
      .map((d) => ({
        linea: (d.range?.start?.line ?? 0) + 1,
        columna: (d.range?.start?.character ?? 0) + 1,
        severidad: d.severity ?? 1,
        severidadTexto: ETIQUETA_SEVERIDAD[d.severity ?? 1] || "Error",
        mensaje: d.message || "",
      }))
      .sort((a, b) => a.linea - b.linea || a.columna - b.columna);
  });

  const errores = computed(() => lista.value.filter((d) => d.severidad === 1).length);
  const avisos = computed(() => lista.value.filter((d) => d.severidad === 2).length);

  const resumenTexto = computed(() => {
    if (!errores.value && !avisos.value) return "";
    const partes = [];
    if (errores.value) partes.push(`${errores.value} error${errores.value === 1 ? "" : "es"}`);
    if (avisos.value) partes.push(`${avisos.value} aviso${avisos.value === 1 ? "" : "s"}`);
    return partes.join(", ");
  });

  return { lista, errores, avisos, resumenTexto };
}
