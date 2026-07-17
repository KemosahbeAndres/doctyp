# doctyp — imagen del servicio único (Etapa 18, PLAN-V4.md §1/§2).
#
# python:3.12-slim + typst y tinymist como binarios (release oficiales, no paquetes de distro:
# más previsible entre versiones de Debian) + fuentes Liberation Sans (licencia SIL OFL,
# redistribución permitida -- ya versionadas en web/public/fonts/, CLAUDE.md Etapa 11).
# Museo Sans (licenciada, NO redistribuible) se monta por volumen en runtime, nunca se copia
# a la imagen -- ver docker-compose.yml (volumen `fonts`).
#
# Build de la SPA (Vue 3 + Vite) en una etapa `node` separada; la imagen final es solo Python
# + los binarios de compilación -- no necesita Node en runtime.

FROM node:20-slim AS frontend
WORKDIR /app/web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ ./
RUN npm run build

FROM python:3.12-slim AS runtime

ARG TYPST_VERSION=0.12.0
ARG TINYMIST_VERSION=0.15.2
ARG TARGETARCH

# curl + ca-certificates: solo para descargar los binarios de typst/tinymist en build time.
# xz-utils: el tarball de typst viene comprimido en .tar.xz.
RUN apt-get update -qq \
    && apt-get install -y --no-install-recommends curl ca-certificates xz-utils \
    && rm -rf /var/lib/apt/lists/*

# typst: binario oficial (sin paquete apt confiable en Debian slim). Mapea TARGETARCH (amd64/
# arm64, el que use `docker buildx`/podman según el host) al triple de Rust del release.
RUN set -eu; \
    case "${TARGETARCH:-amd64}" in \
        amd64) TYPST_TARGET="x86_64-unknown-linux-musl" ;; \
        arm64) TYPST_TARGET="aarch64-unknown-linux-musl" ;; \
        *) echo "arquitectura no soportada: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl --proto '=https' --tlsv1.2 -LsSf \
        "https://github.com/typst/typst/releases/download/v${TYPST_VERSION}/typst-${TYPST_TARGET}.tar.xz" \
        -o /tmp/typst.tar.xz; \
    tar -xJf /tmp/typst.tar.xz -C /tmp; \
    install -m 755 "/tmp/typst-${TYPST_TARGET}/typst" /usr/local/bin/typst; \
    rm -rf /tmp/typst.tar.xz "/tmp/typst-${TYPST_TARGET}"; \
    typst --version

# tinymist: mismo instalador oficial (cargo-dist) que usa `init` (ver ese script) -- detecta
# arquitectura solo. Degradación automática a typst.ts si esto llegara a fallar (doctyp_web.py
# ya maneja "tinymist no disponible" como caso normal, no fatal).
# ⚠ `VAR=val curl ... | sh` NO alcanza a `sh`: el prefijo de entorno solo aplica al primer
# comando de un pipeline, así que el instalador recibía TINYMIST_INSTALL_DIR vacío y caía a su
# default ($HOME/.local/bin, que en la imagen no está en el PATH). export + statement propio.
RUN export TINYMIST_INSTALL_DIR=/usr/local/bin TINYMIST_NO_MODIFY_PATH=1; \
    curl --proto '=https' --tlsv1.2 -LsSf \
        "https://github.com/Myriad-Dreamin/tinymist/releases/download/v${TINYMIST_VERSION}/tinymist-installer.sh" \
    | sh \
    && tinymist -V

WORKDIR /app

COPY doctyp.py doctyp_db.py doctyp_auth.py doctyp_web.py doctyp_preview_binary.py \
     doctyp_preview_server.py doctyp_lsp_server.py doctyp_ws_server.py doctyp_ws_client.py \
     lib.typ ./
COPY templates_base/ ./templates_base/
COPY --from=frontend /app/web/dist/ ./web/dist/

# organizations/ (config + plantillas de cada org) NO se copia a la imagen: vive enteramente en
# el volumen `data` (DOCTYP_ORGS_DIR más abajo) para que un rebuild nunca pise plantillas ya
# creadas por el usuario. docker-compose.yml monta el volumen vacío la primera vez; `doctyp org
# new`/`template add` lo van poblando en runtime, igual que hoy fuera de Docker.
#
# Volúmenes (docker-compose.yml los define; aquí solo se documentan los mountpoints):
#   /data/organizations   -> organizations/ (config + plantillas) via DOCTYP_ORGS_DIR
#   /data/doctyp.db        -> doctyp.db (WAL) via DOCTYP_DB_PATH
#   /data/settings.json    -> config local (org/autor activos) via DOCTYP_SETTINGS_PATH --
#                             sin esto se perdería en cada restart aunque doctyp.db no se toque
#   /data/docs             -> DOCS_ROOT (documentos) via DOCTYP_DOCS_ROOT
#   /data/fonts            -> Museo Sans (licenciada, montada por el host, nunca en la imagen)
ENV DOCTYP_ORGS_DIR=/data/organizations \
    DOCTYP_DB_PATH=/data/doctyp.db \
    DOCTYP_SETTINGS_PATH=/data/settings.json \
    DOCTYP_DOCS_ROOT=/data/docs \
    DOCTYP_BIND=0.0.0.0 \
    PYTHONUNBUFFERED=1

EXPOSE 8787

CMD ["python3", "doctyp.py", "web", "--host", "0.0.0.0", "--port", "8787", "--no-browser", "--no-build"]
