# Plan: Klauwbekapprotocol Dashboard Tab

## Doel

Voeg een nieuwe dashboardtab toe aan het Klauwbehandeling dashboard die koeien
indeelt volgens het klauwbekapprotocol. De tab moet een praktische
aanbiedlijst geven voor de klauwbekapper, met duidelijke redenen waarom een koe
wel of niet aangeboden moet worden.

De eerste versie moet vooral beslissingen ondersteunen met de data die nu al in
de database staat. Dat betekent:

- klauwbehandelingen uit `klauw_behandelingen`;
- actieve koeien uit `koeien`;
- lactatie-, DIM-, status- en groepsinformatie uit `koe_details`.

Kreupele koeien uit WhatsApp vallen buiten deze versie. Er wordt nu geen
handmatige kreupelregistratie gebouwd.

## Protocolregels

### Altijd aanbieden

Een koe moet altijd aangeboden worden wanneer:

- zij actieve Mortellaro heeft: er is een Mortellaro-notatie geweest en er is
  daarna geen latere bekapdatum geweest waarop geen Mortellaro meer is
  geconstateerd;
- zij een aandoening had en na 12 weken opnieuw beoordeeld moet worden.

Mortellaro is altijd direct opnieuw aanbieden. Andere aandoeningen worden pas
na 12 weken opnieuw aangeboden.

### Preventief aanbieden

Een koe mag preventief aangeboden worden wanneer:

- de laatste bekapdatum alleen de notitie `Vierkant` had;
- er minimaal 6 maanden zijn verstreken sinds de laatste behandeling;
- de koe niet droog staat;
- de koe minimaal 30 dagen in lactatie is;
- er geen actieve indicatie is.

### Tijdelijk niet aanbieden

Een koe wordt tijdelijk niet preventief aangeboden wanneer:

- zij droog staat;
- zij minder dan 30 dagen in lactatie is;
- zij nog niet voldoet aan de termijn voor preventief bekappen.

Bij actieve Mortellaro vervallen deze uitzonderingen.
Bij een andere actieve aandoening vervallen deze uitzonderingen ook; die koe
volgt het hercontroletraject van 12 weken.

## Notatiegroepen

### Aandoeningen

Deze notaties zijn aandoeningen:

- `Mortellaro`;
- `Tussenklauwontsteking`;
- `Zoolzweer`;
- `Wittelijndefect`;
- `Tyloom`;
- `Stinkpoot`;
- `Bont`;
- `Chronisch bevangen`.

### Behandelingen

Deze notaties zijn behandelingen:

- `Verband`;
- `Klos`;
- `Vierkant`.

`Vierkant` betekent: vierkant bekapt / preventief behandeld. Voor
protocolstatus telt `Vierkant` alleen als gezonde of preventieve registratie
wanneer op die bekapdatum geen aandoening is geconstateerd.

## Beschikbare Data

### `koeien`

Benodigde velden:

- `animal_id`;
- `name`;
- `collar_number`;
- `eartag`;
- `eartag_short`;
- `birth_date`;
- `in_current_herd`.

### `koe_details`

Benodigde velden:

- `animal_id`;
- `current_dim`;
- `lactation_number`;
- `feeding_group_number`;
- `feeding_group_name`;
- `barn_group_name`;
- `status`;
- `status_days`;
- `is_young_stock`.

Droogstand wordt afgeleid uit `koe_details.status = 'Droog'`.
`status_days` geeft aan hoeveel dagen de koe in die status zit.

### `klauw_behandelingen`

Benodigde velden:

- `id`;
- `animal_id` wanneer beschikbaar;
- `eartag_short`;
- `behandeldatum`;
- `notatie`.

Koppeling moet aansluiten op de bestaande dashboardregel:

```sql
kb.eartag_short = k.eartag_short
AND kb.behandeldatum > k.birth_date
AND k.in_current_herd = true
```

Als `klauw_behandelingen.animal_id` beschikbaar en betrouwbaar gevuld is, kan
die later als primaire koppeling worden gebruikt. Tot die tijd blijft
`eartag_short` leidend.

## Datagaten En Assumpties

### Kreupele koeien

Kreupele koeien worden in deze versie niet meegenomen. Handmatige invoer,
opslag en afsluiten van kreupelmeldingen blijven buiten scope.

### Preventief bekappen

