# Plan: Uniform-Agri Exporttab Voor Klauwbehandelingen

## Doel

Voeg aan het bestaande `Klauwbehandeling Dashboard` een nieuwe tab
`Uniform-Agri` toe. Deze tab toont een getransformeerde tabel waarmee
klauwbehandelingen gecontroleerd kunnen worden voordat ze als Hoof Supervisor
CSV in Uniform Agri worden geimporteerd.

De tab is bedoeld als controle- en exportweergave:

- laat per klauwbehandeling zien hoe de rij naar Uniform Agri wordt vertaald;
- toon welke rijen exporteerbaar zijn en welke validatiefouten hebben;
- maak het mogelijk om dezelfde gegevens als CSV te downloaden voor import in
  Uniform Agri.

## Bronnen

- Dashboard: `dashboard/klauwbehandeling_dashboard.py`
- Transformfuncties: `dashboard/transforms.py`
- Transformtests: `tests/dashboard/test_transforms.py`
- Klauwbehandelingstabel: `klauw_behandelingen`
- Koeientabel: `koeien`
- Specificatiebestand: `C:\Users\woute\Downloads\Hooftrim.docx`
- Mapping uit aangeleverde afbeelding:
  - pootpositie;
  - hoofzone;
  - conditions;
  - action codes;
  - trim type.

## Uniform Agri CSV-Formaat

Volgens `Hooftrim.docx` verwacht Uniform Agri een CSV-bestand in Hoof
Supervisor-formaat met 4 velden per regel:

```text
animal no.,date,health conditions and location,treatment
```

Voorbeelden uit de specificatie:

```text
41,4.12.17,,
47,4.12.17,D78F78,WT
```

Betekenis:

- veld 1: animal no.;
- veld 2: datum;
- veld 3: health conditions and location;
- veld 4: treatment.

Regels uit de specificatie:

- `animal no.` en `date` zijn verplicht;
- health conditions/location en treatment mogen leeg zijn;
- `animal no.` is de sleutel in Uniform Agri;
- het datumformaat moet overeenkomen met het datumformaat van de PC waarop
  Uniform Agri de import uitvoert;
- voor iedere geimporteerde regel registreert Uniform Agri ook een preventieve
  behandeling/default hoof check.

Voor dit dashboard gebruiken we datumformaat `d.M.yy`; dit is bevestigd als het
juiste formaat voor de Uniform Agri PC waarop wordt geimporteerd. Voorbeeld:
`2026-05-26` wordt `26.5.26`.

## Datagrondslag

Gebruik voor deze tab bij voorkeur `klauw_behandelingen` als primaire bron,
omdat deze tabel inmiddels de directe Uniform Agri-koppeling bevat:

- `klauw_behandelingen.id`;
- `klauw_behandelingen.animal_id`;
- `klauw_behandelingen.eartag`;
- `klauw_behandelingen.eartag_short`;
- `klauw_behandelingen.behandeldatum`;
- `klauw_behandelingen.notatie`;
- `koeien.collar_number`;
- `koeien.name`;
- `koeien.birth_date`.

Queryregel:

```sql
FROM klauw_behandelingen kb
JOIN koeien k
  ON k.animal_id = kb.animal_id
WHERE k.in_current_herd = true
```

Fallback voor oude of niet-gevulde data mag alleen als controlekolom worden
getoond, niet stilzwijgend als exportbasis:

```sql
ltrim(k.eartag_short, '0') = ltrim(kb.eartag_short, '0')
AND kb.behandeldatum > k.birth_date
```

Exporteerbare rijen moeten minimaal hebben:

- `kb.animal_id` gevuld;
- gekoppelde koe met `koeien.in_current_herd = true`;
- `koeien.collar_number` gevuld als werknummer voor `animal no.`;
- `behandeldatum` gevuld;
- een vertaalbare `notatie`.

## Vastgestelde Keuze: Animal No.

De DOCX noemt `animal no.` als sleutel. Voor deze inrichting is vastgesteld dat
dit het werknummer van de koe is: `koeien.collar_number`.

Implementatieregel:

- gebruik `koeien.collar_number` als `animal no.`;
- schrijf `collar_number` als string/integerwaarde naar de CSV;
- toon daarnaast `animal_id`, `eartag`, `eartag_short` en `name` als
  controlekolommen;
