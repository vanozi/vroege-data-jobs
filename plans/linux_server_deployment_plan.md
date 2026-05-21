# Plan: Linux Server Deployment Voor Datajobs En Dashboard

## Doel

Het project moet op een Linux-server draaien zodat:

- de datajobs elke nacht automatisch draaien;
- database migrations gecontroleerd worden uitgevoerd;
- het Marimo-dashboard publiekelijk bereikbaar is;
- de bestaande Traefik reverse proxy op de server wordt hergebruikt;
- secrets en databasegegevens niet in git terechtkomen.

De server draait al een andere applicatie via Docker Compose met Traefik. De
voorkeursaanpak is daarom: geen tweede Traefik-container starten, maar deze
applicatie als extra Compose-project aansluiten op het bestaande Traefik
netwerk.

## Belangrijkste Keuzes

### Traefik

Draai normaal geen tweede Traefik-container naast de bestaande Traefik.

Redenen:

- twee Traefik-containers willen vaak allebei poorten `80` en `443` binden;
- twee ACME/Let's Encrypt configuraties kunnen elkaar in de weg zitten;
- routing, TLS en middleware worden onduidelijker;
- debugging wordt lastiger.

Gebruik in plaats daarvan:

- het bestaande externe Docker-netwerk van Traefik, bijvoorbeeld
  `traefik_proxy`;
- labels op de Marimo-dashboard service;
- eventueel Traefik middleware voor Basic Auth, forward-auth, IP allowlist of
  SSO.

Een tweede Traefik is alleen logisch wanneer:

- hij op andere poorten draait;
- hij een volledig gescheiden netwerk/omgeving bedient;
- er een duidelijke operationele reden is voor scheiding.

Voor dit project is dat niet nodig.

### Processen

Gebruik aparte containers/processen voor aparte verantwoordelijkheden:

- `dashboard`: draait Marimo en is via Traefik bereikbaar.
- `scheduler`: draait de nachtelijke datajobs.
- `db`: alleen als deze projectdatabase ook op deze server in Docker beheerd
  moet worden. Als er al een PostgreSQL draait, gebruik dan die bestaande
  database.

Gebruik geen `init_db()` als runtime schema-oplossing. Migrations blijven via
Alembic lopen.

## Gewenste Serverstructuur

Aanbevolen directory op de server:

```text
/opt/vroege-data-jobs/
  docker-compose.yml
  .env
  app/
    <repo checkout>
  logs/
  backups/
```

Of eenvoudiger:

```text
/opt/vroege-data-jobs/
  <repo checkout>
  .env
  docker-compose.yml
```

Belangrijk:

- `.env` staat op de server, niet in git.
- Docker secrets zijn beter dan `.env` voor wachtwoorden, maar `.env` is
  acceptabel als eerste stap als bestandsrechten goed staan.
- Zet `.env` op `chmod 600`.

## Configuratie

Minimaal benodigde omgevingsvariabelen:

```env
DATABASE_URL=postgresql+psycopg://user:password@postgres:5432/gebroeders-vroege

KLAUWSCORE_USERNAME=...
KLAUWSCORE_PASSWORD=...
KLAUWSCORE_BASE_URL=http://klauwscore.nl
KLAUWSCORE_LOGIN_PATH=/login
KLAUWSCORE_STALLIJST_PATH=/veepedicure/stallijst
KLAUWSCORE_HEADLESS=true

UNIFORM_BASE_URL=...
UNIFORM_USERNAME=...
UNIFORM_PASSWORD=...
UNIFORM_CLIENT_ID=...
UNIFORM_HERD_ID=c670836f-7732-43a1-ac5a-70c4f63435f4
UNIFORM_REQUEST_TIMEOUT_SECONDS=60
UNIFORM_MAX_RETRIES=1
```

Aanvullend voor het dashboard:

```env
MARIMO_HOST=0.0.0.0
MARIMO_PORT=2718
```

## Docker Image

Maak een projectimage die:

1. Python dependencies installeert uit de bestaande dependencybestanden.
2. Playwright browser dependencies installeert voor de Klauwscore scraper.
3. De applicatiecode bevat.
4. Als non-root user draait.
5. Logs naar stdout/stderr schrijft.

Acceptatiecriteria:

- `python -m data_jobs.klauwscore.scripts.collect_klauwscore --summary --dry-run`
  werkt in de container.
- `python -m data_jobs.uniform_agri.scripts.koe_data --dry-run --limit 1`
  werkt in de container.
- `python -m marimo check dashboard/klauwbehandeling_dashboard.py` werkt in de
  container.