Alleen `Vierkant` telt als preventief/gezond afgerond. Dit geldt alleen
wanneer `Vierkant` de enige notatie op de bekapdatum is, of wanneer er op
diezelfde datum in elk geval geen aandoening is geconstateerd.

Voorbeelden:

- `2026-04-21: Vierkant` = gezond/preventief afgerond.
- `2026-04-21: Vierkant + Mortellaro` = actieve Mortellaro, niet gezond.
- `2026-04-21: Vierkant + Zoolzweer` = aandoening, hercontrole na 12 weken.
- `2026-04-21: Vierkant + Verband` = geen aandoening; behandel dit voorlopig
  als gezond/preventief, tenzij later anders besloten wordt.

### Droogstand

Droogstand wordt afgeleid uit `koe_details.status`.

Plan:

1. Maak een kleine helper `is_droogstaand(row)`.
2. Laat alleen statuswaarde `Droog` als droogstand tellen.
3. Gebruik `status_days` als contextkolom in de dashboardtab.
4. Test status `Droog` en een niet-droge status.

## Nieuwe Transformlaag

Voeg pure functies toe aan `dashboard/transforms.py`, zodat de protocolregels
testbaar zijn zonder Marimo en zonder database.

### Nieuwe datavelden

Elke koe krijgt protocolvelden:

- `peildatum`;
- `laatste_klauwdatum`;
- `laatste_klauwnotities`;
- `laatste_mortellaro_datum`;
- `laatste_aandoening_datum`;
- `laatste_gezond_datum`;
- `dagen_sinds_laatste_klauwbehandeling`;
- `dagen_sinds_laatste_aandoening`;
- `is_droogstaand`;
- `is_eerste_30_dim`;
- `heeft_actieve_mortellaro`;
- `heeft_actieve_aandoening`;
- `moet_aangeboden_worden`;
- `aanbiedcategorie`;
- `aanbiedreden`;
- `urgentie_sort_key`;
- `volgende_actiedatum`.

### Aanbiedcategorieen

Gebruik vaste categorieen voor sortering en filtering:

1. `Actieve Mortellaro`
2. `Hercontrole aandoening`
3. `Preventief bekappen`
4. `Tijdelijk niet aanbieden`
5. `Geen actie`
6. `Onvoldoende data`

### Kernfunctie

Maak een functie:

```python
def build_klauwbekap_protocol_rows(
    rows: list[dict[str, object]],
    *,
    reference_date: Optional[date] = None,
) -> list[dict[str, object]]:
    ...
```

Input:

- een lijst dashboardrijen waarin koegegevens en klauwbehandelingen al
  gekoppeld zijn;
- optioneel een peildatum voor tests en dashboardberekeningen.

Als `reference_date` niet wordt meegegeven, gebruikt de functie de datum van
vandaag. In de dashboardtab wordt deze peildatum door de gebruiker aangepast
via een datumveld.

De peildatum is de datum waarop de beslissing wordt berekend. Dit kan een datum
in de toekomst zijn, bijvoorbeeld de geplande datum waarop de klauwbekapper
komt. Daardoor kan de lijst enkele dagen vooraf worden gemaakt op basis van de
werkelijke bekapdatum.

Output:

- een rij per actieve koe;
- met protocolbeslissing en dashboardkolommen.

## Beslislogica

### Stap 1. Groepeer per koe

Groepeer op `animal_id`. Gebruik alleen actieve koeien en geldige
behandelingen na geboortedatum.

### Stap 2. Parse notaties

Gebruik de bestaande `parse_notatie(...)`.

Benodigde signalen:

- `is_mortellaro`;
- `is_vierkant`;
- `is_aandoening`;
- `is_behandeling`;
- aandoening = een notatie uit de vaste aandoeningenlijst;
- behandeling = een notatie uit de vaste behandelingenlijst.

### Stap 3. Bepaal laatste toestand

Per koe:

- sorteer alle behandelingen op `behandeldatum`;
- groepeer notities per bekapdatum;
- bepaal per bekapdatum:
  - heeft Mortellaro;
  - heeft andere aandoening;
  - heeft aandoening;
  - heeft Vierkant;
  - is zuivere Vierkant-datum;
- bepaal de laatste bekapdatum;
- bepaal de laatste bekapdatum met aandoening;
- bepaal de laatste zuivere Vierkant-datum.

