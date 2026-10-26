# Bokföring

Tillägget Bokföring för organisationens bokföring i Metra: dubbel
bokföring med numrerade verifikat och kvitton, enligt den finska
bokföringslagen. En administratör slår på det under Inställningar >
Tillägg. Kassören för bokföringen; styrelsen och den skrivskyddade rollen
(till exempel revisorn) kan läsa den.

## Starta bokföringen

Öppna **Bokföring** och välj den första räkenskapsperioden och en kontoplan:

- **Förening** för en registrerad förening (yhdistys), med
  medlemsavgifter och insamling samt överskott eller underskott;
- **Andelslag eller bolag** för ett andelslag (osuuskunta), till exempel ett
  vattenandelslag, eller ett bolag, med försäljning samt vinst eller förlust.

Kontoplanen är en utgångspunkt. Under **Kontoplan** kan du lägga till
konton, byta namn på dem och ta ur bruk de som du inte behöver. När ett
konto har bokföringsposter ändras inte dess nummer och slag.

Ange sedan de balanser som året börjar med, från fjolårets balansräkning,
som det första verifikatet, av slaget **Ingående balans**.

En räkenskapsperiod är 12 månader och börjar dagen efter att den föregående
slutar. Den första perioden, eller en period vars datum ändras, kan vara 1
till 18 månader.

## Verifikat

Varje bokföringspost grundar sig på ett verifikat. Under **Nytt verifikat**
anger du datum, en beskrivning och raderna: varje rad hör till ett konto,
som debet eller kredit. Debet och kredit måste vara lika stora.

Till exempel en elräkning på 84,50 € som betalas från bankkontot:

| Konto | Debet | Kredit |
| --- | --- | --- |
| 4610 El | 84,50 | |
| 1910 Bankkonto | | 84,50 |

Ett verifikat är ett utkast tills du bokför det. Bifoga kvittot (en PDF
eller ett foto) till utkastet och tryck sedan på **Bokför**. Vid bokföringen
kontrolleras att verifikatet balanserar, det får nästa nummer och låses.
Numren har inga luckor: utkast har inget nummer, så när du tar bort ett
utkast blir det ingen lucka.

## Moms

Om organisationen är momsregistrerad lägger du till datumen för
registreringen under **Bokföring av fakturor** > **Momsregistrering**. Moms
kan då bokföras på dagar inom en registrering, och bara med en sats som
gäller på verifikatets datum: den reducerade satsen var till exempel 14 %
till och med 31.12.2025 och är 13,5 % från och med 1.1.2026. Varje rad
behåller den sats den bokfördes med.

På ett verifikat märker du raden med priset utan moms och momsraden med
samma momskod. För ett inköp på 100 € + 25,5 % moms:

| Konto | Debet | Kredit | Moms |
| --- | --- | --- | --- |
| 4000 Material och förnödenheter | 100,00 | | Inköp 25,5 % |
| 1765 Ingående moms | 25,50 | | Inköp 25,5 % |
| 1910 Bankkonto | | 125,50 | |

Utgående moms, ingående moms och momsen som ska betalas har egna konton.
För varje momsperiod flyttar du den utgående och ingående momsen till
momsavräkningskontot (2939 Momsskuld (redovisas)) med ett verifikat, och
bokför betalningen av skatten mot det.

Omvänd skattskyldighet (tjänster som köps från andra EU-länder,
byggtjänster) och import, även av varor över Ålands skattegräns, stöds inte
ännu. Bokför dem för hand utan momskod och låt en bokförare granska dem.

## Fakturor och betalningar

Metra kan bokföra faktureringen åt dig. Under **Bokföring av fakturor**
väljer du den dag då den automatiska bokföringen startar och kontona:

- varje utfärdad faktura bokförs på fakturadatumet: kundfordringar på
  debetsidan, försäljning (och utgående moms) på kreditsidan;
- en kreditnota bokförs på samma sätt, men åt andra hållet;
- en betalning bokförs den dag den betalades: bankkonto på debetsidan,
  kundfordringar på kreditsidan;
