import { onUnmounted } from "vue";

/**
 * Etapa 12.4: sincroniza el scroll de dos paneles (editor de código y vista previa) para que
 * bajen "a la par" -- misma posición relativa, misma velocidad -- sin importar cuál de los dos
 * dispara el scroll (rueda del mouse, barra de scroll, teclado). Sincroniza por proporción
 * (scrollTop / scrollHeight-clientHeight) en vez de píxeles 1:1 porque el editor (texto plano)
 * y la vista previa (documento paginado) casi nunca tienen la misma altura total; iguala la
 * fracción recorrida, que es la única forma de que ambos lleguen al final juntos.
 *
 * @param {() => HTMLElement | null} getScrollerA
 * @param {() => HTMLElement | null} getScrollerB
 */
export function useScrollSync(getScrollerA, getScrollerB) {
  let origen = null; // evita que el eco del scroll sincronizado dispare otro ciclo

  function fraccion(el) {
    const rango = el.scrollHeight - el.clientHeight;
    return rango > 0 ? el.scrollTop / rango : 0;
  }

  function aplicarFraccion(el, frac) {
    const rango = el.scrollHeight - el.clientHeight;
    el.scrollTop = rango > 0 ? frac * rango : 0;
  }

  function sincronizar(desde, hacia) {
    return () => {
      if (origen && origen !== desde) return; // ya está sincronizando en la otra dirección
      const elDesde = desde === "a" ? getScrollerA() : getScrollerB();
      const elHacia = hacia === "a" ? getScrollerA() : getScrollerB();
      if (!elDesde || !elHacia) return;
      origen = desde;
      aplicarFraccion(elHacia, fraccion(elDesde));
      requestAnimationFrame(() => {
        origen = null;
      });
    };
  }

  const onScrollA = sincronizar("a", "b");
  const onScrollB = sincronizar("b", "a");

  let scrollerAActual = null;
  let scrollerBActual = null;

  function reconectar() {
    const nuevoA = getScrollerA();
    const nuevoB = getScrollerB();
    if (nuevoA !== scrollerAActual) {
      scrollerAActual?.removeEventListener("scroll", onScrollA);
      nuevoA?.addEventListener("scroll", onScrollA, { passive: true });
      scrollerAActual = nuevoA;
    }
    if (nuevoB !== scrollerBActual) {
      scrollerBActual?.removeEventListener("scroll", onScrollB);
      nuevoB?.addEventListener("scroll", onScrollB, { passive: true });
      scrollerBActual = nuevoB;
    }
  }

  onUnmounted(() => {
    scrollerAActual?.removeEventListener("scroll", onScrollA);
    scrollerBActual?.removeEventListener("scroll", onScrollB);
  });

  return { reconectar };
}