### Stap 4. Actieve Mortellaro

Een koe heeft actieve Mortellaro wanneer:

- er een Mortellaro-notatie is geweest;
- en er na de laatste Mortellaro-datum geen latere bekapdatum is geweest waarop
  geen Mortellaro meer is geconstateerd.

Belangrijk:

- Een latere bekapdatum met `Vierkant` en een andere aandoening sluit
  Mortellaro af, zolang op die latere datum geen Mortellaro staat.
- Die andere aandoening start daarna wel een eigen hercontroletraject van
  12 weken.
- Als op de latere datum opnieuw Mortellaro staat, blijft Mortellaro actief en
  moet de koe direct opnieuw worden aangeboden.

Resultaat:

- `aanbiedcategorie = Actieve Mortellaro`;
- `moet_aangeboden_worden = True`;
- `volgende_actiedatum = reference_date`;
- droogstand en DIM-regels blokkeren dit niet.

### Stap 5. Hercontrole aandoening

Een koe moet voor hercontrole aangeboden worden wanneer:

- de laatste open aandoening geen Mortellaro is;
- er na die aandoening geen latere bekapdatum zonder aandoening is geweest;
- er minimaal 12 weken zijn verstreken sinds de laatste aandoeningsdatum.

Resultaat:

- `aanbiedcategorie = Hercontrole aandoening`;
- `moet_aangeboden_worden = True`;
- `volgende_actiedatum = laatste_aandoening_datum + 84 dagen`.

Als de 12 weken nog niet voorbij zijn:

- `aanbiedcategorie = Tijdelijk niet aanbieden`;
- `moet_aangeboden_worden = False`;
- `aanbiedreden = Hercontrole vanaf <datum>`.

### Stap 6. Preventief bekappen

Een koe moet preventief aangeboden worden wanneer:

- de laatste bekapdatum een zuivere Vierkant-datum was;
- er minimaal 6 maanden zijn verstreken sinds die laatste gezonde behandeling;
- de koe niet droog staat;
- `current_dim >= 30`;
- er geen actieve aandoening is.

Voor de eerste versie mag 6 maanden technisch worden benaderd als 183 dagen.
Als later kalendermaanden belangrijk zijn, gebruik `dateutil.relativedelta`.

Resultaat:

- `aanbiedcategorie = Preventief bekappen`;
- `moet_aangeboden_worden = True`;
- `volgende_actiedatum = laatste_gezond_datum + 183 dagen`.

### Stap 7. Tijdelijk niet aanbieden

Een koe wordt tijdelijk niet preventief aangeboden wanneer:

- zij droog staat;
- of `current_dim < 30`;
- of de preventieve termijn nog niet verstreken is.

Resultaat:

- `aanbiedcategorie = Tijdelijk niet aanbieden`;
- `moet_aangeboden_worden = False`;
- `aanbiedreden` beschrijft de blokkade.

### Stap 8. Onvoldoende data

Wanneer een koe geen klauwbehandeling heeft of noodzakelijke context mist:

- toon de koe in een aparte controlelijst;
- geef duidelijk aan welke data mist.

Koeien zonder klauwdata mogen automatisch preventief gepland worden wanneer:

- de koe geen jongvee is;
- de koe niet droog staat;
- `current_dim >= 30`.

Koeien zonder klauwdata blijven in datacontrole wanneer:

- `is_young_stock = true`;
- `current_dim` mist;
- statusinformatie mist of onduidelijk is.

## Dashboardtab

Voeg een nieuwe tab toe, bijvoorbeeld `Protocol`.

### Peildatum

Plaats bovenaan de protocoltab een datumveld:

- label: `Peildatum / datum klauwbekapper`;
- standaardwaarde: vandaag;
- de gebruiker mag een toekomstige datum kiezen.

Alle termijnberekeningen gebruiken deze peildatum:

- 12 weken hercontrole;
- 183 dagen preventief bekappen;
- DIM- en droogstandregels voor preventief aanbieden;
- dagen sinds laatste behandeling.

De gekozen peildatum moet zichtbaar blijven bij de tabellen, zodat duidelijk is
waarop de aanbiedlijst gebaseerd is.

### Bovenste KPI's

Toon compacte KPI's:

- `Nu aanbieden`: aantal koeien met `moet_aangeboden_worden = True`;
- `Actieve Mortellaro`;
- `Hercontrole aandoening`;
- `Preventief bekappen`;
- `Tijdelijk niet aanbieden`;
- `Onvoldoende data`.

### Hoofdtabel: Aanbiedlijst

Tabel `Aanbiedlijst klauwbekapper`.

Alleen koeien met `moet_aangeboden_worden = True`.

Kolommen:

- `Aanbiedcategorie`;
- `Aanbiedreden`;
- `Koe / naam`;
- `Halsbandnummer`;
- `Oormerk kort`;
- `Oormerk`;
- `Laatste klauwdatum`;
- `Laatste notatie(s)`;
- `Dagen sinds laatste behandeling`;
- `Volgende actiedatum`;
- `DIM`;
- `Lactatie`;
- `Voergroep`;
- `Status`.

Sortering:

1. actieve Mortellaro;
2. hercontrole aandoening;
3. preventief bekappen;
4. oudste overschrijding bovenaan;
5. halsbandnummer.

### Tweede tabel: Binnenkort / tijdelijk niet

Tabel `Nog niet aanbieden`.

Kolommen:

- `Aanbiedcategorie`;
- `Aanbiedreden`;
- `Koe / naam`;
- `Halsbandnummer`;
- `Laatste klauwdatum`;
- `Volgende actiedatum`;
- `DIM`;
- `Voergroep`;
- `Status`.

Gebruik deze tabel voor koeien die wel relevant zijn, maar nog niet aan de
termijn voldoen of tijdelijk geblokkeerd zijn door droogstand of eerste 30 DIM.

### Derde tabel: Datacontrole

Tabel `Onvoldoende data`.

Kolommen:

- `Koe / naam`;
- `Halsbandnummer`;
- `Oormerk kort`;
- `Oormerk`;
- `Missende data`;
- `Laatste bekende klauwdatum`;
- `Voergroep`;
- `Status`.

## Filters

Minimale filters:

- categorie;
- voergroep;
- lactatie;
- status;
- zoeken op naam, halsbandnummer, oormerk of kort oormerk.

Optioneel later:

- alleen overschrijdingen ouder dan X dagen;
- alleen vaarzen;
- alleen koeien met onbekende data.

## Implementatiefasen

### Fase 1. Dataverkenning

1. Inventariseer echte waarden in `koe_details.status`.
2. Bevestig vaste gezonde notaties:
   - `Vierkant`;
3. Bevestig vaste aandoeningsnotaties:
   - `Mortellaro`;
   - `Tussenklauwontsteking`;
   - `Zoolzweer`;
   - `Wittelijndefect`;
   - `Tyloom`;
   - `Stinkpoot`;
   - `Bont`;
   - `Chronisch bevangen`.
4. Bevestig vaste behandelingsnotaties:
   - `Verband`;
   - `Klos`;
   - `Vierkant`.
5. Controleer of `klauw_behandelingen.animal_id` beschikbaar en gevuld is in de
   productieomgeving.

Acceptatiecriteria:

- Droogstandstatus `Droog` is vastgelegd.
- `Vierkant` is vastgelegd als enige preventief/gezonde notatie.
- De koppeling voor klauwbehandelingen is inhoudelijk bevestigd.

### Fase 2. Transformfuncties

1. Breid `parse_notatie(...)` uit met aandoening- en behandelingsclassificatie.
2. Voeg helpers toe:
   - `is_zuivere_vierkant_datum(...)`;
   - `is_aandoening(...)`;
   - `is_mortellaro_datum(...)`;
   - `has_aandoening_datum(...)`;
   - `is_droogstaand(...)`;
   - `add_days(...)` of datumhelpers.
3. Bouw `build_klauwbekap_protocol_rows(...)`.
4. Zorg dat de functie geen Marimo- of databaseafhankelijkheid heeft.

Acceptatiecriteria:

- Functie geeft precies een rij per actieve koe.
- Alle categorieen zijn deterministisch.
- Peildatum is testbaar via `reference_date`.

### Fase 3. Tests

Voeg tests toe aan `tests/dashboard/test_transforms.py`.

Testcases:

- standaard peildatum is vandaag wanneer geen `reference_date` is meegegeven;
- gebruiker kan een toekomstige peildatum gebruiken waardoor koeien alvast op
  de aanbiedlijst komen;
