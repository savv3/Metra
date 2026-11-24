# Kirjanpito

Kirjanpito-lisäosa pitää organisaation kirjanpitoa Metrassa: kahdenkertainen
kirjanpito numeroiduin tositteineen ja kuitteineen Suomen kirjanpitolain
mukaan. Ylläpitäjä ottaa sen käyttöön kohdassa Asetukset > Lisäosat.
Rahastonhoitaja pitää kirjanpitoa; hallitus ja vain luku -rooli (esimerkiksi
tilintarkastaja) voivat lukea sitä.

## Kirjanpidon aloittaminen

Avaa **Kirjanpito** ja valitse ensimmäinen tilikausi ja tilikartta:

- **Yhdistys** rekisteröidylle yhdistykselle (yhdistys), jolla on
  jäsenmaksuja ja varainhankintaa sekä ylijäämä tai alijäämä;
- **Osuuskunta tai yhtiö** osuuskunnalle (osuuskunta), esimerkiksi
  vesiosuuskunnalle, tai yhtiölle, jolla on liikevaihtoa sekä voitto tai
  tappio.

Tilikartta on lähtökohta. Kohdassa **Tilikartta** voit lisätä tilejä,
nimetä niitä uudelleen ja poistaa käytöstä tarpeettomat. Kun tilillä on
kirjauksia, sen numero ja laji pysyvät ennallaan.

Anna sitten tilikauden alkusaldot edellisen vuoden taseesta ensimmäisenä
tositteena, lajiltaan **Avaavat saldot**. Myöhemmät tilikaudet saavat
avaavat saldonsa, kun edellinen tilikausi suljetaan.

Tilikausi on 12 kuukautta ja alkaa edellisen päättymistä seuraavana
päivänä. Ensimmäinen tilikausi tai tilikausi, jonka päivämäärät muuttuvat,
voi olla 1–18 kuukautta.

## Tositteet

Jokainen kirjaus perustuu tositteeseen. Kohdassa **Uusi tosite** annat
päivämäärän, kuvauksen ja rivit: jokainen rivi kuuluu yhdelle tilille,
debetinä tai kreditinä. Debetin ja kreditin summien on oltava yhtä suuret.

Esimerkiksi pankkitililtä maksettu sähkölasku 84,50 €:

| Tili | Debet | Kredit |
| --- | --- | --- |
| 4610 Sähkö | 84,50 | |
| 1910 Pankkitili | | 84,50 |

Tosite on luonnos, kunnes kirjaat sen. Liitä kuitti (PDF tai valokuva)
luonnokseen ja paina sitten **Kirjaa**. Kirjattaessa tarkistetaan, että
tosite täsmää, se saa seuraavan numeron ja lukitaan. Numeroissa ei ole
aukkoja: luonnoksilla ei ole numeroa, joten luonnoksen poistaminen ei jätä
aukkoa.

## ALV

Jos organisaatio on arvonlisäverovelvollinen, lisää rekisteröinnin
päivämäärät kohdassa **Laskujen kirjanpito** > **ALV-rekisteröinti**. ALV
voidaan sen jälkeen kirjata rekisteröinnin aikaisille päiville, ja vain
tositteen päivänä voimassa olevalla kannalla: alennettu kanta oli esimerkiksi
14 % 31.12.2025 asti ja on 13,5 % 1.1.2026 alkaen. Jokainen rivi säilyttää
kannan, jolla se kirjattiin.

Merkitse tositteella rivi, jolla on veroton hinta, ja ALV-rivi samalla
ALV-koodilla. Ostosta 100 € + 25,5 % ALV:

| Tili | Debet | Kredit | ALV |
| --- | --- | --- | --- |
| 4000 Aineet ja tarvikkeet | 100,00 | | Ostot 25,5 % |
| 1765 Ostojen arvonlisävero | 25,50 | | Ostot 25,5 % |
| 1910 Pankkitili | | 125,50 | |

