# Plan: Klauwbehandeling Dashboard

## Doel

Een praktisch Marimo-dashboard bouwen voor de klauwgezondheid van de huidige
actieve koppel. Het dashboard moet vooral snel antwoord geven op vragen rond
Mortellaro:

- hoeveel nieuwe Mortellaro-cases zijn er per behandeldatum;
- welke koeien hebben herhaalde Mortellaro op dezelfde pootpositie;
- welke koeien staan nog open voor opvolging;
- welke cases lijken opgelost na een volgende inspectie;
- welke posities, groepen of lactaties vallen op.

Het dashboard is bedoeld voor gebruik op het bedrijf en moet daarom
Nederlandse labels, korte tabellen en duidelijk voorgesorteerde opvolglijsten
gebruiken.

## Reviewstatus

Dit plan is bijgewerkt op basis van de huidige implementatie in:

- `dashboard/klauwbehandeling_dashboard.py`;
- `dashboard/transforms.py`;
- `tests/dashboard/test_transforms.py`.

De oude versie van dit plan was grotendeels een algemeen startplan. Een deel is
inmiddels al gebouwd, maar er zijn nog placeholders en technische punten die
eerst moeten worden opgeruimd.

## Huidige Stand

### Al aanwezig

- Marimo-dashboard in `dashboard/klauwbehandeling_dashboard.py`.
- Transformmodule in `dashboard/transforms.py`.
- Parsertests in `tests/dashboard/test_transforms.py`.
- Databasequery voor actieve koeien met klauwbehandelingen.
- Koppeling op `klauw_behandelingen.eartag_short = koeien.eartag_short`.
- Filter op `koeien.in_current_herd = true`.
- Filter op `klauw_behandelingen.behandeldatum > koeien.birth_date`.
- Basisfilters voor datum, positie, probleem en zoeken op koe.
- KPI-cards voor het Mortellaro-overzicht.
- Per-koe tab met selectie, profielkaarten, tijdlijn, probleemoverzicht,
  positieoverzicht en vergelijking met koppelgemiddelde.

### Nog onvolledig

- Het algemene overzicht moet boven de tabs komen in plaats van als aparte tab.
- De tabs moeten voorlopig worden beperkt tot `Mortellaro overzicht` en
  `Per koe`.
- De algemene KPI's voor alle klauwbehandelingen moeten nog worden aangescherpt.
- De tab `Herhalingen` is nog placeholder en kan voorlopig vervallen.
- De tab `Posities & groepen` is nog placeholder en kan voorlopig vervallen.
- Een aparte data-kwaliteitstab ontbreekt nog.
- Mortellaro-case tracking, opvolgstatus en de open-Mortellaro tabel zijn
  aanwezig, maar moeten na review door de veearts inhoudelijk worden
  gevalideerd.

## Datadefinities

### Tabellen

`koeien`

- `animal_id`;
- `name`;
- `eartag`;
- `collar_number`;
- `birth_date`;
- `in_current_herd`;
- `created_at`;
- `updated_at`.

`koe_details`

- `animal_id`;
- `lactation_number`;
- `current_dim`;
- `last_calving_date`;
- `feeding_group_name`;
- `barn_group_name`;
- `status`;
- `status_days`;
- `is_young_stock`.

`klauw_behandelingen`

- `id`;
- `eartag_short`;
- `behandeldatum`;
- `notatie`;
- `created_at`;
- `updated_at`.

### Belangrijke dataregels

Klauwbehandelingen hebben geen directe `animal_id`. De waarde uit Klauwscore is
het korte oormerknummer (`eartag_short`), niet het halsbandnummer. Daarom mag
een notitie alleen aan de huidige koe worden gekoppeld wanneer:

```sql
kb.eartag_short = k.eartag_short
AND k.in_current_herd = true
AND kb.behandeldatum > k.birth_date
```

Deze regel is verplicht voor alle dashboardqueries en tests.

## Notatieparser

Het veld `notatie` bevat meestal een positie plus diagnose:

