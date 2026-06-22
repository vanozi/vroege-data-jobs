# Moneybird Dashboard Plan

## Doel

Het Moneybird dashboard verder uitbouwen tot een read-only boekhoudkundig dashboard
dat lokale databasegegevens inzichtelijk maakt zonder Moneybird API-token in de
dashboard runtime.

## Uitgangspunten

- Dashboard runtime gebruikt alleen `DATABASE_URL`.
- De Moneybird API wordt alleen door de datajob gebruikt.
- Het dashboard blijft read-only.
- Data komt uit de lokale tabellen:
  - `moneybird_sales_invoices`
  - `moneybird_purchase_invoices`
  - `moneybird_contacts`
  - `moneybird_ledger_accounts`
  - `moneybird_financial_accounts`
  - `moneybird_financial_mutations`
  - `moneybird_report_snapshots`
- Facturen moeten contactnamen kunnen tonen via `moneybird_contacts`.
- Profit/loss account ids moeten naar grootboekrekeningnamen kunnen worden gemapt
  zodra daarvoor detaildata beschikbaar is.

## Fase 1: Basisindeling Aanscherpen

### Werk

- Bovenaan compacte filters houden:
  - periode
  - datum van/tot
  - verkoopstatus
  - inkoopstatus
- Tabs structureren:
  - `Overzicht`
  - `Verkoop`
  - `Inkoop`
  - `Bank`
  - `Rapporten`
  - `Datakwaliteit`
- Bedragen consequent formatteren als EUR.
- Statuswaarden vertalen naar duidelijke labels waar nodig.

### Acceptatiecriteria

- Dashboard opent zonder Moneybird token.
- Alle tabs laden zonder API-calls.
- Filters zijn bruikbaar en breken niet bij lege datasets.

## Fase 2: KPI's

### Werk

- KPI cards toevoegen of verfijnen:
  - omzet
  - kosten
  - bruto marge
  - operationeel resultaat
  - netto resultaat
  - open debiteuren
  - open crediteuren
  - verlopen verkoopfacturen
  - verlopen inkoopfacturen
  - laatste synchronisatie per dataset
- KPI's baseren op gefilterde data waar dat logisch is.
- Rapport-KPI's baseren op de gekozen rapportperiode.

### Acceptatiecriteria

- KPI's tonen `EUR 0,00` of `0` bij lege datasets.
- Open debiteuren en crediteuren zijn direct zichtbaar.
- Laatste sync is zichtbaar per belangrijke dataset.

## Fase 3: Verkoopfacturen

### Werk

- Verkoopfacturentabel uitbreiden met:
  - factuurdatum
  - factuurnummer
  - contactnaam
  - status
  - vervaldatum
  - betaaldatum
  - totaal incl. btw
  - betaald
  - open bedrag
  - herinneringen
- Openstaande facturen apart tonen.
- Verlopen facturen markeren of apart samenvatten.
- Omzetgrafiek per maand toevoegen.
- Filter op contactnaam toevoegen als dat praktisch blijft.

### Acceptatiecriteria

- Contactnamen komen uit de lokale contacts-tabel waar beschikbaar.
- Openstaande en verlopen verkoopfacturen zijn snel te vinden.
- Tabel blijft bruikbaar bij honderden of duizenden facturen.

## Fase 4: Inkoopfacturen

### Werk

- Inkoopfacturentabel uitbreiden met:
  - datum
  - boekstuk
  - referentie
  - leverancier/contactnaam
  - status
  - vervaldatum
  - betaaldatum
  - totaal incl. btw
  - totaal basisvaluta
- Openstaande inkoopfacturen apart tonen.
- Verlopen inkoopfacturen markeren of apart samenvatten.
- Kostengrafiek per maand toevoegen.
- Filter op leverancier toevoegen als dat praktisch blijft.

### Acceptatiecriteria

- Leveranciersnamen komen uit de lokale contacts-tabel waar beschikbaar.
- Open crediteuren zijn betrouwbaar zichtbaar.
- Inkoopkosten per maand zijn scanbaar.

## Fase 5: Banktab

### Werk

- Financiele rekeningen tonen:
  - naam
  - type
  - identifier
  - valuta
  - provider
  - actief
- Bankmutaties tonen:
  - datum
  - rekening
  - bedrag
  - open bedrag
  - tegenrekening naam
  - tegenrekening nummer
  - omschrijving
  - status
  - afletterstatus
- Filters toevoegen:
  - rekening
  - status
  - datum van/tot
- Grafiek toevoegen:
  - inkomend/uitgaand per maand
  - eventueel per rekening
- Niet-verwerkte of open mutaties samenvatten.

### Acceptatiecriteria

- Bank tab data is volledig lokaal beschikbaar.
- Bankmutaties zijn per rekening te filteren.
- Open/niet-verwerkte mutaties zijn zichtbaar.

## Fase 6: Rapporten En Grootboek

### Werk

- Profit/loss snapshot tonen als compacte rapportkaart.
- Balance sheet snapshot bruikbaar tonen.
- Grootboekrekeningen als lookup-tabel tonen.
- Zodra rapport-detailregels beschikbaar zijn:
  - account ids mappen naar grootboekrekeningnamen
  - omzet/kosten per grootboekrekening tonen
  - top kostenrekeningen tonen

### Acceptatiecriteria

- Rapporten tab geeft snel inzicht in resultaat en balans.
- Grootboekrekening lookup is beschikbaar.
- Account-id mapping is voorbereid zonder API-call in dashboard.

## Fase 7: Datakwaliteit

### Werk

- Controleblokken toevoegen voor:
  - facturen zonder contactnaam
  - facturen met contact_id zonder lokaal contact
  - bankmutaties zonder financiele rekeningnaam
  - lege rapport snapshots
  - laatste sync per tabel
- Waarschuwingen als callouts tonen.

### Acceptatiecriteria

- Problemen in lokale data zijn zichtbaar.
- Gebruiker kan zien welke data mogelijk ontbreekt voordat conclusies worden getrokken.

## Fase 8: Technische Opschoning

### Werk

- Helperfuncties voor:
  - EUR-formattering
  - open/verlopen status
  - maandaggregaties
  - sync-status
- Overweeg een aparte module `dashboard/moneybird_transforms.py` wanneer
  `moneybird_dashboard.py` te groot wordt.
- Tests toevoegen voor helperfuncties.

### Acceptatiecriteria

- Dashboardbestand blijft leesbaar.
- Kernberekeningen zijn getest.
- Geen Moneybird API-client of Moneybird config import in dashboard runtime.

## Aanbevolen Implementatievolgorde

1. KPI's en sync-status verbeteren.
2. Verkoop- en inkoopfactuurdetails verfijnen.
3. Banktab uitbreiden met filters en grafieken.
4. Rapporten en grootboekweergave uitbreiden.
5. Datakwaliteitstab toevoegen.
6. Helperfuncties en tests opschonen.
