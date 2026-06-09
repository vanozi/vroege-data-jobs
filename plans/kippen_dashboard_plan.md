# Plan: Kippen Dashboard (Marimo)

## Doel

Een Marimo-dashboard bouwen dat productieanalyse geeft over een geselecteerde
stal en koppel (flock). Vergelijkbaar met `klauwbehandeling_dashboard` en
`tank_terminal_dashboard`: bereikbaar via het portal op
`/kippen-dashboard`, beveiligd via Traefik ForwardAuth, en aangedreven door
de bestaande Kippen-tabellen in PostgreSQL.

Het dashboard is een **analyseschijf op de invoer** — niet bedoeld voor
invoer of correctie. De Kippen Flask-app blijft de bron voor registraties.

## Gebruikers en gebruikssituatie

- **Beheerders** (Kippen `admin` rol op een nieuwe dashboard-app, zie
  Authenticatie hieronder): bedrijfsleider, dierenarts, externe adviseur.
- **Niet voor de werknemer** die alleen registraties doet — dat blijft de
  Kippen registratie-app.
- Geopend op laptop of groot scherm. Niet primair mobiel.

Typische vragen die het dashboard moet beantwoorden:

- Hoe ontwikkelt het legpercentage zich richting de top, en hoe verloopt de
  productiecurve daarna ten opzichte van de koppelnorm?
- Hoe consistent is de water- en voeropname per dag/per week?
- Wat is de voederconversie en hoe trendt die over de tijd?
- Lopen we voor of achter op gemiddeld eigewicht t.o.v. de leeftijdsweek?
- Is er een piek in dode hennen of buitennest-eieren in een bepaalde periode?
- Hoeveel pallets en kilo's eieren zijn er deze week geproduceerd?

## Scope

In scope:

- Eén nieuw Marimo-dashboard `dashboard/kippen_dashboard.py`.
- Filters: huis (`house_id`) en koppel (`Flock`), met defaults op het
  actieve huis/koppel. Optioneel datumbereik binnen het koppel.
- Trendgrafieken (Altair, conform de andere twee dashboards) voor de zes
  KPI-categorieën uit de vraagstelling:
  1. Voer en water opname (per dag).
  2. Buitennest-eieren (per dag).
  3. Dode hennen (per dag) plus cumulatieve uitval.
  4. Palletgewicht en gemiddeld eigewicht.
  5. Totaal afgedraaide eieren en legpercentage.
  6. Voederconversie (FCR) = gram voer ÷ eimassa in gram.
- Header-KPI-cards voor de meest gebruikte cijfers (legpercentage vandaag,
  totaal afgedraaide eieren in week, gemiddeld eigewicht in week, cumulatieve
  uitval %).
- Eén Marimo container in `docker-compose.yml`, Traefik labels analoog aan
  de twee bestaande Marimo dashboards.
- Tile in het portaaloverzicht.
- Bootstrap van een nieuwe `applications`-rij + `viewer`/`admin` rollen.
- **Nieuwe tabel `flock_lay_curve_norms`** met de Dekalb White ISA-richtlijn
  uit `dekalb_wit_legkalender.pdf` (leeftijd 18 t/m 100 weken), zodat elke
  grafiek de werkelijke koppelprestatie kan plotten tegen de norm.

Buiten scope (later optioneel):

- Voorspellende modellen / breakeven-analyses.
- Bewerken van registraties vanuit het dashboard.
- Vergelijking tussen koppels (cross-flock) — eerste versie is per koppel.
- Mobiele optimalisatie.
- UI in de Kippen-app om normen toe te voegen of te bewerken; voor v1
  komen normen via een migratie + seed.
- Real-time updates; het dashboard leest bij elke pagina-load opnieuw uit
  PostgreSQL, conform de bestaande Marimo dashboards.

## Datadefinities

Alle data zit in de Kippen-tabellen die de registratie-app al schrijft.
Het dashboard doet **alleen reads**.

Relevante tabellen (zie `database/models/laying_hens.py`):