- `Linksachter Mortellaro`;
- `Rechtsvoor Wittelijndefect`;
- `Linksvoor Bont`;
- `Rechtsachter Tyloom`.

Soms is er geen positie:

- `Vierkant`;
- `Bont`.

De parser moet minimaal opleveren:

- `positie_code`: `LV`, `RV`, `LA`, `RA` of `Geen`;
- `positie_volledig`: `Linksvoor`, `Rechtsvoor`, `Linksachter`,
  `Rechtsachter` of `Geen`;
- `zijde`: `Links`, `Rechts` of `None`;
- `poot`: `Voor`, `Achter` of `None`;
- `probleem`;
- `categorie`;
- `is_mortellaro`;
- `is_vierkant`.

De parser moet hoofdletterverschillen en eenvoudige spatiefouten robuust
verwerken. Ondersteun ook de veelgemaakte spelling `Mortelaro` als Mortellaro.

## Mortellaro Case-Definitie

Mortellaro wordt per koe en per pootpositie beoordeeld. Een koe met
`Linksachter Mortellaro` en later `Rechtsachter Mortellaro` heeft dus twee
aparte cases.

Case key:

- `animal_id`;
- `positie_code`.

Alleen Mortellaro-notities met een bekende pootpositie tellen als case. Een
Mortellaro-notitie zonder positie moet zichtbaar blijven als
`Onbekende positie`, maar mag niet stilzwijgend worden samengevoegd met een
andere positie.

Per case:

- eerste Mortellaro-notitie = `nieuwe_case`;
- latere Mortellaro-notities op dezelfde case key = `herhaalde_case`;
- bereken `eerste_datum`;
- bereken `vorige_mortellaro_datum`;
- bereken `dagen_sinds_vorige`;
- bereken `dagen_sinds_eerste`;
- bereken `herhaling_nummer`.

## Opvolgstatus

Een Mortellaro-case blijft open tot er een latere inspectie is waaruit blijkt
dat de pootpositie geen Mortellaro meer heeft.

Statusregels:

- `Actief/herhaald`: op de volgende bezoekdatum staat opnieuw Mortellaro op
  dezelfde pootpositie.
- `Opgelost`: op een latere bezoekdatum staat `Vierkant` en is er op dezelfde
  pootpositie geen Mortellaro-notitie voor die koe.
- `Open/onbekend`: er is nog geen latere bezoekdatum na de laatste
  Mortellaro-notitie.
- `Onzeker`: er is wel een latere inspectie, maar geen duidelijke `Vierkant`
  en ook geen Mortellaro op dezelfde positie.

Het dashboard moet deze statussen apart tonen. `Vierkant` is dus niet alleen
een algemene behandeling, maar ook een mogelijk oplossingssignaal.

## Filters

Filters mogen de case-definitie niet breken. Bereken cases en herhalingen eerst
over de volledige actieve-koppel-historie. Pas daarna filters toe voor
weergave.

Benodigde filters:

- datum van/tot;
- positie;
- probleem;
- alleen Mortellaro;
- alleen actieve/open opvolging;
- minimale herhalingen;
- lactatienummer;
- voergroep;
- stalgroep;
- koe zoeken op naam, halsbandnummer of oormerk;
- onbekende positie tonen/verbergen.

Bij datumfilters moet zichtbaar blijven of een case echt nieuw is of alleen de
eerste zichtbare case binnen de gekozen periode.

## Dashboard Structuur

### Algemeen Overzicht Boven De Tabs

Plaats bovenaan de pagina een algemeen overzicht voor alle klauwbehandelingen
van de actieve koeien op stal. Dit is geen tab, maar een vaste samenvatting die
altijd zichtbaar is voordat de gebruiker naar specifieke analyses gaat.

Belangrijkste KPI's:

- `Actieve koeien`: totaal aantal koeien met `in_current_herd = true`.
- `Koeien met notitie`: aantal actieve koeien met minstens een
  klauwbehandelingsnotitie na geboortedatum.
- `Koeien nog nooit behandeld`: actieve koeien zonder gekoppelde
  klauwbehandelingsnotitie na geboortedatum.
