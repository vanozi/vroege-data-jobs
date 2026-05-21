# Plan: Flask Dashboard Portal Voor Marimo Dashboards

## Doel

Maak een kleine Flask-app als centrale homepage voor dashboards. Gebruikers
moeten eerst inloggen en zien daarna een overzicht met links naar specifieke
Marimo-dashboardpagina's.

Dit portal wordt het publieke entrypoint. De losse Marimo-apps blijven achter
Traefik draaien, maar zijn niet direct publiek zonder dezelfde
toegangscontrole.

## Gewenste Structuur

Gewenste publieke structuur:

```text
https://dashboards.gebroedersvroege.nl/
  -> Flask login als gebruiker niet is ingelogd
  -> Flask overzichtspagina met dashboardlinks als gebruiker is ingelogd

https://dashboards.gebroedersvroege.nl/klauwgezondheid
  -> Marimo klauwgezondheid dashboard

https://dashboards.gebroedersvroege.nl/<toekomstig-dashboard>
  -> toekomstige Marimo dashboards
```

Voorbeelden van toekomstige routes:

```text
https://dashboards.gebroedersvroege.nl/melkproductie
https://dashboards.gebroedersvroege.nl/vruchtbaarheid
https://dashboards.gebroedersvroege.nl/datajobs
```

Gebruik dus een enkel domein met path-based routing. De root `/` is de Flask
portal. Dashboardroutes zijn korte, leesbare paden direct onder hetzelfde
domein.

## Hoofdkeuze: Waar Authenticatie Afdwingen

Er zijn twee logische opties.

### Optie A: Auth In Flask En Traefik ForwardAuth

Flask verzorgt login, sessie en autorisatie. Traefik gebruikt de Flask-app als
`forwardAuth` middleware voor Marimo-routes.

Voordelen:

- een login voor portal en Marimo dashboards;
- Marimo hoeft zelf geen auth te kennen;
- toekomstige dashboards kunnen dezelfde middleware gebruiken;
- gebruikers kunnen niet om de portal heen als Marimo-routes ook beschermd
  zijn.

Nadelen:

- iets meer Traefik-configuratie;
- Flask moet een auth-check endpoint aanbieden.

Aanbevolen voor productie.

### Optie B: Auth Alleen Op Flask Portal

Alleen de homepage heeft login. De Marimo links wijzen naar losse Marimo-routes
die niet extra worden afgeschermd, of alleen Basic Auth krijgen.

Voordelen:

- eenvoudiger.

Nadelen:

- gebruikers kunnen directe Marimo-URL's delen;
- auth is niet centraal gegarandeerd;
- later lastiger netjes op te schalen.

Niet aanbevolen voor publieke dashboards met bedrijfsdata.

## Aanbevolen Aanpak

Gebruik Optie A:

- Flask portal voor login en homepage;
- Flask endpoint `/auth/verify` voor Traefik ForwardAuth;
- Traefik beschermt alle dashboardroutes zoals `/klauwgezondheid` via dezelfde
  auth middleware;
- Marimo services blijven intern op Docker-netwerk bereikbaar;
- dashboardlinks worden gedefinieerd in een kleine registry/config.

## Flask Portal Scope

### Routes

Minimale routes:

- `GET /login`: loginformulier.
- `POST /login`: credentials controleren en sessie starten.
- `POST /logout`: sessie verwijderen.
- `GET /`: homepage met dashboardlinks als ingelogd, anders redirect naar
  `/login`.
- `GET /auth/verify`: endpoint voor Traefik ForwardAuth.
- `GET /healthz`: healthcheck zonder auth.

### Homepage

Toon dashboardkaarten met:

- naam;
- korte omschrijving;
- statuslabel, bijvoorbeeld `Productie`, `Concept`, `Intern`;
- link;
- laatste data-update als dat makkelijk beschikbaar is;
- optioneel eigenaar/contactpersoon.

Eerste dashboard:

```python
{
    "name": "Klauwgezondheid",
    "description": "Mortellaro en klauwgezondheid van de actieve koppel.",
    "url": "/klauwgezondheid",
    "status": "Productie",
}
```

## Authenticatie

### Eerste Versie

Gebruik eenvoudige server-side sessie-auth:

- gebruikersnaam + wachtwoord uit environment variables of een kleine
  server-only config;
- wachtwoorden gehasht opslaan, niet plaintext;
- Flask `SECRET_KEY` verplicht uit environment;
- sessie-cookie:
  - `Secure`;
  - `HttpOnly`;
  - `SameSite=Lax`;
  - korte of redelijke sessieduur, bijvoorbeeld 8 tot 24 uur.

Benodigde env vars:

```env
PORTAL_SECRET_KEY=...
PORTAL_ADMIN_USERNAME=...
PORTAL_ADMIN_PASSWORD_HASH=...
PORTAL_SESSION_HOURS=12
```