Myynnin ALV:lla, ostojen ALV:lla ja maksettavalla ALV:lla on omat tilinsä.
Siirrä kunkin ALV-kauden myynnin ja ostojen ALV tositteella ALV-tilitystilille
(2939 Arvonlisäverovelka (tilitettävä)) ja kirjaa veron maksu sitä vastaan.

Käännettyä verovelvollisuutta (muista EU-maista ostetut palvelut,
rakennuspalvelut) ja tuontia, myös tavaroita Ahvenanmaan verorajan yli, ei
vielä tueta. Kirjaa ne käsin ilman ALV-koodia ja tarkistuta ne
kirjanpitäjällä.

## Laskut ja suoritukset

Metra voi kirjata laskutuksen puolestasi. Kohdassa **Laskujen kirjanpito**
valitset päivän, jona automaattinen kirjaaminen alkaa, sekä tilit:

- jokainen annettu lasku kirjataan laskun päivälle: myyntisaamiset
  debetpuolelle, myynti (ja myynnin ALV) kreditpuolelle;
- hyvityslasku kirjataan samoin, mutta toisin päin;
- suoritus kirjataan maksupäivälle: pankkitili debetpuolelle,
  myyntisaamiset kreditpuolelle;
- muistutusmaksu kirjataan muistutuksen päivälle muistutusmaksujen tilille,
  ilman ALV:a.

Myynti kirjataan laskurivin maksurivin tilille, muuten sen ALV-kannan
tilille, muuten myynnin oletustilille. Laskut menevät omaan tositesarjaansa
(L) ja suoritukset toiseen (S).

Laskun tosite päivätään laskun päivämäärälle, mutta sen arvonlisävero
kuuluu laskun toimituspäivän tai toimitusjakson päättymisen kuukaudelle,
jonka tosite näyttää. Tammikuussa viime vuoden vedestä laadittu lasku
kuuluu siis arvonlisäverossa viime joulukuun jaksoon viime vuoden
verokannalla.

Asetussivu tarkistaa, että myyntisaamisten tili automaattisen kirjauksen
alkaessa vastaa sitä, mitä ennen sitä laaditut laskut olivat avoinna, ja
varoittaa, jos ne eroavat.

Jokainen tällainen tosite kirjataan heti ja näyttää laskun, josta se on
peräisin; lasku on sen todiste, ja laskun sivu näyttää sen tositteet. Jos
tositetta ei voi kirjata (esimerkiksi koska tili ei ole enää käytössä), se
jää luonnokseksi, jonka korjaat ja kirjaat. Laskut ja suoritukset, jotka on
tehty kirjaamisen ollessa pois päältä tai jotka on päivätty ilman avointa
tilikautta, luetellaan Kirjanpito-sivulla; **Kirjaa ne nyt** kirjaa ne
kerran.

Valitse aloituspäivä käsin jo kirjatun jälkeen, jotta mitään ei kirjata
kahdesti. Ennen aloituspäivää annetut laskut kuuluvat avaaviin saldoihin:
niiden suoritukset, jos ne tehdään aloituspäivän jälkeen, kirjataan
tavalliseen tapaan myyntisaamisten tiliä vastaan.

Myyntisaamisten tili vastaa tällöin laskuilla avoinna olevaa määrää:
laskut miinus hyvityslaskut ja suoritukset, plus muistutusmaksut.

Virheellinen automaattinen tosite oikaistaan kuten muutkin: kumoa se ja
kirjaa oikea kirjaus uutena tositteena.

## Virheen oikaiseminen

Kirjattu tosite ei koskaan muutu eikä sitä voi poistaa. Voit oikaista sen
avaamalla sen ja painamalla **Tee vastakirjaus**: uusi tosite, jonka rivit
ovat samat vastakkaisella puolella, mitätöi sen, ja molemmat jäävät
kirjanpitoon. Anna sitten oikea kirjaus uutena tositteena. Kirjattuun
tositteeseen voi vielä lisätä kuitin, mutta sitä ei voi poistaa.

## Raportit

- **Päiväkirja**: kirjatut kirjaukset päivämääräjärjestyksessä.
- **Pääkirja**: kirjaukset tileittäin, saldo jokaisen kirjauksen jälkeen.
  Napsauta tiliä nähdäksesi vain sen tilin.