- `Laatste bekapdatum`: meest recente `behandeldatum` in de actieve-koppeldata.
- `Koeien behandeld laatste bezoek`: aantal unieke actieve koeien met een
  notitie op de laatste bekapdatum.
- `Aantal notities laatste bezoek`: totaal aantal notities op de laatste
  bekapdatum.
- `Meest voorkomend probleem`: probleem met de hoogste telling in de
  actieve-koppeldata, exclusief puur administratieve of algemene notities als
  dat later nodig blijkt.
- `Mortellaro open`: aantal actieve koeien met open/onzekere Mortellaro-status,
  als brug naar de Mortellaro-tab.

Aanvullende compacte elementen:

- Top 5 meest voorkomende problemen met aantallen.
- Tabel `Koeien nog nooit behandeld` met minimaal:
  - naam;
  - halsbandnummer;
  - kort oormerk;
  - volledig oormerk;
  - geboortedatum;
  - lactatie;
  - DIM;
  - voergroep/stalgroep waar beschikbaar.

Regels:

- Baseer alle algemene KPI's op actieve koeien en de geldige koppeling:
  `klauw_behandelingen.eartag_short = koeien.eartag_short` en
  `klauw_behandelingen.behandeldatum > koeien.birth_date`.
- Gebruik `notitie` in zichtbare tekst, niet `record`.
- Houd deze bovenste samenvatting compact; details horen in de tabs.

### Tabs Voor Nu

Beperk de tabs voorlopig tot:

1. `Mortellaro overzicht`;
2. `Per koe`.

De eerdere tabs `Herhalingen`, `Locaties`, `Groepen`, `Historie`,
`Alle klauwproblemen` en `Data kwaliteit` blijven ideeën voor later, maar
worden nu niet in de eerste werkbare dashboardstructuur getoond.

### 1. Mortellaro Overzicht

Dit overzicht blijft voorlopig zoals het nu is, zodat de veearts de inhoud kan
reviewen voordat er nieuwe inhoudelijke wijzigingen worden gedaan.

Huidige onderdelen:

- Mortellaro KPI's;
- tabel `Koeien met open Mortellaro`;
- distributie van Mortellaro-notities door de tijd heen op basis van
  `df_behandelingen_parsed`.

Na review door de veearts opnieuw beoordelen:

- of `Vierkant` als oplossingssignaal goed genoeg werkt;
- of open/onzeker/actief-herhaald begrijpelijke statuslabels zijn;
- of extra grafieken of filters echt nodig zijn.

### 2. Per Koe

De bestaande per-koe tab mag blijven, maar moet aansluiten op de nieuwe
Mortellaro-casevelden.

Toon:

- profielkaarten;
- behandelhistorie;
- Mortellaro-cases per positie;
- opvolgstatus per case;
- alle klauwproblemen voor context.

## Implementatiefasen

### Fase 1. Technische Opschoning

1. Verwijder `sys.path` mutation uit `dashboard/klauwbehandeling_dashboard.py`.
2. Zorg dat het dashboard start vanuit de repo-root met:

   ```powershell
   .\.venv\Scripts\python.exe -m marimo edit dashboard\klauwbehandeling_dashboard.py
   .\.venv\Scripts\python.exe -m marimo run dashboard\klauwbehandeling_dashboard.py
   ```

3. Los Marimo duplicate-variable fouten op door iedere cell output een unieke
   naam te geven.
4. Herstel verkeerd gerenderde tekens in zichtbare dashboardtekst.
5. Maak een dependencykeuze:
   - voeg `polars` toe aan de dependencybestanden; of
   - refactor het dashboard terug naar pandas/SQLAlchemy.
6. Run formattering en importchecks.

Acceptatiecriteria:

- Het dashboard start zonder `ModuleNotFoundError`.
- Marimo meldt geen cellen die dezelfde variabelen definieren.
- Zichtbare Nederlandse tekst heeft geen mojibake.
- Dependencies komen overeen met imports.