| Tabel | Hoofdvelden voor het dashboard |
|---|---|
| `flocks` | `id`, `flock_name`, `date_of_birth`, `placement_date`, `end_date`, `bird_count`, `house_id`, `is_active` |
| `egg_registrations` | `house_id`, `flock_id`, `registration_date`, `first_quality_eggs`, `second_quality_eggs`, `total_eggs` |
| `feed_water_registrations` | `house_id`, `flock_id`, `registration_date`, `water_ml`, `feed_grams` |
| `dead_hen_registrations` | `house_id`, `flock_id`, `found_at`, `count`, `stable_side`, `walkway`, `found_place`, `suspected_cause` |
| `outside_nest_egg_rounds` | `house_id`, `flock_id`, `round_at`, `egg_count` |
| `egg_pallet_weight_registrations` | `house_id`, `flock_id`, `registration_date`, `supplier_name`, `pallet_weight_kg`, `empty_packaging_weight_kg`, `egg_count_per_pallet`, `egg_weight_grams` |

### Nieuwe tabel: `flock_lay_curve_norms`

Referentienormen per ras/strain per leeftijdsweek, uit fabrikant-PDFs zoals
`dekalb_wit_legkalender.pdf`. Eén rij = één leeftijdsweek voor één strain.

Velden:

| Kolom | Type | Bron in PDF | Eenheid |
|---|---|---|---|
| `id` | `int PK` | — | — |
| `breed_key` | `str`, indexed | filename / strain-naam, bv. `"dekalb_white_scharrel_voliere"` | — |
| `breed_name` | `str` | header van de PDF, bv. `"DEKALB WHITE SCHARREL EN VOLIÈRE"` | — |
| `age_weeks` | `int`, ge=18, le=100 | kolom **LEEFTIJD** | weken |
| `lay_percentage` | `Decimal(5,2)` | **% LEG** | % |
| `egg_weight_grams` | `Decimal(5,2)` | **EIGEWICHT IN GRAM** | gram |
| `egg_mass_grams` | `Decimal(5,2)` | **EIMASSA IN GRAM** | gram |
| `feed_intake_grams_per_day` | `Decimal(5,2)` | **VOEROPNAME IN GRAM/DAG** | gram/dag |
| `feed_conversion_ratio` | `Decimal(5,3)` | **VOEDER CONVERSIE** | g voer / g ei |
| `liveability_percentage` | `Decimal(5,2)` | **% LEEFBAARHEID** | % |
| `cumulative_eggs_per_placed_hen` | `Decimal(6,1)` | **AANTAL EIEREN** (per opgezette hen, cumulatief) | stuks |
| `cumulative_egg_kg_per_placed_hen` | `Decimal(6,2)` | **KG EI CUMULATIEF** | kg |
| `cumulative_feed_kg_per_placed_hen` | `Decimal(6,2)` | **KG VOER CUMULATIEF** | kg |
| `cumulative_feed_conversion_ratio` | `Decimal(5,3)` | **VOEDERCONVERSIE CUMULATIEF** | g voer / g ei |
| `hen_weight_grams` | `int` | **HEN GEWICHT** | gram |
| `source` | `str` | bv. `"L9120-ic-1 ISA B.V."`, of bestandsnaam | — |
| `created_at`, `updated_at` | `datetime` | mixin | — |

Constraints:

- `UNIQUE (breed_key, age_weeks)` zodat één strain niet twee waarden voor
  dezelfde week kan hebben.
- `age_weeks BETWEEN 18 AND 100` als CheckConstraint — de Dekalb-tabel
  start op week 18 (opfok) en stopt op 100.

Koppeling aan een koppel:

- `flocks.breed` bestaat al (`Optional[str]`). We voegen géén FK toe, want
  `breed` is vrij tekst en kan typo's bevatten.
- Het dashboard normaliseert `flocks.breed` naar een `breed_key` met een
  kleine lookup (lowercase, spaties → underscores, accenten weg).
- Als de koppel-`breed` niet matcht met een `breed_key` in
  `flock_lay_curve_norms`: het dashboard toont de normen niet, met een korte
  hint ("geen normcurve gevonden voor ras X").

### Afgeleide grootheden