- **Saldoluettelo**: kunkin tilin saldo jakson alussa ja lopussa sekä
  jakson debetit ja kreditit.

Kukin raportti voi kattaa koko tilikauden tai muutaman päivän sen sisällä,
ja sen voi tulostaa. Saldo näytetään muodossa debet miinus kredit.

## Milloin kirjaus tehdään

Laki edellyttää, että käteismaksut kirjataan viipymättä, päiväkohtaisesti,
ja muut kirjaukset viimeistään neljän kuukauden kuluttua kuukauden
päättymisestä. Kirjanpito-sivu luettelee luonnokset, jotka ovat ylittäneet
määräajan.

## Kuinka kauan kirjanpito säilytetään

Tilikauden sivu näyttää, kuinka kauan sen aineisto on säilytettävä:
tilinpäätös, päiväkirja, pääkirja, tilikartta ja luettelo kirjanpidoista ja
aineistoista 10 vuotta tilikauden päättymisestä; tositteet ja kuitit 6
vuotta sen kalenterivuoden lopusta, jona tilikausi päättyi. Laskutuksesta
kirjatut laskut, hyvityslaskut ja suoritukset ovat tositteiden perusteena,
ja ne säilytetään yhtä kauan. **Kuinka kauan kirjanpito säilytetään**,
johon on linkki tilikausien luettelosta, näyttää kaikki tilikaudet yhdessä:
tositteet, kuitit ja laskut, kaksi päivämäärää ja sen, onko lain
vähimmäisaika jo kulunut.

Nämä ovat lyhimmät kirjanpitolain sallimat ajat. Muut säännöt voivat
vaatia aineiston säilyttämistä pidempään: avustuksen ehdot
(vesihuoltoverkkojen avustukset edellyttävät usein vähintään 10 vuotta),
kiinteistöinvestoinnin arvonlisäveron 10 vuoden tarkistuskausi tai
keskeneräinen verotarkastus, muutoksenhaku tai riita. Sivu kertoo, milloin
kirjanpitolain vähimmäisaika on kulunut, ei sitä, että aineiston saa
poistaa. Mitään ei poisteta automaattisesti,
eikä määräajan ylittäneen tilikauden poistamista vielä tarjota Metrassa:
kun sen aika koittaa, vie tilikausi ensin ja päätä asiasta hallituksen ja
tilintarkastajan kanssa. Kun kirjanpidossa on kirjattuja tositteita,
lisäosaa ei voi poistaa käytöstä, jotta ne pysyvät luettavina.

Tositteissa, kuiteissa ja laskuissa voi olla jäsenten ja toimittajien
nimiä. Ne ovat kirjanpitoaineistoa, jonka säilyttämisestä laki velvoittaa,
joten ne säilytetään näiden aikojen ajan, vaikka henkilö pyytäisi tietojensa
poistamista (GDPR:n 17 artiklan 3 kohdan b alakohta). Henkilön tai yksikön
muuttaminen tai arkistointi rekisterissä ei muuta mitään jo kirjattua:
kirjanpito säilyttää nimet ja summat sellaisina kuin ne kirjattiin.

Ylläpitäjän, joka poistaa lisäosan palvelimelta (`METRA_PLUGINS`-asetuksesta), on ensin säilytettävä kirjanpito lakisääteisen ajan muulla tavoin: vie jokainen tilikausi (katso alla), säilytä tilinpäätöspaketit ja säilytä varmuuskopio. Tiedot jäävät tietokantaan, mutta niitä ei voi lukea Metrassa, kun lisäosa ei ole asennettuna.

## Kirjanpidon vienti

**Vie kirjanpito** tilikauden sivulla antaa tilikauden tiedostoina
kirjanpitäjälle, joka ottaa kirjanpidon haltuunsa omalla ohjelmallaan, tai
kopion säilyttämiseksi Metran ulkopuolella:

