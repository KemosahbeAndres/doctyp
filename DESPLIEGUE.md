# DESPLIEGUE.md — doctyp en producción (VPS + Docker + Traefik + CI/CD)

> Guía operativa para desplegar `doctyp` en el VPS y dejar el CI/CD funcionando
> (`.github/workflows/deploy.yml`). Complementa PLAN-V4.md §2 (topología Docker) —
> no repite las decisiones de arquitectura, solo los pasos para ejecutarlas.

---

## 0. Resumen del flujo

1. El repo vive en GitHub (`KemosahbeAndres/informes-uti-slep-chinchorro`).
2. En el VPS: se clona el repo una vez, se completan los archivos que **no** van al repo
   (fuentes con licencia, dominio real en `docker-compose.yml`), y se levanta con
   `docker compose up -d --build`.
3. **A partir de ahí, no vuelves a tocar el VPS a mano para desplegar cambios.** Cada
   `git push` a `master` dispara el workflow de GitHub Actions, que entra al VPS por SSH,
   hace `git pull` y reconstruye el contenedor.
4. El build de la imagen (typst, tinymist, la SPA) ocurre **dentro del VPS**, no en el
   runner de GitHub — no hay registry de imágenes de por medio, ver §5 si más adelante
   quieres cambiar eso.

---

## 1. Requisitos en el VPS (una sola vez)

```bash
# Docker + Compose plugin (Ubuntu/Debian; ajusta si tu VPS es otra distro)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"      # cierra sesión y vuelve a entrar para que aplique
```

Verifica:

```bash
docker --version
docker compose version
```

`docker-compose.yml` ya está configurado para conectarse a la red externa `proxy` — la
misma que ya usa tu Traefik en este VPS. **No hace falta crearla ni tocarla**: ya existe,
y `docker compose up` solo se conecta a ella por nombre (`external: true` en la sección
`networks:` del archivo le dice a Compose que no intente crearla ni gestionarla, solo
unirse). Si en algún momento tu Traefik cambia de red, ajusta el nombre `proxy` en
`docker-compose.yml` (sección `networks:`, tanto en el servicio como al final del archivo)
para que coincida.

---

## 2. Generar la clave SSH dedicada para CI/CD

**En tu máquina local** (no en el VPS), genera un par de claves exclusivo para que GitHub
Actions se conecte al VPS. Sin passphrase (el workflow no puede escribir una
interactivamente) y de uso único — no reutilices tu clave SSH personal.

```bash
ssh-keygen -t ed25519 -C "ci-deploy-doctyp" -f ~/.ssh/doctyp_deploy_key -N ""
```

Esto crea dos archivos:

- `~/.ssh/doctyp_deploy_key` — **privada**. Va a un secret de GitHub (§4), nunca al repo,
  nunca por email/chat. Si se filtra, revócala de inmediato (borra la línea correspondiente
  de `~/.ssh/authorized_keys` en el VPS y genera un par nuevo).
- `~/.ssh/doctyp_deploy_key.pub` — pública. Va al VPS (siguiente paso).

Copia la clave pública al VPS, a un usuario dedicado para despliegue (recomendado: no usar
`root`; crea un usuario `deploy` con permiso de grupo `docker`):

```bash
# En el VPS (una sola vez, como root o con sudo):
sudo useradd -m -s /bin/bash deploy
sudo usermod -aG docker deploy

# Desde tu máquina local, copia la clave pública al usuario deploy del VPS:
ssh-copy-id -i ~/.ssh/doctyp_deploy_key.pub deploy@TU_IP_O_DOMINIO_VPS
```

Verifica que la conexión funciona **antes** de configurar el secret en GitHub:

```bash
ssh -i ~/.ssh/doctyp_deploy_key deploy@TU_IP_O_DOMINIO_VPS "docker --version"
```

---

## 3. Clonar el repo en el VPS (una sola vez)

```bash
# Como el usuario deploy, en el VPS:
sudo mkdir -p /opt/doctyp
sudo chown deploy:deploy /opt/doctyp
cd /opt/doctyp
git clone https://github.com/KemosahbeAndres/informes-uti-slep-chinchorro.git .
```

Este `/opt/doctyp` es el `VPS_DEPLOY_PATH` que usará el workflow (§4) — puedes usar otra
ruta, pero debe coincidir con el secret.

### 3.1 Ajustar el dominio real

Edita `docker-compose.yml` en el VPS y cambia el `Host()` por tu dominio real (ya lo
hiciste en tu copia local con `doctyp.tinorte.cl` y la red `proxy` — asegúrate de que el
VPS tenga exactamente esos mismos valores, o vuelve a aplicarlos ahí si el clon trajo los
placeholders del repo):