- en påminnelseavgift bokförs på påminnelsens dag, på kontot för
  påminnelseavgifter, utan moms.

Försäljningen går till det konto som valts för fakturaradens avgiftsrad,
annars till det konto som valts för dess momssats, annars till
standardkontot för försäljning. Fakturor går till en egen verifikatserie
(L) och betalningar till en annan (S).

En fakturas verifikat dateras med fakturadatumet, men dess moms hör till
månaden för fakturans leveransdatum eller slutet av dess leveransperiod,
som verifikatet visar. En faktura som utfärdas i januari för förra årets
vatten har därför sin moms i förra decembers period, med förra årets
momssats.

Inställningssidan kontrollerar att kontot för kundfordringar, när den
automatiska bokföringen startar, motsvarar det som fakturorna som utfärdats
före dess hade obetalt, och varnar om de skiljer sig.

Varje sådant verifikat bokförs genast och visar fakturan det kommer från;
fakturan är dess underlag, och fakturans sida visar dess verifikat. Om ett
inte kan bokföras (till exempel för att ett konto inte längre används)
förblir det ett utkast som du rättar och bokför. Fakturor och betalningar
som gjorts medan bokföringen var av, eller som är daterade i ingen öppen
räkenskapsperiod, listas på sidan Bokföring; **Bokför dem nu** bokför dem,
en enda gång.

Välj startdagen efter det som redan bokförts för hand, så att inget bokförs
två gånger. Fakturor från före startdagen ingår i ingångsbalanserna: deras
betalningar, om de görs efter startdagen, bokförs som vanligt mot kontot
för kundfordringar.

Kontot för kundfordringar motsvarar då det som är obetalt på fakturorna:
fakturor minus kreditnotor och betalningar, plus påminnelseavgifter.

Ett felaktigt automatiskt verifikat rättas som alla andra: upphäv det och
ange den rätta bokföringsposten som ett nytt verifikat.

## Rätta ett misstag

Ett bokfört verifikat ändras aldrig och kan inte tas bort. För att rätta
ett öppnar du det och trycker på **Gör rättelse**: ett nytt verifikat med
samma rader på motsatt sida upphäver det, och båda finns kvar i
bokföringen. Ange sedan den rätta bokföringsposten som ett nytt verifikat.
Ett kvitto kan fortfarande läggas till i ett bokfört verifikat, men inte
tas bort.

## Rapporter

- **Dagbok**: de bokförda posterna i datumordning.
- **Huvudbok**: posterna konto för konto, med saldot efter varje post.
  Klicka på ett konto för att se bara det kontot.
- **Saldobalans**: varje kontos saldo vid periodens början och slut samt
  periodens debet och kredit.

Varje rapport kan gälla hela räkenskapsperioden eller några datum i den, och
kan skrivas ut. Saldot visas som debet minus kredit.

## När man ska bokföra

Lagen kräver att kontantbetalningar bokförs genast, dag för dag, och andra
bokföringsposter senast fyra månader efter utgången av sin månad. Sidan
Bokföring visar de utkast som har passerat den tiden.

## Hur länge bokföringen sparas

Periodens sida visar hur länge dess material ska sparas: bokslut, dagbok,
huvudbok, kontoplan och förteckning över bokföringar och material 10 år från
utgången av räkenskapsperioden; verifikat och kvitton 6 år från utgången av
det kalenderår då räkenskapsperioden slutade. Inget tas bort automatiskt.
När bokföringen har bokförda verifikat kan tillägget inte slås av, så att
de förblir läsbara.

En administratör som tar bort tillägget från servern (ur `METRA_PLUGINS`) måste först spara bokföringen under den lagstadgade tiden på annat sätt: spara rapporterna och kvittona, och behåll en säkerhetskopia. Uppgifterna finns kvar i databasen, men kan inte läsas i Metra medan tillägget inte är installerat.

Resultaträkning, balansräkning, budget, momssammanställningen och
avslutning av året kommer i senare versioner av tillägget.