- **Lataa ZIP-tiedosto**: tilikartta, jossa kunkin tilin avaava saldo,
  debet, kredit ja päättävä saldo (`accounts.csv`), kirjattujen tositteiden
  kaikki rivit päiväjärjestyksessä (`vouchers.csv`), kuitit kansiossa
  tositetta kohden, tilikausi SIE 4 -muodossa (`books.se`) sekä README, joka
  kuvaa tiedostot.
- **Lataa SIE 4**: pelkkä SIE 4 -tiedosto. SIE on pohjoismainen tekstimuoto
  kirjanpidon siirtämiseen kirjanpito-ohjelmien välillä. Avaavat saldot ovat
  sen avaavia saldoja ja muut kirjatut tositteet sen tositteita.

CSV-tiedostot ovat UTF-8-muotoisia, erotettu puolipisteillä, päivämäärät
muodossa YYYY-MM-DD ja desimaalierottimena pilkku. Luonnokset eivät kuulu
kirjanpitoon, ja ne jätetään pois. Avoimen tilikauden vienti kertoo, että
se on alustava. Kysy kirjanpitäjältä, mitä muotoa heidän ohjelmansa tuo;
useimmat hyväksyvät SIE-tiedoston tai CSV-tiedoston. Jokainen vienti
kirjataan muutoslokiin.

## Kuukausien lukitseminen

Kun kuukausi on ilmoitettu, esimerkiksi arvonlisäveroilmoituksessa, lukitse
se tilikauden sivulla: valitse viimeinen lukittava päivä ja paina
**Lukitse**. Sinä päivänä tai aiemmin ei voi kirjata mitään, eikä lukitusta
voi purkaa. Jakson päivätyt luonnokset on ensin kirjattava tai poistettava.
Lukitulle jaksolle päivätty lasku, suoritus tai muistutusmaksu kirjataan
sen sijaan ensimmäiselle avoimelle päivälle, ja kuvaukseen tulee
"kirjattu jälkikäteen" ja sen oma päivämäärä.

## Käyttöomaisuus

Kirjaa kohtaan **Käyttöomaisuus** jokainen kone, rakennus, vesijohtoverkosto
tai muu yli vuoden käytössä oleva hyödyke: sen tasetili, hankintapäivä,
hankintameno ja poistosuunnitelma (tasapoisto vuosien määrälle tai
menojäännöspoisto prosentteina; maa-alueesta ei tehdä poistoja).
Suunnitelma lasketaan hankintakuukaudesta alkaen, myös vuosille ennen kuin
kirjanpitoa pidettiin Metrassa. Kirjaa itse hankinta tositteena tasetilille.

## Tilikauden päättäminen

Kun tilikausi on päättynyt, avaa se ja paina **Sulje tilikausi**. Sivu käy
läpi tilinpäätöksen vaiheet:

1. **Suunnitelman mukaiset poistot**: **Tee poistotosite** tekee
   käyttöomaisuusrekisteristä luonnoksen, joka on päivätty tilikauden
   viimeiselle päivälle. Tarkista ja kirjaa se.
2. **Tilikauden jälkeen laskutetut tuotot**: tilikauden jälkeen lähetetyt
   laskut sen aikana tehdyistä toimituksista tarjotaan jaksotustositteeksi,
   jotta tuotto kohdistuu oikealle vuodelle. Muut jaksotukset (myöhemmin
   laskutetut kulut, etukäteen saadut tuotot) ovat lajia **Jaksotus**
   olevia tositteita, jotka päivätään tilikauden viimeiselle päivälle.
   Sulkeminen peruu kaikki jaksotukset seuraavan tilikauden ensimmäisenä
   päivänä.
3. **Tiliotteet**: anna jokaisen pankkitilin saldo tilikauden lopun
   tiliotteelta; tase-erittelyt vertaavat sitä kirjanpitoon.
4. **Liitetiedot ja allekirjoitukset**: tilinpäätöksen liitetiedot, kuhunkin
   ehdotettu teksti, ja allekirjoittavat hallituksen jäsenet. Kysy
   kirjanpitäjältä, mitä liitetietoja yhteisö tarvitsee.