Gebruik geen plaintext `PORTAL_ADMIN_PASSWORD` in productie. Voor lokale
ontwikkeling mag dat tijdelijk, maar het plan voor deploy moet hashes gebruiken.

### Later

Als meerdere gebruikers nodig zijn:

- kleine database tabel `portal_users`;
- rollen zoals `admin`, `viewer`;
- dashboardrechten per rol;
- of uitbesteden aan bestaande identity provider via OAuth/OIDC.

## Traefik Integratie

Gebruik voor deze dashboards een zelfstandige Compose-stack met een eigen
Traefik-container. Deze stack staat los van de bestaande applicatie-compose.
Daarmee blijft de dashboardomgeving apart te deployen, te stoppen en te
configureren.

Voorbeeldconcept:

```yaml
services:
  traefik:
    image: traefik:v3.6
    command:
      - --providers.docker=true
      - --providers.docker.exposedbydefault=false
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
      - --entrypoints.web.http.redirections.entrypoint.to=websecure
      - --entrypoints.web.http.redirections.entrypoint.scheme=https
      - --certificatesresolvers.letsencrypt.acme.email=${TRAEFIK_ACME_EMAIL}
      - --certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json
      - --certificatesresolvers.letsencrypt.acme.httpchallenge=true
      - --certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - traefik_letsencrypt:/letsencrypt

  portal:
    build: .
    command: gunicorn "dashboard_portal.app:create_app()" --bind 0.0.0.0:8000
    env_file:
      - ./deploy/dashboard.env
    labels:
      - traefik.enable=true
      - traefik.http.routers.dashboard-portal.rule=Host(`${DASHBOARD_HOST}`)
      - traefik.http.routers.dashboard-portal.entrypoints=websecure
      - traefik.http.routers.dashboard-portal.tls.certresolver=letsencrypt
      - traefik.http.services.dashboard-portal.loadbalancer.server.port=8000
      - traefik.http.middlewares.portal-auth.forwardauth.address=http://portal:8000/auth/verify
      - traefik.http.middlewares.portal-auth.forwardauth.trustForwardHeader=true

  marimo-klauwgezondheid:
    build: .
    command: python -m marimo run dashboard/klauwbehandeling_dashboard.py --host 0.0.0.0 --port 2718 --base-url /klauwgezondheid --proxy https://${DASHBOARD_HOST} --no-token
    env_file:
      - ./deploy/dashboard.env
    labels:
      - traefik.enable=true
      - traefik.http.routers.marimo-klauw.rule=Host(`${DASHBOARD_HOST}`) && PathPrefix(`/klauwgezondheid`)
      - traefik.http.routers.marimo-klauw.entrypoints=websecure
      - traefik.http.routers.marimo-klauw.tls.certresolver=letsencrypt
      - traefik.http.routers.marimo-klauw.middlewares=portal-auth
      - traefik.http.services.marimo-klauw.loadbalancer.server.port=2718
```

ForwardAuth middleware concept:

```yaml
labels:
  - traefik.http.middlewares.portal-auth.forwardauth.address=http://portal:8000/auth/verify
  - traefik.http.middlewares.portal-auth.forwardauth.trustForwardHeader=true
```

De Compose `.env` bevat alleen Compose-waarden zoals `DASHBOARD_HOST` en
`TRAEFIK_ACME_EMAIL`. Portal- en database-secrets staan in
`deploy/dashboard.env`, zodat password hashes met `$` niet door Compose als
variabelen worden geinterpreteerd.

## Marimo Achter Een Dashboardroute

Controleer expliciet of Marimo goed werkt achter:

```text
/klauwgezondheid
```

Let op:

- websocket/connectiegedrag;
- static asset paths;
- base path support van Marimo;
- trailing slash gedrag;
- redirect headers achter Traefik.

Als path-based routing niet stabiel werkt, zijn er twee opties:

1. route herschrijven met Traefik middleware zodat Marimo intern `/` ziet;
2. alsnog per dashboard een subdomein gebruiken.

Subdomein fallback:

```text
https://klauwgezondheid.dashboards.gebroedersvroege.nl/
```

De Flask homepage kan dan nog steeds naar die subdomeinen linken. Maar de
voorkeur blijft:

```text
https://dashboards.gebroedersvroege.nl/klauwgezondheid
```

## Projectstructuur

Voorgestelde nieuwe module:

```text
dashboard_portal/
  __init__.py
  app.py
  auth.py
  config.py
  registry.py
  templates/
    base.html
    login.html
    dashboards.html
  static/
    portal.css
```

Waarom aparte `dashboard_portal` package:

- scheidt Flask UI van Marimo notebooks;
- voorkomt dat `dashboard/` te veel verantwoordelijkheden krijgt;
- maakt testen eenvoudiger.

## Dependencies

Toevoegen aan runtime dependencies:

- `Flask`;
- `gunicorn` voor Linux productie;
- eventueel `Werkzeug` expliciet alleen als nodig voor password hashing;
- optioneel `Flask-WTF` later, maar eerste versie kan zonder.

Gebruik bestaande projectafspraak:

- als er `requirements.piptools` komt of bestaat: top-level dependency daar;
- anders requirements aanpak consistent houden met huidige repo.

## UI Richting

Rustig en functioneel:

- simpele loginpagina;
- homepage met compacte cards of tabel;
- duidelijke dashboardnamen;
- geen marketingpagina;
- Nederlandse labels.

Voorbeeld homepage tekst:

- `Dashboards`
- `Klauwbehandelingen`
- `Mortellaro en klauwgezondheid van de actieve koppel`
- `Open dashboard`

## Security

Minimaal:

- alle routes behalve `/login`, `/healthz`, static assets en `/auth/verify`
  vereisen sessie;
- `/auth/verify` retourneert:
  - `2xx` als sessie geldig is;
  - `401` of `403` als sessie ontbreekt/ongeldig is;
- cookies `Secure`, `HttpOnly`, `SameSite=Lax`;
- `PORTAL_SECRET_KEY` verplicht;
- wachtwoordhash verplicht in productie;
- rate limiting op login via Traefik middleware of Flask later toevoegen;
- dashboard en database nooit zonder auth publiek.

Aanbevolen:

- Traefik IP allowlist als alleen bekende locaties toegang nodig hebben;
- fail2ban of Traefik rate limit;
- read-only database user voor dashboards.

## Tests

Voeg tests toe:

```text
tests/dashboard_portal/test_config.py
tests/dashboard_portal/test_auth.py
tests/dashboard_portal/test_routes.py
tests/dashboard_portal/test_registry.py
```

Testcases:

- ontbrekende `PORTAL_SECRET_KEY` faalt duidelijk;
- login met verkeerde credentials faalt;
- login met juiste credentials zet sessie;
- `/` redirect naar login zonder sessie;
- `/` toont dashboardlinks met sessie;
- `/auth/verify` geeft `401` zonder sessie;
- `/auth/verify` geeft `200` met sessie;
- registry bevat geldige relatieve of absolute dashboardlinks.

## Implementatiefasen

### Fase 1. Portal Basisskelet

1. Maak `dashboard_portal/`.
2. Voeg config loader toe.
3. Voeg dashboard registry toe.
4. Voeg Flask app factory toe.
5. Voeg templates toe voor login en homepage.

Acceptatiecriteria:

- `python -m flask --app dashboard_portal.app:create_app routes` werkt.
- Homepage bestaat maar is beschermd achter login.

### Fase 2. Authenticatie

1. Implementeer password hash verificatie.
2. Implementeer login/logout.
3. Implementeer sessieconfiguratie.
4. Implementeer `/auth/verify` voor Traefik.

Acceptatiecriteria:

- Zonder login geen toegang tot `/`.
- Met login wel toegang.
- `/auth/verify` werkt voor Traefik ForwardAuth.

### Fase 3. Dashboard Registry

1. Maak registry voor huidige en toekomstige dashboards.
2. Voeg Klauwgezondheid dashboard toe met route `/klauwgezondheid`.
3. Toon dashboardkaarten op homepage.
4. Maak links configureerbaar via code of environment.

Acceptatiecriteria:

- Nieuwe dashboards kunnen worden toegevoegd zonder loginlogica te wijzigen.
- Homepage toont alleen dashboards uit registry.

### Fase 4. Docker En Traefik

1. Voeg een zelfstandige Traefik service toe aan de Compose-stack.
2. Voeg portal service toe aan Compose plan.
3. Voeg Marimo dashboard service toe als aparte service.
4. Configureer Traefik route voor portal.
5. Configureer Traefik ForwardAuth voor Marimo routes.
6. Test path-prefix routing; val terug op subdomeinen als nodig.

Acceptatiecriteria:

- Portal is bereikbaar via HTTPS.
- Marimo is alleen bereikbaar met geldige portal-sessie.
- Direct openen van Marimo zonder sessie faalt.

### Fase 5. Tests En Verificatie

1. Voeg pytest tests toe.
2. Run focused tests.
3. Run Ruff.
4. Test lokaal met Flask dev server.
5. Test in container.

Acceptatiecriteria:

- Tests slagen.
- Ruff slagen.
- Loginflow werkt lokaal en achter Traefik.

## Open Vragen

- Wil je een gedeelde gebruiker of meerdere gebruikers?
- Is Basic Auth via Traefik voldoende als eerste stap, of wil je direct een
  echte Flask-loginpagina?
- Heeft Marimo extra base-path of strip-prefix configuratie nodig voor
  `/klauwgezondheid`?
- Welke bestaande Traefik auth middleware is er al beschikbaar?
- Moeten gebruikersrollen bepalen welke dashboards zichtbaar zijn?