## Docker Compose Ontwerp

Voorbeeldstructuur:

```yaml
services:
  dashboard:
    image: vroege-data-jobs:latest
    env_file: .env
    command:
      - python
      - -m
      - marimo
      - run
      - dashboard/klauwbehandeling_dashboard.py
      - --host
      - 0.0.0.0
      - --port
      - "2718"
    networks:
      - default
      - traefik_proxy
    labels:
      - traefik.enable=true
      - traefik.http.routers.vroege-dashboard.rule=Host(`dashboard.example.nl`)
      - traefik.http.routers.vroege-dashboard.entrypoints=websecure
      - traefik.http.routers.vroege-dashboard.tls.certresolver=letsencrypt
      - traefik.http.services.vroege-dashboard.loadbalancer.server.port=2718

  scheduler:
    image: vroege-data-jobs:latest
    env_file: .env
    command:
      - supercronic
      - /app/deploy/crontab
    networks:
      - default
    restart: unless-stopped

networks:
  traefik_proxy:
    external: true
```

De exacte Traefik labels moeten aansluiten op de bestaande Traefik-configuratie:

- bestaande networknaam;
- bestaande entrypoints;
- bestaande certresolver;
- bestaande auth middleware.

## Dashboard Publiek Beschikbaar Maken

Het dashboard bevat bedrijfsdata. Maak het niet zonder toegangscontrole publiek.

Aanbevolen:

1. Publiceer via een subdomein, bijvoorbeeld `dashboard.boerderij.nl`.
2. Gebruik bestaande Traefik TLS.
3. Zet minstens Basic Auth of forward-auth voor het dashboard.
4. Overweeg IP allowlisting als alleen vaste gebruikers toegang nodig hebben.
5. Controleer of Marimo achter de reverse proxy goed werkt met websockets.

Acceptatiecriteria:

- `https://dashboard...` opent het dashboard.
- De verbinding gebruikt TLS.
- Ongeauthenticeerde bezoekers krijgen geen dashboarddata te zien.
- Het dashboard kan de database lezen met read-only of minimaal benodigde
  rechten.

## Nachtelijke Datajobs

Gebruik bij voorkeur een scheduler-container in plaats van host cron. Goede
opties:

- `supercronic`: eenvoudig, container-native, logs naar stdout.
- `ofelia`: Docker-label based scheduler.
- systemd timers op de host: kan ook, maar minder self-contained.

Aanbevolen eerste versie: `supercronic`.

Voorbeeld crontab:

```cron
SHELL=/bin/sh
PATH=/usr/local/bin:/usr/bin:/bin

# 02:00 migrations
0 2 * * * cd /app && alembic -c database/alembic.ini upgrade head

# 02:10 Uniform Agri koeien en details
10 2 * * * cd /app && python -m data_jobs.uniform_agri.scripts.koe_data --include-details

# 03:00 Klauwscore stallijst
0 3 * * * cd /app && python -m data_jobs.klauwscore.scripts.collect_klauwscore --summary
```

Mogelijke uitbreiding:

- Uniform Agri melkingen apart plannen, omdat dit meer API-calls kan geven:

```cron
30 2 * * * cd /app && python -m data_jobs.uniform_agri.scripts.koe_data --include-details --include-milkings
```

Begin conservatief:

1. Eerst migrations.
2. Daarna Uniform Agri zonder melkingen.
3. Daarna Klauwscore.
4. Pas later melkingen toevoegen als runtime en API-stabiliteit bekend zijn.

## Database

Aanpak:

1. Gebruik PostgreSQL.
2. Draai Alembic migrations bij deploy en/of voor de nachtelijke jobs.
3. Maak backups voordat migrations automatisch draaien.
4. Gebruik aparte database user waar mogelijk:
   - dashboard user: read-only;
   - datajob user: read/write;
   - migration user: schema privileges.

Pragmatische eerste versie:

- één database user voor app + jobs;
- dagelijkse databasebackup;
- later opsplitsen naar least privilege.

Backupvoorbeeld:

```sh
pg_dump "$DATABASE_URL" | gzip > /opt/vroege-data-jobs/backups/db-$(date +%F).sql.gz
```

Bewaar backups minimaal 14 tot 30 dagen.

## Deployment Workflow

### Eerste Installatie

1. Maak serverdirectory.
2. Clone repo.
3. Maak `.env` aan op de server.
4. Bouw Docker image.
5. Verbind Compose-project met bestaand Traefik-netwerk.
6. Run migrations handmatig:

   ```sh
   docker compose run --rm scheduler alembic -c database/alembic.ini upgrade head
   ```

