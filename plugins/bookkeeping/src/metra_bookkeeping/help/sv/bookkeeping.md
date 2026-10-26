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

Avslutning av året kommer i en senare version av tillägget.

## Bokslut

**Resultaträkning** och **Balansräkning** visar bokföringen i de format som
anges i förordningen om bokslut för små och mikroföretag (PMA 1753/2015):
en förening får den ideella resultaträkningen, med egen verksamhet,
insamling samt placerings- och finansieringsverksamhet, var och en med
överskott eller underskott; ett andelslag eller bolag får den vanliga
resultaträkningen med omsättning och rörelsevinst. Balansräkningen är den
samma för båda.

Välj språk under **Språk**. Radnamnen på finska är förordningens egna;
de svenska är de vanliga finlandssvenska termerna och ännu inte granskade
mot förordningens svenska text, vilket en svensk uppställning säger. Bokslutet förs på finska eller svenska; en engelsk version kan
visas, men den är en översättning och inte avsedd för inlämning. Den
föregående räkenskapsperioden visas bredvid perioden när den finns i Metra.

Varje konto hör till den rad som dess nummer faller på. Kontoplansmallarna
följer detta, och ett konto som du lägger till hamnar på raden för sitt
nummerintervall: till exempel 1700–1749 kundfordringar, 1900–1999 kassa och
bank, 2610–2699 lån från kreditinstitut, 2871–2879 leverantörsskulder. Om
ett konto faller på ingen rad räknar uppställningen upp det och utelämnar
det, så ge det ett nummer i rätt intervall. Kryssa i **Långfristig** på ett
konto för en fordran eller skuld som förfaller efter mer än ett år; håll den
del som förfaller inom ett år på ett eget konto.

Årets vinst eller överskott räknas ut från intäkts- och kostnadskontona, så
balansräkningen går ihop redan innan året har avslutats.
Tills året är avslutat märks pdf- och csv-filen av en uppställning som
preliminär, med skälen (året är öppet, den gäller en del av året, konton
saknas eller den går inte ihop): bara det avslutade årets undertecknade
bokslut är slutligt.

### Storleksklass

Under uppställningarna visar Metra storleksklassen, utifrån balansomslutningen,
omsättningen (räknad för 12 månader) och det genomsnittliga antalet anställda
under året och året före. Ange årets genomsnittliga antal anställda på
periodens sida. Ett **mikroföretag** får använda det kortare formatet, som
utelämnar de bokstavsmärkta specifikationerna och visar hur stor del av
skulden som är kortfristig; det fullständiga formatet är alltid tillåtet.
Metra håller sig på den säkra sidan: ett företag är ett mikroföretag endast
om högst en av mikroföretagsgränserna överskrids under något av åren. För en
förening räknas alla dess intäkter som omsättning. När även gränserna för ett
småföretag överskrids gäller förordningen inte längre: fråga en bokförare.

## Budget

Under **Budget** tar **Redigera budgeten** emot årets förväntade intäkter och
kostnader per konto, som positiva belopp. **Budget** jämför dem sedan med det
som bokförts under de valda datumen, per konto och totalt.

## Momssammandrag

**Momssammandrag** summerar utgående och ingående moms per momssats för varje
momsperiod, med skatten att betala eller få tillbaka och den dag då
deklarationen förfaller. Välj momsperiod (månad, kvartal eller kalenderår) i
momsregistreringen.

Momsen följer leveransen, inte verifikatets datum:

- en faktura räknas vid slutet av sin leveransperiod (eller på sitt
  leveransdatum);
- den del av en faktura som betalats innan leveransperioden slutar är en
  förskottsbetalning: dess moms redovisas för den månad den betalades;
- ett kvitto som matats in för hand räknas på verifikatets datum;
- en rättelse räknas där verifikatet den rättar räknades, eftersom ett
  momsfel rättas för den period då det gjordes.

Endast rader med momskod ingår i sammandraget. Omvänd skatteskyldighet,
import (även över Ålands skattegräns) och poster som bokförts utan momskod
ingår inte: lägg till dem i deklarationen själv. Sammandraget säger till när
det inte är redo att kopieras till deklarationen: när en post på ett momskonto
saknar momskod, ett verifikatutkast har moms, eller fakturor och betalningar
väntar på sina verifikat. Det räknar också upp det som bokförts efter att en
period slutat, ifall den periodens deklaration redan lämnats.

## Utskrift och filer

Varje rapport kan skrivas ut, sparas som **PDF** eller laddas ner som en
**CSV**-fil för ett kalkylprogram.