5. **Sulje tilikausi**: sivu näyttää, mikä vielä estää sulkemisen
   (luonnokset, laskutuksesta odottavat kirjaukset, laskelmien ulkopuoliset
   tilit, avoin aiempi tilikausi) ja mitä kannattaa ensin tarkistaa.

Sulkeminen lukitsee tilikauden pysyvästi, tallentaa sen tilikartan
sellaisena kuin se on sinä päivänä (myöhempi nimenmuutos ei muuta suljetun
tilikauden raportteja) ja avaa seuraavan tilikauden, tarvittaessa lisäten
sen, niin että päättävät saldot ovat sen avaavat saldot. Tilikauden tulos
siirretään valitsemallesi oman pääoman tilille, oletuksena edellisten
tilikausien tulokseen. Avaavat saldot kirjoitetaan käsin vain ensimmäiselle
Metrassa pidetylle tilikaudelle.

Tilinpäätös on laadittava neljän kuukauden kuluessa tilikauden
päättymisestä.

## Tilinpäätöspaketti

**Tilinpäätöspaketti** tekee tilintarkastajalle yhden PDF-tiedoston:
tuloslaskelma ja tase edellisen vuoden luvuin, liitetiedot,
allekirjoitussivu tilinpäätösmerkintöineen, tase-erittelyt (saldot,
tiliotteet, käyttöomaisuus ja avoimet laskut), luettelo kirjanpidoista ja
aineistoista, tilikartta, päiväkirja ja pääkirja. Ennen tilikauden
sulkemista sen ensimmäisellä sivulla lukee, että se on keskeneräinen. Se on
suomeksi tai ruotsiksi; englanninkielinen on merkitty käännökseksi. Valitse
**Vain tilinpäätös ja liitetiedot** rekisteröintiä varten: osuuskunta
ilmoittaa tilinpäätöksensä kaupparekisteriin, kun osuuskunnan kokous on
vahvistanut sen.

## Aiemman tilikauden oikaiseminen

Suljettua tilikautta ei voi koskaan avata uudelleen. Myöhemmin löytynyt
virhe oikaistaan avoimella tilikaudella: valitse tositteella suljettu
tilikausi kohtaan **Oikaisee tilikauden**, ja kirjaa olennainen virhe
edellisten tilikausien tulosta vastaan. Tilikauden liitetiedoissa luetellaan
tällaiset oikaisut.

## Tilinpäätös

**Tuloslaskelma** ja **Tase** näyttävät kirjanpidon pien- ja
mikroyritysten tilinpäätöksestä annetun asetuksen (PMA 1753/2015)
mukaisissa muodoissa: yhdistys saa voittoa tavoittelemattoman yhteisön
tuloslaskelman, jossa on varsinainen toiminta, varainhankinta sekä sijoitus-
ja rahoitustoiminta, kukin ylijäämineen tai alijäämineen; osuuskunta tai
yhtiö saa tavallisen tuloslaskelman, jossa on liikevaihto ja liikevoitto.
Tase on molemmille sama.

Valitse kieli kohdasta **Kieli**. Suomenkieliset rivien nimet ovat
asetuksen omat; ruotsinkieliset ovat vakiintuneita suomenruotsalaisia
termejä, joita ei ole vielä tarkistettu asetuksen ruotsinkielistä tekstiä
vasten, ja ruotsinkielinen laskelma kertoo sen. Tilinpäätös laaditaan suomeksi tai ruotsiksi;
englanninkielinen versio voidaan näyttää, mutta se on käännös eikä sitä ole
tarkoitettu toimitettavaksi viranomaiselle. Edellinen tilikausi näytetään
jakson vieressä, kun se on Metrassa.

Jokainen tili kuuluu sille riville, jolle sen numero osuu. Tilikarttapohjat
noudattavat tätä, ja lisäämäsi tili päätyy sen numeroalueen riville:
esimerkiksi 1700–1749 myyntisaamiset, 1900–1999 kassa ja pankki, 2610–2699
lainat rahoituslaitoksilta, 2871–2879 ostovelat. Jos tili ei osu
millekään riville, laskelma luettelee sen ja jättää sen pois, joten anna sille
numero oikealta väliltä. Rastita tilillä **Pitkäaikainen**, kun kyse on yli
vuoden kuluttua erääntyvästä saamisesta tai velasta; pidä vuoden sisällä
erääntyvä osa omalla tilillään.