7. Test jobs met dry-run:

   ```sh
   docker compose run --rm scheduler python -m data_jobs.uniform_agri.scripts.koe_data --dry-run --limit 5
   docker compose run --rm scheduler python -m data_jobs.klauwscore.scripts.collect_klauwscore --summary --dry-run
   ```

8. Start dashboard:

   ```sh
   docker compose up -d dashboard
   ```

9. Controleer Traefik route en auth.
10. Start scheduler:

    ```sh
    docker compose up -d scheduler
    ```

### Reguliere Deploy

1. Pull nieuwe code.
2. Bouw nieuwe image.
3. Run tests of minimaal importchecks in image.
4. Run migrations.
5. Restart dashboard.
6. Scheduler blijft doorlopen of wordt opnieuw gestart.

Voorbeeld:

```sh
git pull
docker compose build
docker compose run --rm scheduler alembic -c database/alembic.ini upgrade head
docker compose up -d dashboard scheduler
docker compose logs -f --tail=100 dashboard
```

## Logging En Monitoring

Minimaal:

- Docker logs verzamelen via bestaande host logging.
- Datajob commands moeten summary counts loggen.
- Scheduler logs moeten zichtbaar zijn met `docker compose logs scheduler`.

Aanbevolen:

- healthcheck op dashboard HTTP endpoint;
- alert als scheduler job faalt;
- alert als databasebackup faalt;
- logrotate of centrale logging.

Nuttige checks:

```sh
docker compose ps
docker compose logs --tail=200 scheduler
docker compose logs --tail=200 dashboard
```

## Security

1. Dashboard nooit open zonder auth.
2. `.env` niet committen.
3. Server firewall: alleen `80`, `443`, en SSH open.
4. SSH met keys, geen password login.
5. Database niet publiek exposen.
6. Playwright/Klauwscore credentials alleen in server secrets.
7. Regelmatige OS en Docker updates.

## Fases

### Fase 1. Serverinventarisatie

1. Bepaal bestaande Traefik networknaam.
2. Bepaal bestaande Traefik entrypoints en certresolver.
3. Bepaal of PostgreSQL al bestaat of in dit Compose-project moet komen.
4. Bepaal gewenst dashboarddomein.

Acceptatiecriteria:

- Bekend welke Traefik labels nodig zijn.
- Bekend waar `DATABASE_URL` naar wijst.
- Bekend welke poort Marimo intern gebruikt.

### Fase 2. Docker Image

1. Maak Dockerfile.
2. Installeer Python dependencies.
3. Installeer Playwright dependencies.
4. Voeg non-root user toe.
5. Test CLI commands in de image.

Acceptatiecriteria:

- Klauwscore dry-run werkt in container.
- Uniform dry-run werkt in container.
- Marimo check werkt in container.

### Fase 3. Compose En Traefik

1. Maak `docker-compose.yml` voor dashboard en scheduler.
2. Sluit dashboard aan op bestaand Traefik-netwerk.
3. Voeg Traefik labels toe.
4. Voeg auth middleware toe.
5. Start dashboard.

Acceptatiecriteria:

- Dashboard is bereikbaar via HTTPS.
- Auth werkt.
- Geen tweede Traefik nodig.

### Fase 4. Scheduler

1. Voeg `supercronic` of gelijkwaardige scheduler toe.
2. Maak crontab voor migrations en jobs.
3. Start met dry-run of beperkte `--limit`.
4. Schakel volledige jobs pas in na succesvolle runs.

Acceptatiecriteria:

- Nachtelijke jobs draaien automatisch.
- Fouten zijn zichtbaar in logs.
- Jobs muteren alleen de database als dry-run bewust uit staat.

### Fase 5. Backups En Monitoring

1. Voeg dagelijkse databasebackup toe.
2. Voeg backupretentie toe.
3. Voeg simpele healthchecks toe.
4. Documenteer herstelprocedure.

Acceptatiecriteria:

- Backupbestand wordt dagelijks aangemaakt.
- Minimaal één restore-test is gedaan.
- Dashboard en scheduler status zijn controleerbaar.

## Open Vragen

- Staat PostgreSQL al op de server of moet deze in het nieuwe Compose-project?
- Wat is de bestaande Traefik networknaam?
- Welke auth gebruikt de bestaande applicatie achter Traefik?
- Welk domein/subdomein moet het dashboard krijgen?
- Moeten Uniform melkingen elke nacht mee, of minder vaak vanwege runtime/API
  load?
- Hoe lang moeten databasebackups bewaard blijven?