- maak `animal_no_source = koeien.collar_number`;
- markeer rijen zonder `collar_number` als niet exporteerbaar.

## Mapping Naar Hoof Supervisor Codes

### Pootpositie

Uniform-code op basis van de positie in onze `notatie`:

| Onze positie | Uniform code |
| --- | ---: |
| Rechtsvoor | 1 |
| Linksvoor | 3 |
| Rechtsachter | 5 |
| Linksachter | 7 |
| Onbekend/geen positie | leeg of validatiefout |

Bron: aangeleverde afbeelding.

### Hoofzone

Er is geen zone-informatie in de huidige klauwbekappernotatie. Daarom:

| Zone | Uniform code |
| --- | ---: |
| Niet bekend | 0 |

Regel:

- zet zone altijd op `0`;
- leg dit expliciet vast in de exportkolom `hoof_zone_code`.

### Conditions

Vertaling van diagnose/probleem naar Uniform condition-code:

| Uniform code | Onze notatie/probleem |
| --- | --- |
| D | Mortellaro |
| I | Tussenklauwontsteking |
| U | Zoolzweer |
| W | Wittelijndefect |
| K | Tyloom |
| F | Stinkpoot |
| H | Bont |
| O | Chronisch bevangen |

Niet gemapte problemen krijgen geen condition-code en worden gemarkeerd met
`validation_status = warning` of `error`, afhankelijk van exportkeuze.

### Action Codes

Vertaling van behandeling/actie naar Uniform action-code:

| Uniform code | Onze notatie/probleem |
| --- | --- |
| W | Verband |
| B | Klos |
| T | Behandeling |

Regel:

- `Verband` geeft action `W`;
- `Klos` geeft action `B`;
- `T` wordt alleen gebruikt als de notatie expliciet als algemene behandeling
  moet worden gemapt;
- een condition zonder action krijgt geen default `T`; het `treatment`-veld
  blijft dan leeg.

### Trim Type

| Uniform code | Onze notatie/probleem |
| --- | --- |
| R | Vierkant |

Regel:

- `Vierkant` is geen condition, maar trim type `R`;
- bij `Vierkant` blijft `health_conditions_location` leeg;
- `Vierkant` wordt in het CSV-veld `treatment` vertaald naar `R`;
- de dashboardcontroletabel toont daarnaast `trim_type_code = R`, zodat
  zichtbaar blijft dat deze treatment-code uit de trimtype-mapping komt.

## Health Conditions And Location Opbouw

Het derde CSV-veld combineert conditions en locatie. Uit de DOCX:

```text
D78F78
```

Interpretatie voor implementatie:

- per condition wordt een blok gemaakt van:
  - condition-code;
  - pootpositie-code;
  - hoofzone-code;
- voorbeeld met Mortellaro op Linksachter:

```text
D70
```

Omdat de aangeleverde afbeelding zegt dat hoofzone onbekend is en alles op `0`
moet, gebruiken we dus altijd zone `0`.

Voor meerdere conditions op dezelfde notatie:

- concateneer conditionblokken zonder separator;
- voorbeeld: Mortellaro en Stinkpoot op Linksachter zou `D70F70` worden.

In de huidige data lijkt iedere `klauw_behandelingen`-rij meestal 1 notatie te
hebben, dus fase 1 ondersteunt 1 condition of 1 action per rij. Multi-condition
kan als latere uitbreiding.

## Treatment Veld Opbouw

Het vierde CSV-veld bevat action codes. Uit de DOCX:

```text
WT
```

Interpretatie:

- concateneer action codes zonder separator;
- `Verband` -> `W`;
- `Klos` -> `B`;
- geen default `T` bij conditions zonder specifieke action;
- `Vierkant` -> `R`.

Voorbeeldrijen:

| Notatie | Health conditions/location | Treatment |
| --- | --- | --- |
| Linksachter Mortellaro | D70 |  |
| Linksachter Verband |  | W |
| Linksachter Klos |  | B |
| Linksachter Wittelijndefect | W70 |  |
| Vierkant |  | R |