| Grootheid | Definitie |
|---|---|
| Leeftijdsweek (`flock_week`) | `((registration_date - date_of_birth).days - 1) // 7`, met minimum 0. Identiek aan `kippen_app/flock_age.py:calculate_bird_age`. |
| Actuele kippenstand op datum D | `bird_count - cum_sum(dead_hen_registrations.count where found_at.date() <= D)`. |
| Legpercentage op datum D | `total_eggs(D) / kippenstand(D) * 100`. |
| Buitennest per dag | `sum(outside_nest_egg_rounds.egg_count where round_at.date() = D)`. |
| Cumulatieve uitval % | `cum_dead / bird_count * 100` per datum. |
| Eimassa per dag (gram) | `total_eggs(D) * gem_eigewicht(D)`. Waar `gem_eigewicht(D)` het gemiddelde van alle `egg_pallet_weight_registrations.egg_weight_grams` op datum D is. Als er op die dag geen pallet is geregistreerd: laatst bekende eigewicht (forward fill) of NULL — keuze maken bij implementatie, zie open vraag. |
| Voederconversie (FCR) | `feed_grams(D) / eimassa(D)`. Als eimassa NULL/0: FCR NULL. |
| Rollend 7-daags gemiddelde | Voor water, voer, FCR en legpercentage altijd óók een 7-day rolling line tonen om dag-ruis te dempen. |

### Eimassa-strategie (besloten: forward fill)

Pallets worden niet elke dag gewogen. We gebruiken **forward fill**:
het laatst bekende eigewicht wordt doorgetrokken naar volgende dagen tot
de eerstvolgende pallet-meting.

- Dagen vóór de allereerste pallet-meting in een koppel hebben geen
  eigewicht, dus geen eimassa en geen FCR (NULL). Op de chart blijven die
  dagen een gat — geen verzonnen cijfers.
- Geen harde cap op de forward-fill leeftijd. Een meting blijft geldig
  totdat de volgende meting komt.
- Op de FCR- en eigewicht-grafieken worden de **gemeten dagen** als
  zichtbare markers (punten) op de lijn weergegeven, zodat de gebruiker
  ziet hoe vers het cijfer is.