Tilikauden voitto tai ylijäämä lasketaan tuotto- ja kulutileistä, joten tase
täsmää jo ennen tilikauden päättämistä.
Kunnes tilikausi on päätetty, laskelman PDF- ja CSV-tiedosto merkitään
keskeneräiseksi syineen (tilikausi on avoinna, laskelma kattaa osan
tilikaudesta, tilejä puuttuu tai tase ei täsmää): vain päätetyn tilikauden
allekirjoitettu tilinpäätös on lopullinen.

### Kokoluokka

Laskelmien alla Metra näyttää kokoluokan taseen loppusumman, liikevaihdon
(laskettuna 12 kuukaudelta) ja henkilöstön keskimääräisen lukumäärän
perusteella kuluneelta ja sitä edeltäneeltä tilikaudelta. Anna tilikauden
henkilöstön keskimääräinen lukumäärä tilikauden sivulla. **Mikroyritys** saa
käyttää lyhyempää muotoa, joka jättää pois kirjaimilla merkityt erittelyt ja
näyttää, kuinka suuri osa veloista on lyhytaikaisia; täysi muoto on aina
sallittu. Metra pysyy turvallisella puolella: yritys on mikroyritys vain, jos
enintään yksi mikroyrityksen raja ylittyy kumpanakaan vuonna. Yhdistyksellä
kaikki tuotot lasketaan liikevaihdoksi. Kun myös pienyrityksen rajat
ylittyvät, asetus ei enää päde: kysy kirjanpitäjältä.

## Talousarvio

Kohdassa **Talousarvio** **Muokkaa talousarviota** ottaa vastaan vuoden odotetut
tuotot ja kulut tileittäin positiivisina summina. **Talousarvio** vertaa niitä
sitten valituilla päivillä kirjattuun, tileittäin ja yhteensä.

## ALV-yhteenveto

**ALV-yhteenveto** laskee yhteen myynnin ja ostojen ALV:n kannoittain kunkin
verokauden osalta, sisältäen maksettavan tai palautettavan veron ja päivän,
jona ilmoitus erääntyy. Valitse verokausi (kuukausi, neljännesvuosi tai
kalenterivuosi) ALV-rekisteröinnissä.

ALV seuraa toimitusta, ei tositteen päivää:

- lasku lasketaan toimitusjakson lopussa (tai toimituspäivänä);
- laskun osa, joka on maksettu ennen toimitusjakson päättymistä, on
  ennakkomaksu: sen ALV kohdistuu maksukuukaudelle;
- käsin syötetty kuitti lasketaan tositteen päivänä;
- vastakirjaus lasketaan siellä, missä sen oikaisema tosite laskettiin, koska
  ALV-virhe oikaistaan kaudelle, jolla se tehtiin.

Yhteenvedossa ovat vain ALV-koodilliset rivit. Käännetty verovelvollisuus,
maahantuonti (myös Ahvenanmaan verorajan yli) ja ilman ALV-koodia kirjatut
kirjaukset eivät ole mukana: lisää ne ilmoitukseen itse. Yhteenveto kertoo,
milloin se ei ole valmis kopioitavaksi ilmoitukseen: kun ALV-tilin kirjauksella
ei ole ALV-koodia, tositeluonnoksessa on ALV:a tai laskut ja suoritukset
odottavat tositteitaan. Se luettelee myös kauden päättymisen jälkeen kirjatun,
siltä varalta että kauden ilmoitus on jo annettu.

## Tulostus ja tiedostot

Jokaisen raportin voi tulostaa, tallentaa **PDF**-tiedostona tai ladata
**CSV**-tiedostona taulukkolaskentaa varten. Koko tilikausi viedään
toiminnolla **Vie kirjanpito**.