Voor `Vierkant` toont de controletabel daarnaast `trim_type_code = R`, en het
CSV-veld `treatment` krijgt dezelfde code `R`.

## Nieuwe Transformfuncties

Voeg pure functies toe aan `dashboard/transforms.py`, of aan een nieuwe module
`dashboard/uniform_agri_transforms.py` als het bestand te groot wordt.

Voorgestelde API:

```python
def parse_uniform_agri_export_row(row: dict[str, object]) -> dict[str, object]:
    ...

def build_uniform_agri_export_rows(
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    ...

def format_uniform_agri_date(value: date) -> str:
    ...
```

Outputvelden voor dashboardcontrole:

- `behandeling_id`;
- `animal_no`;
- `animal_no_source`;
- `date`;
- `health_conditions_location`;
- `treatment`;
- `uniform_position_code`;
- `hoof_zone_code`;
- `condition_code`;
- `action_code`;
- `trim_type_code`;
- `notatie`;
- `eartag`;
- `eartag_short`;
- `cow_name`;
- `validation_status`;
- `validation_message`;
- `exportable`.

Outputvelden voor CSV-download:

```text
animal no.,date,health conditions and location,treatment
```

De CSV wordt met header gedownload.

## Dashboardtab `Uniform-Agri`

### Controls

Plaats bovenaan de tab:

- datumfilter van/tot;
- filter `Alleen exporteerbaar`;
- filter `Alleen waarschuwingen/fouten`;
- zoekveld voor koe, oormerk, kort oormerk of notatie;
- optioneel selectie voor laatste behandeldatum.

De basisdataset bevat alleen klauwbehandelingen van koeien die momenteel
onderdeel zijn van de kudde (`koeien.in_current_herd = true`). Gebruik de
bestaande filterwaarden als dat praktisch is, maar voorkom dat een export per
ongeluk verborgen validatiefouten mist.

### KPI's

Toon boven de tabel:

- aantal rijen in selectie;
- aantal exporteerbaar;
- aantal waarschuwingen;
- aantal fouten;
- aantal zonder gekoppelde koe;
- aantal zonder vertaalbare notatie.

### Tabel

Kolommen in de dashboardtabel:

- `Exporteerbaar`;
- `Status`;
- `Diernummer`;
- `Datum`;
- `Health conditions/location`;
- `Treatment`;
- `Koe`;
- `Oormerk`;
- `Kort oormerk`;
- `Originele notatie`;
- `Positie`;
- `Probleem`;
- `Validatiemelding`.

Sorteer standaard op:

1. `exportable` oplopend, zodat fouten bovenaan staan;
2. `behandeldatum` aflopend;
3. `animal_no`;
4. `notatie`.

### CSV Download

Voeg een downloadactie toe die alleen exporteerbare rijen gebruikt.

Bestandsnaam:

```text
uniform_agri_hooftrim_YYYYMMDD.csv
```

De download moet exact de 4 Uniform Agri-velden bevatten:

```text
animal no.,date,health conditions and location,treatment
```

Plan voor implementatie:

1. bouw de export-DataFrame in Polars;
2. filter op `exportable = true`;
3. selecteer alleen de 4 CSV-kolommen;
4. serialize naar CSV met header;
5. bied download aan via Marimo.

Tijdens implementatie controleren welke Marimo download-API beschikbaar is in
de geinstalleerde versie.

## Validatieregels

Een rij is exporteerbaar als:

- `animal_no` niet leeg is;
- de gekoppelde koe `in_current_herd = true` heeft;
- `collar_number` gevuld is;
- `behandeldatum` niet leeg is;
- minimaal 1 van deze velden gevuld is:
  - `health_conditions_location`;
  - `treatment`;
  - `trim_type_code`;
- de notatie herkenbaar is of expliciet als `Vierkant` is verwerkt.

Niet exporteerbaar:

- geen gekoppelde koe;
- gekoppelde koe is niet onderdeel van de huidige kudde;
- geen `collar_number` voor `animal no.`;
- onbekende probleemnotatie;
- positie vereist maar ontbreekt bij condition;
- datum ontbreekt.

Warnings:

- notatie zonder positie waarbij export toch mogelijk is;
- meerdere codes uit 1 notatie als dat later wordt ondersteund.