```yaml
labels:
  - traefik.http.routers.doctyp.rule=Host(`doctyp.tinorte.cl`)
networks:
  - proxy   # o el nombre real de tu red de Traefik en este VPS
```

> Si vas a mantener el `docker-compose.yml` del repo como la fuente de verdad (recomendado
> para que el CI/CD no dependa de una edición manual que se pierde en cada `git reset
> --hard`), **haz este cambio en tu máquina local, commitéalo y púshalo** en vez de editarlo
> solo en el VPS — el paso 0.3 del flujo (`git reset --hard origin/master`) descartaría
> cualquier edición hecha directo en el servidor.

### 3.2 Fuentes con licencia (Museo Sans)

Museo Sans no se redistribuye (licencia) y por eso nunca viaja en la imagen ni en el repo.
Si quieres que los PDFs generados usen Museo Sans en vez del fallback (Liberation Sans),
copia los archivos de fuente al volumen `fonts` **después** de levantar el contenedor por
primera vez:

```bash
docker compose cp /ruta/local/a/tus/fuentes/. doctyp:/data/fonts/
docker compose restart doctyp
```

Si no tienes la licencia o no te importa por ahora, omite este paso — el sistema funciona
igual con Liberation Sans.

### 3.3 Primer arranque

```bash
cd /opt/doctyp
docker compose -f docker-compose.yml up -d --build
```

La primera vez tarda varios minutos (descarga typst/tinymist, instala dependencias de la
SPA, compila el frontend). Verifica que quedó arriba:

```bash
docker compose ps
docker compose logs -f doctyp   # Ctrl+C para salir del seguimiento de logs
```

Deberías ver `✔ Servidor doctyp web escuchando en http://0.0.0.0:8787/`. Si Traefik está
bien configurado, el sitio ya debería responder en `https://tu-dominio/`.

### 3.4 Migrar el registro y crear el primer usuario

Los datos **no** vienen en el repo — el VPS arranca con `organizations/`, `doctyp.db` y los
documentos completamente vacíos (viven en volúmenes, no en el código). Tienes dos casos:

**Caso A — primera instalación real, sin datos previos:** no hay nada que migrar. Entra a
`https://tu-dominio/` y la propia SPA te va a mostrar la pantalla de "crear el primer
usuario" (bootstrap, Etapa 20) — created ahí tu organización, plantilla y usuario admin
desde cero con `doctyp org new`/`template new` vía CLI (§3.5) o desde la interfaz.

**Caso B — ya tenías datos en `organizations/*/org.json` de una instalación anterior (fuera
de Docker) y quieres traerlos:** copia esas carpetas `organizations/<slug>/` al volumen
correspondiente del contenedor y corre la migración:

```bash
# Desde tu máquina con los org.json originales, cópialos al VPS:
scp -r -i ~/.ssh/doctyp_deploy_key organizations/tu-org deploy@TU_IP:/tmp/tu-org

# En el VPS, dentro del contenedor:
docker compose cp /tmp/tu-org doctyp:/data/organizations/tu-org
docker compose exec doctyp python3 doctyp.py migrate
docker compose exec doctyp python3 doctyp.py migrate --check   # verifica conteos
```

Y si además tenías documentos ya creados (carpetas bajo `<Documentos>/doctyp/<org>/`),
cópialos al volumen `docs_data` con el mismo patrón (`docker compose cp ... doctyp:/data/docs/tu-org`).

### 3.5 Comandos CLI dentro del contenedor

Cualquier subcomando de `doctyp` se ejecuta con `docker compose exec`:

```bash
docker compose exec doctyp python3 doctyp.py org new mi-org --nombre "Mi Organización"
docker compose exec doctyp python3 doctyp.py list
```

---

## 4. Configurar los secrets de GitHub Actions

En GitHub: **Settings → Secrets and variables → Actions → New repository secret** (del
repo `informes-uti-slep-chinchorro`). Crea estos cuatro:

| Secret | Valor |
|---|---|
| `VPS_HOST` | IP o dominio del VPS (p. ej. `123.45.67.89` o `vps.tinorte.cl`) |
| `VPS_USER` | `deploy` (el usuario creado en §2) |
| `VPS_SSH_KEY` | **Contenido completo** de `~/.ssh/doctyp_deploy_key` (la clave **privada**) — pégalo tal cual, incluyendo las líneas `-----BEGIN OPENSSH PRIVATE KEY-----` / `-----END...` |
| `VPS_DEPLOY_PATH` | `/opt/doctyp` (o la ruta real que usaste en §3) |

Opcional (si tu VPS no usa el puerto SSH 22 por defecto):

| Secret | Valor |
|---|---|
| `VPS_PORT` | El puerto SSH real, si no es 22 |