### Fase 2. Transformlaag Uitbreiden

1. Breid `dashboard/transforms.py` uit met expliciete velden voor
   `is_mortellaro` en `is_vierkant`.
2. Ondersteun `Mortellaro` en `Mortelaro`.
3. Voeg helpers toe voor case keys en positievolgorde.
4. Voeg pure functies toe voor case tracking:
   - `add_mortellaro_case_columns(...)`;
   - `build_mortellaro_followup_status(...)`;
   - naamgeving mag anders, maar verantwoordelijkheden moeten gelijk blijven.
5. Houd functies testbaar zonder database en zonder Marimo.

Acceptatiecriteria:

- Parsertests dekken Mortellaro, Mortelaro, Vierkant en onbekende positie.
- Een koe met LA en later RA telt als twee nieuwe cases.
- Een koe met LA op twee datums telt als een nieuwe case plus herhaling.

### Fase 3. Algemeen Overzicht Boven De Tabs

1. Verplaats de inhoud van de huidige tab `Dashboard overzicht` naar een vaste
   sectie boven de tabs.
2. Vervang placeholdertekst door echte KPI's voor alle klauwbehandelingen van
   actieve koeien op stal.
3. Bouw minimaal deze KPI's:
   - actieve koeien;
   - koeien met notitie;
   - koeien nog nooit behandeld;
   - laatste bekapdatum;
   - koeien behandeld laatste bezoek;
   - aantal notities laatste bezoek;
   - meest voorkomend probleem;
   - open Mortellaro-koeien als verwijzing naar de Mortellaro-tab.
4. Voeg een compacte top-problemen lijst toe:
   - top 5 problemen;
   - aantallen;
   - eventueel percentage van alle notities.
5. Voeg een tabel `Koeien nog nooit behandeld` toe:
   - naam;
   - halsbandnummer;
   - kort oormerk;
   - volledig oormerk;
   - geboortedatum;
   - lactatie/DIM/groep indien beschikbaar.

Acceptatiecriteria:

- De gebruiker ziet bovenaan direct hoe de klauwbehandelingssituatie van de
  actieve koppel ervoor staat.
- De meest voorkomende problemen zijn zichtbaar zonder naar een tab te gaan.
- Koeien zonder klauwbehandelingsnotitie zijn snel te vinden.
- De algemene samenvatting gebruikt alleen actieve koeien en geldige notities
  na geboortedatum.

### Fase 4. Opvolglijst

Status: pauzeren tot na review door de veearts.

Al aanwezig:

- `Koeien met open Mortellaro` toont actieve/open/onzekere opvolging per koe;
- de tabel gebruikt de opvolgstatus uit de case-tracking;
- de tabel toont per koe de open pootposities, eerste en laatste constatering,
  totaal aantal herhalingen en context uit `koe_details`;
- de tabel is voorgesorteerd op aantal open posities, laatste constatering en
  totaal aantal herhalingen.

Niet opnieuw bouwen:

- geen tweede losse `Open opvolglijst Mortellaro` op het
  Mortellaro-overzicht; die overlapt te veel met `Koeien met open Mortellaro`.
- geen inhoudelijke wijziging aan de Mortellaro-statuslogica voordat de
  veearts het huidige overzicht heeft beoordeeld.

Mogelijk later werk, alleen na review:

1. Voeg tabelcontrols toe op de bestaande `Koeien met open Mortellaro` tabel:
   - statusfilter: open/onbekend, actief/herhaald, onzeker;
   - minimale herhalingen;
   - optioneel positie-filter voor `LV`, `RV`, `LA`, `RA`.
2. Maak een aparte, ondergeschikte view of tab voor opgeloste cases:
   - standaard niet bovenaan tonen;
   - wel beschikbaar voor controle en historie.
3. Maak de statuslabels in de tabel explicieter:
   - `Open/onbekend`;
   - `Actief/herhaald`;
   - `Onzeker`;
   - `Opgelost` alleen in de ondergeschikte opgeloste-cases view.