## Tests

Breid `tests/dashboard/test_transforms.py` uit met tests voor:

- `format_uniform_agri_date(date(2026, 5, 26)) == "26.5.26"`;
- `Linksachter Mortellaro` -> condition `D`, positie `7`, zone `0`,
  health field `D70`;
- `Rechtsvoor Wittelijndefect` -> `W10`;
- `Linksvoor Zoolzweer` -> `U30`;
- `Rechtsachter Tyloom` -> `K50`;
- `Linksachter Verband` -> treatment `W`;
- `Linksachter Klos` -> treatment `B`;
- `Linksachter Mortellaro` heeft geen default treatment `T`;
- `Vierkant` -> trim type `R` en treatment `R`;
- onbekende notatie geeft `exportable = false`;
- rij zonder gekoppelde koe geeft `exportable = false`;
- rij zonder `collar_number` geeft `exportable = false`;
- rij van koe buiten huidige kudde komt niet in de exportdataset;
- CSV-selectie bevat alleen de vier exportkolommen met header.

## Implementatiefasen

### Fase 1. Transformlaag

1. Maak mappingconstanten voor positie, hoofzone, conditions, actions en trim
   type.
2. Voeg pure transformfuncties toe.
3. Voeg tests toe voor alle mappings uit de afbeelding.
4. Houd de bestaande Mortellaro-transforms stabiel.

Acceptatiecriteria:

- alle nieuwe transformtests slagen;
- onbekende notaties worden zichtbaar als fout, niet stilzwijgend leeg.

### Fase 2. Dataquery

1. Maak een aparte query/cell voor Uniform-Agri exportdata.
2. Gebruik `kb.animal_id` als primaire koppeling naar `koeien`.
3. Filter op `koeien.in_current_herd = true`, zodat alleen koeien die momenteel
   onderdeel zijn van de kudde in de exportdataset zitten.
4. Gebruik `koeien.collar_number` als `animal no.`.
5. Toon records zonder `animal_id` of zonder `collar_number` alleen in een
   validatie-overzicht, niet in de exportdataset.

Acceptatiecriteria:

- de tab kan ook oude/onvolledige records tonen;
- de gebruiker ziet waarom een rij niet exporteerbaar is.
- de exportdataset bevat alleen huidige-kudde-koeien.

### Fase 3. Dashboardtab

1. Voeg `Uniform-Agri` toe aan de bestaande `mo.ui.tabs`.
2. Bouw KPI's, filters en tabel.
3. Voeg CSV-download toe voor exporteerbare rijen.

Acceptatiecriteria:

- de tabel is scanbaar en toont de vier uiteindelijke CSV-velden;
- fouten staan bovenaan of zijn eenvoudig te filteren;
- de CSV-download bevat alleen exporteerbare rijen.

### Fase 4. Proefimport En Correcties

1. Download CSV voor een kleine datumselectie.
2. Importeer in Uniform Agri.
3. Controleer:
   - `animal no.` (`koeien.collar_number`) matcht de juiste koe;
   - condition/location wordt goed gelezen;
   - treatment codes worden juist vertaald;
   - `Vierkant` wordt als treatment `R` geimporteerd.
4. Pas mapping alleen aan als de proefimport aantoont dat Uniform Agri `R`
   anders verwacht.

Acceptatiecriteria:

- proefimport geeft geen rode regels in Uniform Agri;
- geimporteerde gebeurtenissen staan op de juiste koeien;
- de labels in Uniform Agri komen overeen met de mapping.

## Open Vragen Voor Review

Deze keuzes zijn vastgesteld:

- `animal no.` is het werknummer: `koeien.collar_number`;
- een condition zonder action krijgt geen default treatment `T`;
- `Vierkant` wordt vertaald naar treatment `R`;
- CSV wordt met header gedownload;
- datumformaat is `d.M.yy`;
- export bevat alleen klauwbehandelingen van koeien die momenteel onderdeel
  zijn van de kudde.

Nog te valideren in een proefimport:

- of Uniform Agri `R` als treatment-code voor `Vierkant` correct verwerkt;
- of `collar_number` exact overeenkomt met de sleutel die Uniform Agri in de
  importwizard verwacht.
