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

Tuloslaskelma, tase, budjetti, laskuista ja maksuista tehtävät automaattiset
kirjaukset sekä tilikauden päättäminen tulevat lisäosan myöhempiin
versioihin.