- Het rauwe palletgewicht-scatter in de palletchart (zie UI Layout #4)
  blijft één punt per pallet — dat is altijd een gemeten waarde.

## UI Layout

Boven aan de pagina een filterbalk; daaronder KPI-cards; daaronder vier of
vijf gestapelde tabbladen of secties. Bestaande dashboards gebruiken één
lange scroll-pagina met `mo.md` koppen tussen blokken. Aanhouden — geen
tabs.

### Filters (sticky boven aan de pagina)

- `mo.ui.dropdown` huiskeuze; default actieve huis (vandaag onbekend → kies
  het huis met meeste recente registraties).
- `mo.ui.dropdown` koppel binnen het huis (toon `flock_name` + start- en
  einddatum). Default: het actieve koppel; bij geen actief koppel het laatst
  geëindigde koppel.
- `mo.ui.date_range` datumbereik. Default: vanaf `placement_date` t/m
  `min(end_date or today, today)`.
- `mo.ui.switch` "Toon 7-daags voortschrijdend gemiddelde". Default aan.

### KPI-cards

Vier of vijf compacte cards bovenin, alle berekend over het geselecteerde
bereik:

- Geselecteerd koppel · plaatsingsdatum · leeftijd op laatste datum in
  selectie.
- Aantal hennen op laatste datum (na uitval).
- Cumulatief % uitval.
- Totaal afgedraaide eieren in de selectie.
- Gemiddeld legpercentage in de selectie.

### Trendgrafieken (één voor elke vraag)

Elke trendgrafiek heeft waar mogelijk **twee lagen**: de werkelijke meting
in een opvallende kleur, en de norm uit `flock_lay_curve_norms` als een
grijze stippellijn (Altair `strokeDash`). De X-as is *leeftijdsweek*, niet
kalenderdatum, zodat metingen en norm naast elkaar liggen.

Een togglt-switch boven de grafieken — `mo.ui.switch` "Toon norm" — laat
de gebruiker de normlijnen aan/uit zetten. Default aan.

Volgorde zoals de gebruiker ze opnoemde, want dat is hun mentale model:

1. **Voer en water per dag.** Twee lijnen (water_ml en feed_grams) op een
   dubbele Y-as, of twee aparte charts onder elkaar. Met 7-day rolling.
   Normlijn: `feed_intake_grams_per_day` per leeftijdsweek voor voer
   (water staat niet in de Dekalb-norm).
2. **Buitennest-eieren per dag.** Bar chart. Optioneel kleur per
   tijd-van-dag-bucket (ochtend/middag) als nuttig blijkt. Geen norm.
3. **Dode hennen per dag.** Bar chart per dag + lijn voor cumulatief
   uitval-%. Norm: `100 - liveability_percentage` als verwachte cumulatieve
   uitval, op de rechter Y-as.
4. **Palletgewicht en eigewicht.** Scatter van `pallet_weight_kg` op datum,
   plus een lijn met `egg_weight_grams`. Annotatie met `supplier_name`.
   Normlijn: `egg_weight_grams` per leeftijdsweek.
5. **Totaal afgedraaide eieren en legpercentage.** Stacked bar (1e + 2e
   soort) en een legpercentage-lijn op rechter Y-as. Normlijn:
   `lay_percentage` per leeftijdsweek.
6. **Voederconversie.** Lijn met FCR per dag (forward-filled eigewicht) +
   7-day rolling. Markers waar het eigewicht daadwerkelijk gemeten is.
   Normlijn: `feed_conversion_ratio` per leeftijdsweek.

Onder elke chart: een korte `mo.md` regel met de berekende waardes uit
het bereik (gemiddelden, min/max) als sanity-check, plus een **delta** ten
opzichte van de norm voor dezelfde leeftijdsweek (bv. "Legpercentage week
33: 96,4% — norm 97,0% — −0,6 pp").

### Cumulatieve KPI-card

Boven de trendgrafieken, een extra blok dat de **cumulatieve grootheden uit
"per opgezette hen"** vergelijkt:

| KPI | Werkelijk | Norm (leeftijdsweek nu) | Δ |
|---|---|---|---|
| Eieren per opgezette hen | berekend | `cumulative_eggs_per_placed_hen` | |
| Kg ei per opgezette hen | berekend | `cumulative_egg_kg_per_placed_hen` | |
| Kg voer per opgezette hen | berekend | `cumulative_feed_kg_per_placed_hen` | |
| Cumulatieve FCR | berekend | `cumulative_feed_conversion_ratio` | |
| Leefbaarheid | `100 − cum_uitval_%` | `liveability_percentage` | |

Werkelijke cumulatieve cijfers worden berekend met de
`bird_count` op plaatsingsdatum als noemer (dat is de "opgezette hen"
definitie).

### Datatabel onderaan

Een rauwe per-dag-tabel met alle berekende kolommen, sorteerbaar, voor
gebruikers die liever cijfers zien. Hergebruikbaar als CSV-download
(`mo.download` met polars `write_csv`).

## Authenticatie en autorisatie

### Nieuwe shared-auth applicatie

Toevoegen aan `shared_auth/bootstrap.py:CORE_APPLICATIONS`:

```python
CoreApplication(
    key="dashboard_kippen",
    name="Kippen dashboard",
    url="/kippen-dashboard",
    category="dashboard",
    description="Analyse en trends van leghennenproductie per koppel.",
    display_order=15,
)
```

Bootstrap geeft de eerste admin **viewer** rechten op deze app (analoog aan
de andere twee dashboards in `ADMIN_ROLE_GRANTS`).

### Traefik ForwardAuth

Identiek aan `marimo-klauwgezondheid`:

- `traefik.http.routers.marimo-kippen-dashboard.middlewares=portal-auth`
- `portal-auth` forwardauth gaat naar `http://portal:8000/auth/verify`
- `dashboard_portal/app.py:application_key_for_path` moet de prefix
  `/kippen-dashboard` → `dashboard_kippen` mappen.

Resultaat: een gebruiker zonder `dashboard_kippen` toegang krijgt 403 op het
dashboard, ook al hebben ze wel toegang tot `/kippen` (de registratie-app).

### Route-mapping in `dashboard_portal`

`PATH_APPLICATION_KEYS` in `dashboard_portal/app.py` aanvullen:

```python
("/kippen-dashboard", "dashboard_kippen"),
```

## Files to Touch / Create

- **Nieuw** `dashboard/kippen_dashboard.py` — Marimo notebook.
- **Nieuw** `dashboard/kippen_transforms.py` — pure functies voor afgeleide
  grootheden (FCR, legpercentage, kippenstand, forward-fill eigewicht,
  cumulatieve grootheden, norm-lookup en normalisatie van `breed`).
  Testbaar zonder database. Conform `dashboard/transforms.py`.
- **Nieuw** `tests/dashboard/test_kippen_transforms.py` — pytest, parameter
  cases voor:
  - kippenstand-berekening met meerdere dode-hen events op één dag;
  - legpercentage met 0 of None bird_count;
  - FCR met ontbrekende eigewicht (forward fill, max 14d);
  - leeftijdsweek-berekening conform `kippen_app/flock_age.py`;
  - `breed → breed_key` normalisatie (case, accenten, spaties);
  - cumulatieve berekeningen per opgezette hen.
- **Nieuw** `database/models/laying_hens.py` — nieuwe model
  `FlockLayCurveNorm` (zelfde bestand, want is een Kippen-tabel).
- **Nieuw** `database/repositories/laying_hens_repository.py` —
  `FlockLayCurveNormsRepository` met `list_by_breed_key(key)` en
  `get_by_breed_and_week(key, age_weeks)`.
- **Nieuw** Alembic-migratie `database/migrations/versions/<ts>_<id>_add_flock_lay_curve_norms.py`
  — `CREATE TABLE flock_lay_curve_norms ...`.
- **Nieuw** `database/seeds/dekalb_white_norms.csv` — CSV met de 83 rijen
  uit `dekalb_wit_legkalender.pdf` (leeftijd 18 t/m 100). Eén keer
  handmatig gegenereerd uit de PDF en geversioneerd.
- **Nieuw** `database/seeds/load_lay_curve_norms.py` — idempotent CLI om
  de CSV in te lezen en de tabel te vullen / bij te werken
  (`UPSERT (breed_key, age_weeks)`). Onderdeel van de bootstrap-stap.
- **Wijzig** `shared_auth/bootstrap.py` of een aparte
  `kippen_bootstrap.py` — roept de norm-loader aan na migraties zodat
  een fresh stack meteen de Dekalb-curve heeft.
- **Wijzig** `docker-compose.yml` — service `marimo-kippen-dashboard`,
  poort `2720`, base-url `/kippen-dashboard`, Traefik labels. Plus optioneel
  een `kippen-norms-seed` profile=tools service die de CSV importeert
  (analoog aan `auth-bootstrap`).
- **Wijzig** `docker-compose.local.yml` — analoge override met `http://`
  proxy en de Host-regel met `127.0.0.1`.
- **Wijzig** `shared_auth/bootstrap.py` — nieuwe app
  (`dashboard_kippen`) in `CORE_APPLICATIONS` + `dashboard_kippen:
  ["viewer"]` in `ADMIN_ROLE_GRANTS`.
- **Wijzig** `dashboard_portal/app.py` — `PATH_APPLICATION_KEYS` aanvullen.
- **Wijzig** `README.md` — sectie over het nieuwe dashboard, route,
  bootstrap-instructie, hoe rollen werken voor dit dashboard, en hoe je
  een nieuwe norm-CSV voor een ander ras toevoegt.
- **Geen wijziging** aan `kippen_app/` — registratie-app blijft buiten
  schot. Norms zijn alleen-lezen voor het dashboard.

## Implementation Phases

### Phase 1: Norms tabel en data import

- Voeg `FlockLayCurveNorm` model en `FlockLayCurveNormsRepository` toe.
- Schrijf een Alembic-migratie voor de tabel + indexes + constraints.
- Genereer `database/seeds/dekalb_white_norms.csv` één keer door de PDF
  uit te lezen. Cross-check een paar rijen handmatig tegen de PDF
  (week 33, week 80).
- Schrijf `load_lay_curve_norms.py` met idempotent upsert.
- Test: laad de CSV in een schone SQLite test-database en assert dat
  alle 83 rijen erin staan; assert dat dubbel laden geen duplicaten
  veroorzaakt.
- Doel: de norm-data is beschikbaar voordat we het dashboard openen.

### Phase 2: Transforms en tests

- Schrijf `kippen_transforms.py` met pure Polars/Python functies:
  `calculate_flock_week`, `daily_bird_count`, `daily_lay_percentage`,
  `forward_fill_egg_weight`, `daily_fcr`, `normalize_breed_key`,
  `cumulative_kpis_per_placed_hen`, `join_norms_by_age_week`.
- Schrijf bijbehorende tests met seed-fixtures (geen DB nodig — geef
  rauwe DataFrames door).
- Doel: snel valideren dat de cijfers kloppen voordat we UI bouwen.

### Phase 3: Marimo notebook skeleton

- `dashboard/kippen_dashboard.py` aanmaken met de standaard imports
  (`marimo`, `polars`, `altair`, `connectorx_database_url` boilerplate
  uit `klauwbehandeling_dashboard.py`).
- Eén SQL-query die per geselecteerd huis/koppel:
  - flock metadata ophaalt;
  - alle relevante registraties tussen `placement_date` en `today` ophaalt.
- Filters UI: house dropdown, flock dropdown, date_range, rolling switch.
- KPI-cards bovenin met statische placeholder values.

### Phase 4: Trendgrafieken (werkelijk)

- Implementeer de zes Altair charts uit "UI Layout" met alleen de
  werkelijke meting (nog geen normlijnen).
- Hergebruik `mo.ui.altair_chart` voor consistente styling.
- Per chart: korte `mo.md` samenvatting met gemiddelden uit de selectie.

### Phase 5: Norm-overlay op grafieken

- Voeg een tweede laag toe per chart met de norm uit
  `flock_lay_curve_norms`, op basis van leeftijdsweek (niet datum).
- `mo.ui.switch` "Toon norm" voor aan/uit (default aan).
- Cumulatieve KPI-card (eieren, kg ei, kg voer, cum FCR, leefbaarheid)
  toevoegen boven de trendgrafieken.
- Onder elke trendgrafiek: delta-regel "werkelijk vs norm" voor de huidige
  leeftijdsweek.
- Test: render een koppel met `breed = "Dekalb Wit"` en assert dat de
  normlijn zichtbaar is; render een koppel met onbekend ras en assert dat
  de hint "geen normcurve gevonden" verschijnt.

### Phase 6: Datatabel + CSV download

- Per-dag overzicht met alle berekende kolommen plus de norm-kolommen
  ernaast.
- `mo.download` knop met CSV.

### Phase 7: Portal & deploy

- `shared_auth/bootstrap.py` aanpassen.
- `dashboard_portal/app.py` `PATH_APPLICATION_KEYS` aanpassen.
- `docker-compose.yml` en `docker-compose.local.yml` aanpassen, inclusief
  een `kippen-norms-seed` tools-service voor de CSV-import.
- README bijwerken (route, rollen, hoe een nieuwe norm-CSV toevoegen).
- `auth-bootstrap` + `kippen-norms-seed` lokaal draaien om de nieuwe
  app/rol/norm-seeds te bevestigen.

### Phase 8: Verificatie

- `ruff format` + `ruff check --fix` op alle gewijzigde Python-bestanden.
- `pytest tests/dashboard/test_kippen_transforms.py
  tests/database/test_lay_curve_norms.py`.
- Stack lokaal rebuilden, inloggen als admin → kippen dashboard tile
  zichtbaar → openen → filters werken → grafieken laden zonder errors →
  norm-stippellijn zichtbaar op legpercentage, voer, eigewicht en FCR.
- Inloggen als worker (alleen `kippen` worker rol, géén
  `dashboard_kippen`): tile niet zichtbaar; directe URL → 403.

## Risks and Trade-offs

- **Forward-fill eigewicht.** Een verkeerde keuze hier vervalst de FCR.
  Voorstel om markers te tonen op gemeten dagen helpt de gebruiker
  inschatten hoe vers het cijfer is. Bevestigen met de gebruiker.
- **Dunne datapunten in begin van koppel.** Eerste paar weken na
  plaatsing zijn er nauwelijks eieren — grafieken moeten X-as goed
  configureren (toon vanaf placement_date, niet vanaf 1 januari) anders
  ogen ze leeg.
- **Connector-x leest synchronoon.** Bij grote koppels (jaar lange
  historie) is dat nog steeds milliseconden — geen probleem verwacht. Wel
  een limiet zetten op datumbereik om incidenten te voorkomen.
- **Authorisatie-decoupling.** Iemand die de registratie-app mag bedienen
  hoeft niet automatisch dit dashboard te zien (te veel exposure van
  gevoelige bedrijfsdata). Daarom een aparte `dashboard_kippen` app i.p.v.
  rollen aanhangen aan `kippen`. Volgt het patroon van
  `dashboard_klauwgezondheid` / `dashboard_tank_terminal`.
- **Twee bronnen voor "leeftijd".** `kippen_app/flock_age.py` heeft de
  curve-day-conventie (`elapsed - 1`). Het dashboard moet exact diezelfde
  berekening gebruiken, anders praten Kippen-app en dashboard langs elkaar
  heen. Daarom een testcase die de twee implementaties vergelijkt of de
  Kippen-helper hergebruikt (laatste voorkeur — geen duplicatie).
- **Norm-koppeling op vrij-tekst `breed`.** `flocks.breed` is een vrij
  tekstveld. Een typo betekent dat de koppel geen norm-curve krijgt. We
  normaliseren met een lookup (lowercase, accenten weg, spaties →
  underscores), maar fouten blijven mogelijk. Een herinneringshint in de
  Kippen-app bij het invullen van `breed` zou de match betrouwbaarder
  maken. Niet in v1, wel waard om te overwegen.
- **Norm-data updates.** Fabrikanten kunnen normcurves bijwerken. De CSV
  zit in git en is dus versie-controleerbaar; de loader is idempotent
  (`UPSERT op (breed_key, age_weeks)`) zodat een herhaalde load veilig
  is.
- **Per-aanwezige hen vs per-opgezette hen.** De PDF heeft twee
  invalshoeken; de kolomtypes zijn verschillend. We slaan ze allebei op
  zodat zowel dagelijkse trend (per aanwezige hen) als cumulatieve KPI's
  (per opgezette hen) direct uit één tabel komen.

## Decisions (bevestigd)

- **Eigewicht wordt forward-filled** vanaf de eerste pallet-meting tot
  de eerstvolgende meting, zonder harde cap. Gemeten dagen tonen als
  markers op de FCR- en eigewicht-grafieken. Dagen vóór de eerste
  pallet-meting blijven NULL voor eimassa en FCR.
- Dashboard krijgt een eigen `dashboard_kippen` shared-auth application,
  niet via de `kippen` rollen. Bedrijfsleider krijgt `viewer`-rol;
  `admin` blijft beschikbaar voor toekomstige beheerfuncties.
- Tile-categorie in het portaal: `dashboard` (zelfde groep als
  klauwgezondheid en tanken — geen nieuwe sub-categorieën).
- Start met één huis-/koppel-selectie; geen cross-flock vergelijking in
  v1.
- Gebruik dezelfde leeftijds-conventie als de Kippen-app (curve-day) en
  importeer waar mogelijk uit `kippen_app.flock_age` om duplicatie te
  voorkomen.
- Een nieuwe Marimo container op poort `2720`, base-url
  `/kippen-dashboard`.
- Geen schrijfacties vanuit dit dashboard.
- Nieuwe tabel `flock_lay_curve_norms` met de Dekalb-norm uit
  `dekalb_wit_legkalender.pdf` als CSV-seed onder `breed_key =
  dekalb_white_scharrel_voliere`. Alleen Dekalb in v1; andere rassen
  (Lohmann, Hy-Line) volgen later via dezelfde tabel + extra CSV-seed.
- Norm-lijnen worden als grijze stippellijn over de werkelijke curves
  gelegd; X-as = leeftijdsweek.
- Bij `breed = NULL` of een ras zonder match in
  `flock_lay_curve_norms`: norm-overlay automatisch verbergen, korte
  hint tonen ("geen normcurve gevonden voor ras X"), rest van het
  dashboard blijft werken.
- Pallet- en eigewicht-chart: **dagelijks gemiddelde** als hoofdlijn,
  met de losse pallets als markers (consistent met
  `kippen_app/templates/dashboard.html`).
- Datatabel onderaan: schakelbaar tussen **dagniveau** en **weekniveau**
  via een toggle.
