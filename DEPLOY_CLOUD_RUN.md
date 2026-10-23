# Dashboard PCP — despliegue en Google Cloud Run (gratis)

Servicio de solo lectura: lee el Sheet `1Svr0a4lwiw1b4Eujr_aMJwfd3N1kbVfSTa1IjzBMbQ4`
y muestra la pestaña Pallets + Campaña. El sync con Gestagro corre aparte, en la LAN.

## Prerrequisitos

- Cuenta Google con billing habilitado (el free tier cubre este caso con `min-instances=0`).
- Credencial de solo lectura del Sheet (OAuth token o service account JSON).
- Todo se hace desde **Cloud Shell** (sin instalar `gcloud` local).

## 1. Clonar y preparar el repo

```bash
git clone https://github.com/Rixhard001/Dashboard-pcp.git
cd Dashboard-pcp
gcloud config set project <TU_PROJECT_ID>
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com
```

## 2. Subir la credencial a Secret Manager (no va en la imagen)

```bash
# OAuth token (el que ya tenés como token_pallet_readonly.json):
gcloud secrets create google-creds --data-file=token_pallet_readonly.json

# o service account:
gcloud secrets create google-creds --data-file=sa-pallets-viewer.json
```

## 3. Desplegar

```bash
gcloud run deploy dashboard-pcp \
  --source . \
  --region southamerica-west1 \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 2 \
  --memory 512Mi \
  --set-secrets GOOGLE_CREDENTIALS_JSON=google-creds:latest \
  --set-env-vars SPREADSHEET_ID=1Svr0a4lwiw1b4Eujr_aMJwfd3N1kbVfSTa1IjzBMbQ4
```

La primera build tarda ~3-5 minutos. El comando devuelve la URL del servicio.

## 4. Verificar

```bash
gcloud run services describe dashboard-pcp --region southamerica-west1 --format='value(status.url)'
curl -s "$(gcloud run services describe dashboard-pcp --region southamerica-west1 --format='value(status.url)')/api/campania" | head -c 200
```

## Costos

- Con `min-instances=0` no hay cargo cuando nadie entra.
- El free tier mensual cubre el uso normal de consulta (2M requests, 180k vCPU-s).
- Si alguien deja la página abierta refrescando todo el día, o se pone `min-instances=1`, ahí sí se cobra.

## Advertencias

- `--allow-unauthenticated` deja el dashboard **público**. Si los datos no deben ser públicos, quitá ese flag y usá IAM (cada usuario necesita cuenta Google en la organización).
- El caché de 1 h vive en cada instancia. Con `max-instances=2` puede haber dos cachés distintas — inofensivo, se refresca solo.
- El dashboard muestra lo último que haya en el Sheet, que escribe la tarea de la LAN. Si la sesión de la PC está cerrada, los datos quedan viejos sin aviso (mirá la fecha en "Última lectura del Sheet").
- La región `southamerica-west1` (Santiago) es la más cercana a Perú. Si no está disponible en tu cuenta, usá `us-central1`.