**Nunca pegues la clave privada en un issue, PR, commit, ni chat.** Los secrets de GitHub
se cifran en reposo y no vuelven a mostrarse una vez guardados — si necesitas verificarla,
regenera el par de claves en vez de intentar leerla de vuelta.

---

## 5. El workflow (`.github/workflows/deploy.yml`)

Ya está en el repo. Se dispara automáticamente en cada push a `master`, o manualmente desde
la pestaña **Actions** de GitHub (botón "Run workflow"). Hace exactamente esto en el VPS:

```bash
cd $VPS_DEPLOY_PATH
git fetch origin master
git reset --hard origin/master
docker compose -f docker-compose.yml up -d --build
docker image prune -f
```

`git reset --hard` (no `git pull`) para que el VPS siempre quede idéntico a `master`, sin
arriesgar un merge conflict a mitad de un despliegue automático. Esto significa: **cualquier
cambio hecho a mano dentro de `/opt/doctyp` en el VPS se pierde en el próximo despliegue** —
la única fuente de verdad del código es el repo. Los datos (`organizations/`, `doctyp.db`,
documentos) están a salvo porque viven en volúmenes Docker, fuera del working tree de git.

`docker image prune -f` al final limpia las imágenes viejas que van quedando huérfanas en
cada rebuild (cada deploy construye una imagen nueva; sin este paso, el disco del VPS se
llena con el tiempo).

### 5.1 Verificar que el CI/CD funciona

Después de configurar los 4 secrets:

1. Haz un cambio trivial (p. ej. un comentario) y púshalo a `master`.
2. Ve a la pestaña **Actions** del repo en GitHub — deberías ver el workflow "Desplegar a
   producción" corriendo.
3. Si falla, el log del step "Desplegar por SSH" muestra el error exacto (típicamente: clave
   mal pegada, usuario sin permiso de grupo `docker`, o `VPS_DEPLOY_PATH` incorrecto).

---

## 6. Backups

`docker-compose.yml` usa volúmenes nombrados (`data`, `docs_data`, `fonts`) — Docker los
gestiona en `/var/lib/docker/volumes/` (o el path de podman equivalente). Respaldo mínimo
recomendado, corriendo en el VPS (cron, o a mano periódicamente):

```bash
# Backup en caliente de la BD (SQLite + WAL, seguro hacerlo con el contenedor corriendo)
docker compose exec doctyp sh -c 'sqlite3 /data/doctyp.db ".backup /data/doctyp.db.backup"'
docker compose cp doctyp:/data/doctyp.db.backup ./backups/doctyp-$(date +%Y%m%d).db

# Documentos y plantillas (los .typ, snapshots, imágenes)
docker run --rm -v doctyp_docs_data:/data -v "$(pwd)/backups":/backup alpine \
  tar czf /backup/docs-$(date +%Y%m%d).tar.gz -C /data .
docker run --rm -v doctyp_data:/data -v "$(pwd)/backups":/backup alpine \
  tar czf /backup/organizations-$(date +%Y%m%d).tar.gz -C /data organizations
```

Copia esos backups fuera del VPS (otro servidor, almacenamiento externo) — un backup que
vive solo en la misma máquina no protege contra la pérdida del VPS completo.

---

## 7. Troubleshooting rápido

| Síntoma | Causa probable | Qué revisar |
|---|---|---|
| El workflow falla en "Desplegar por SSH" con "Permission denied" | La clave pública no quedó en `~/deploy/.ssh/authorized_keys`, o el secret `VPS_SSH_KEY` no tiene el contenido completo | Repite `ssh-copy-id` (§2); verifica el secret pegando la clave de nuevo, sin espacios extra al final |
| El sitio no responde por HTTPS aunque el contenedor está `Up` | Traefik no está viendo las labels, o el `Host()` no coincide con el dominio real | `docker compose logs doctyp`; revisa el dashboard de Traefik si lo tienes expuesto; confirma que `doctyp` y Traefik comparten la misma red (`docker network inspect proxy`) |
| `docker compose up -d --build` tarda mucho en cada deploy | Normal la primera vez (descarga typst/tinymist + build de la SPA); en deploys siguientes debería cachear capas si el `Dockerfile` no cambió | Si siempre es lento, revisa que no estés invalidando la caché de Docker sin necesidad (p. ej. tocar un archivo temprano en el `Dockerfile` en cada commit) |
| `doctyp migrate` no encuentra ningún `org.json` | Las carpetas de `organizations/` no se copiaron al volumen antes de migrar | Repite §3.4, confirmando la ruta de destino con `docker compose exec doctyp ls /data/organizations` |
| Perdiste la clave privada de despliegue | — | Genera un par nuevo (§2), reemplaza la clave pública en el VPS y el secret `VPS_SSH_KEY` en GitHub; borra la entrada vieja de `authorized_keys` en el VPS |