- actieve Mortellaro blijft aanbieden ondanks droogstand of lage DIM;
- Mortellaro gevolgd door latere `Vierkant` is niet actief;
- Mortellaro gevolgd door latere `Vierkant + Zoolzweer` sluit Mortellaro,
  maar start hercontrole voor Zoolzweer;
- Mortellaro gevolgd door latere `Vierkant + Mortellaro` blijft actieve
  Mortellaro;
- andere aandoening wordt na 12 weken aangeboden;
- andere aandoening binnen 12 weken wordt nog niet aangeboden;
- zuivere `Vierkant` ouder dan 6 maanden wordt preventief aangeboden;
- `Vierkant` jonger dan 6 maanden wordt nog niet aangeboden;
- `Vierkant + aandoening` wordt niet preventief aangeboden;
- droogstaande koe wordt niet preventief aangeboden;
- koe met `current_dim < 30` wordt niet preventief aangeboden;
- koe zonder klauwdata wordt preventief aangeboden vanaf 30 DIM wanneer zij geen
  jongvee is;
- jongvee zonder klauwdata komt niet op de preventieve aanbiedlijst;
- status `Droog` blokkeert alleen preventief bekappen, niet actieve
  aandoeningen.

Acceptatiecriteria:

- Focused tests slagen.
- Randgevallen rond 84 dagen, 183 dagen en 30 DIM zijn afgedekt.

### Fase 4. Dashboardtab

1. Voeg cell toe die protocolrijen bouwt vanuit `df_behandelingen_parsed` en
   actieve koeien zonder behandeling.
2. Voeg een `mo.ui.date` toe voor `Peildatum / datum klauwbekapper`, standaard
   gevuld met vandaag.
3. Geef deze datum door aan `build_klauwbekap_protocol_rows(...,
   reference_date=...)`.
4. Voeg tab `Protocol` toe aan `mo.ui.tabs`.
5. Bouw KPI's.
6. Bouw hoofdtabel `Aanbiedlijst klauwbekapper`.
7. Bouw tabel `Nog niet aanbieden`.
8. Bouw tabel `Onvoldoende data`.
9. Voeg filters toe.

Acceptatiecriteria:

- Tab opent zonder errors.
- Peildatum staat standaard op vandaag en kan naar een toekomstige datum gezet
  worden.
- Aanbiedlijst toont alleen koeien die nu aangeboden moeten worden.
- Reden per koe is direct leesbaar.
- Droogstand/DIM blokkeren preventief bekappen maar niet actieve aandoeningen.

### Fase 5. Validatie Met Bedrijf

1. Vergelijk dashboardlijst met de huidige handmatige werkwijze.
2. Controleer minimaal 10 koeien uit elke categorie.
3. Leg afwijkingen vast:
   - verkeerde statusinterpretatie;
   - notaties die parser nog niet kent;
   - onduidelijke preventieve termen.
4. Pas regels alleen aan met expliciete beslissing.

Acceptatiecriteria:

- De lijst is inhoudelijk bruikbaar voor de volgende klauwbekapperronde.
- Bekende beperkingen staan zichtbaar in het dashboard of in documentatie.

## Technische Aandachtspunten

- Bereken protocolstatus altijd over de volledige behandelgeschiedenis, niet
  over de gefilterde dashboardweergave.
- Houd de transformfuncties klein en puur.
- Gebruik `Optional[type]`, geen `type | None`.
- Gebruik `pathlib.Path` wanneer er paden nodig zijn.
- Voeg tests toe voordat de dashboardtab op de transformlogica leunt.
- Run na Python-wijzigingen:

```powershell
.\.venv\Scripts\python.exe -m ruff format dashboard\klauwbehandeling_dashboard.py dashboard\transforms.py tests\dashboard\test_transforms.py
.\.venv\Scripts\python.exe -m ruff check --fix dashboard\klauwbehandeling_dashboard.py dashboard\transforms.py tests\dashboard\test_transforms.py
.\.venv\Scripts\python.exe -m pytest tests\dashboard\test_transforms.py
```

## Buiten Scope Voor Deze Versie

- Handmatige invoer van kreupele koeien.
- Opslag van kreupelmeldingen in een eigen tabel.
- Automatisch of handmatig sluiten van kreupelmeldingen.