4. Controleer of de sortering praktisch genoeg is; zo niet, sorteer op:
   - actieve/herhaalde cases boven open/onbekend;
   - hoogste aantal herhalingen;
   - langste tijd sinds laatste constatering.

Acceptatiecriteria:

- Het huidige Mortellaro-overzicht blijft stabiel voor de review.
- Na review is duidelijk welke statuslabels, filters of opgeloste-cases view
  echt nodig zijn.

### Fase 5. Per-Koe Analyse Afronden

1. Behoud de bestaande koe-selectie.
4. Toon algemene klauwgeschiedenis ondergeschikt aan Mortellaro.
5. Controleer dat tabellen logisch gesorteerd zijn.

Acceptatiecriteria:

- Een individuele koe is snel terug te vinden.
- De gebruiker ziet per koe direct welke pootpositie aandacht vraagt.

### Fase 6. Locaties En Groepen

Status: uitstellen. Deze tab wordt voorlopig niet getoond.

1. Implementeer positie-heatmap voor de hele koppel.
2. Implementeer probleem x positie matrix.
3. Voeg groepsanalyse toe voor voergroep, stalgroep, lactatie en DIM.
4. Toon aantallen en percentages, zodat grote groepen niet misleidend zijn.

Acceptatiecriteria:

- Positiepatronen zijn zichtbaar zonder handmatig filteren.
- Groepsvergelijkingen tonen aantallen en denominators.

### Fase 7. Alle Klauwproblemen

Status: vervangen door het algemene overzicht boven de tabs.

Voorlopig niet als aparte tab bouwen. De belangrijkste algemene informatie
hoort boven de tabs:

1. top-problemen;
2. algemene KPI's;
3. koeien zonder notitie.

Later eventueel uitbreiden met:

- trends voor alle probleemcategorieen;
- recente notities;
- per-probleem analyse.

Acceptatiecriteria:

- Mortellaro blijft het hoofdverhaal in de eerste tab.
- Algemene klauwinformatie is toch zichtbaar voordat de gebruiker een tab
  opent.

### Fase 8. Data Kwaliteit

Status: uitstellen. Deze tab wordt voorlopig niet getoond.

1. Bouw controles voor unmatched en historische `eartag_short`-data.
2. Toon parserproblemen.
3. Toon dubbele notities.
4. Toon Mortellaro-notities zonder positie apart.

Acceptatiecriteria:

- De gebruiker kan zien waarom aantallen mogelijk afwijken.
- Dataproblemen zijn zichtbaar zonder de hoofdtab te vervuilen.

### Fase 9. Tests En Verificatie

1. Breid `tests/dashboard/test_transforms.py` uit.
2. Voeg tests toe voor case tracking en opvolgstatus.
3. Voeg waar mogelijk kleine fixture-dataframes toe.
4. Run:

   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests\dashboard
   uv run ruff format dashboard tests\dashboard
   uv run ruff check --fix dashboard tests\dashboard
   .\.venv\Scripts\python.exe -m marimo check dashboard\klauwbehandeling_dashboard.py
   ```

Acceptatiecriteria:

- Focused tests slagen.
- Ruff slagen voor aangepaste Python-bestanden.
- Marimo check geeft geen duplicate-definition fouten.

## Open Vragen

- Moet `Vierkant` altijd gelden als opgelost, of alleen wanneer het op een
  reguliere opvolgdatum na Mortellaro komt?
- Welke termijn is praktisch voor urgentie: aantal dagen sinds laatste
  inspectie, aantal bezoeken, of beide?
- Moeten exporten naar CSV of Excel in deze fase, of pas na stabilisatie van de
  dashboardlogica?
- Is melkproductie of DIM belangrijk genoeg om al in de eerste versie mee te
  nemen, of alleen als contextfilter?

## Referenties

- Dashboard: `dashboard/klauwbehandeling_dashboard.py`
- Transforms: `dashboard/transforms.py`
- Tests: `tests/dashboard/test_transforms.py`
- Database models: `database/models/`
- Klauwscore datajob: `data_jobs/klauwscore/`
