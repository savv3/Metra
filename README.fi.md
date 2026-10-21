[English](README.md) · [Svenska](README.sv.md) · **Suomi**

> **Huom.** Tämä suomenkielinen teksti on konekäännös, eikä sitä ole
> tarkistettu. Jos teksti ja [englanninkielinen README](README.md) eroavat
> toisistaan, englanninkielinen pätee. Korjaukset ovat tervetulleita.

# Metra

Yksinkertainen verkkosovellus, jota voit ylläpitää omalla palvelimellasi.
Se on tehty pienille yrityksille ja yhdistyksille jäsenten ja asiakkaiden
hallintaan. Vapaa ja avoin lähdekoodi MIT-lisenssillä.

Metrassa on rekisteri kotitalouksista tai muista yksiköistä ja niiden
yhteyshenkilöistä. Se kerää vuosittaiset lukemat, kuten vesimittarit,
lähettää tekstiviestejä, sähköposteja ja kiireellisiä tiedotteita, lähettää
uutiskirjeitä ja laatii laskut. Se toimii pienellä palvelimella Dockerin
avulla ja varmuuskopioi itsensä joka yö toiseen paikkaan. Ylläpitäjä
määrittää rekisterin tyypit ja kentät, joten mikään ei ole sidottu yhteen
organisaatiotyyppiin.

## Kenelle Metra sopii?

Metra sopii kaikille, joilla on luettelo kotitalouksista tai jäsenistä,
jotka laskuttavat heitä kerran tai kahdesti vuodessa ja joiden täytyy joskus
tavoittaa kaikki nopeasti. Se tehtiin ensin vesiosuuskunnalle, jossa on noin
50 kotitaloutta. Muita sopivia käyttäjiä:

- **Tiekunnat**, joilla on osuudet kiinteistöittäin, vuosimaksu ja
  tiedotteet tien sulkemisista.
- **Valokuitu- ja kyläverkko-osuuskunnat**, joilla on liittymät
  kotitalouksittain, kuukausi- tai vuosimaksut ja tiedotteet katkoista.
- **Asunto-osakeyhtiöt ja pienet taloyhtiöt**, joissa asunnot ovat
  yksiköitä, ja joilla on maksut sekä tiedotteet vesikatkoista tai
  huolloista.
- **Satamat ja veneseurat**, joissa venepaikat ovat yksiköitä, ja joilla on
  kausimaksut ja myrskyvaroitukset.
- **Siirtolapuutarha- ja mökkiyhdistykset**, joilla on palstat, vuosimaksut
  ja vesi, joka kytketään päälle tai pois kauden mukaan.
- **Metsästysseurat ja kalastuskunnat**, joilla on jäsenet, osuudet ja
  maksut.
- **Urheiluseurat ja pienet vapaaehtoisjärjestöt**, joilla on jäsenet,
  jäsenmaksut ja uutiskirjeet.
- **Pienet palveluyritykset**, kuten nuohoojat, sakokaivojen tyhjennys tai
  lumenauraus, joilla on asiakkaat osoitteittain, vuosittaiset laskut ja
  käynti-ilmoitukset.

## Ominaisuudet

- Muokattava rekisteri yksiköistä, henkilöistä ja yhteystiedoista sekä
  CSV-tuonti ja -vienti
- Roolit, henkilökunnan kaksivaiheinen tunnistautuminen ja loki kaikista
  muutoksista
- Vuosittaiset lukemat, jotka hallitus tai jäsenet itse syöttävät
- Jäsenten itsepalvelu henkilökohtaisten linkkien kautta, ilman salasanoja
- Tekstiviestit (46elks) ja sähköpostit, kiireelliset tiedotteet ja julkinen
  sivu tiedotteineen
- Uutiskirjeet tallennetulla suostumuksella ja yhden klikkauksen
  peruutuksella
- Laskutus suomalaisilla viitenumeroilla, virtuaaliviivakoodilla,
  maksun QR-koodilla, hyvityslaskuilla ja maksumuistutuksilla
- Öiset varmuuskopiot, salattuina ja kopioituina S3:een, SFTP:hen tai
  FTPS:ään
- Ilmoitukset kellon alla henkilökunnalle, esimerkiksi epäonnistunut
  varmuuskopio tai perille menemätön tekstiviesti, ja jokainen valitsee, mitä saa
- Kokoukset (erikseen käyttöön otettava laajennus): kokouskutsu ja
  esityslista, läsnäolo ja äänet sekä pöytäkirjat, jotka
  pöytäkirjantarkastajat tarkastavat ja jotka näytetään jäsenille
- Laajennukset (pluginit) sekä ruotsi, englanti ja suomi sovelluksessa
  (suomenkielinen käännös on konekäännös, jota ei ole tarkistettu, ja
  sovellus kertoo sen)

**Tila:** varhainen kehitysvaihe. Rekisteri, lukemat, itsepalvelu,
viestit, uutiskirjeet ja laskutus ovat valmiina; suunnitelma ja tulevat
vaiheet ovat tiedostossa [docs/architecture.md](docs/architecture.md)
(englanniksi).

## Aloitus

```sh
cp .env.example .env    # aseta sitten METRA_DOMAIN ja METRA_SECRET_KEY
docker compose up -d --build
```

Muu dokumentaatio on englanniksi:

- [INSTALL.md](INSTALL.md): asennus, asetukset, sähköposti ja tekstiviestit,
  varmuuskopiot ja kehitys
- [Käyttöopas](docs/user-guide.md): lukemat, itsepalvelu, viestit,
  uutiskirjeet, laskutus, tuonti ja roolit
- [Useita organisaatioita yhdellä palvelimella](docs/multiple-organisations.md)
- [Laajennukset](docs/plugins.md)
- [REST-rajapinta](docs/api.md): `api`-laajennus muille järjestelmille tunnisteilla
- [AGENTS.md](AGENTS.md): ohjeet koodia kehittäville

## Lisenssi

MIT, katso [LICENSE](LICENSE).
