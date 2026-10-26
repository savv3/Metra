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
tositteena, lajiltaan **Avaavat saldot**.

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
vuotta sen kalenterivuoden lopusta, jona tilikausi päättyi. Mitään ei
poisteta automaattisesti. Kun kirjanpidossa on kirjattuja tositteita,
lisäosaa ei voi poistaa käytöstä, jotta ne pysyvät luettavina.

Ylläpitäjän, joka poistaa lisäosan palvelimelta (`METRA_PLUGINS`-asetuksesta), on ensin säilytettävä kirjanpito lakisääteisen ajan muulla tavoin: tallenna raportit ja kuitit ja säilytä varmuuskopio. Tiedot jäävät tietokantaan, mutta niitä ei voi lukea Metrassa, kun lisäosa ei ole asennettuna.

Tuloslaskelma, tase, budjetti, ALV-yhteenveto ja tilikauden päättäminen
tulevat lisäosan myöhempiin versioihin.
