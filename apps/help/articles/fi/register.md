# Rekisteri

Rekisteri sisältää **yksiköt** (esimerkiksi taloudet, kiinteistöt tai
venepaikat) ja **henkilöt**. Henkilö liitetään yksikköön sen omistajana,
laskutusyhteyshenkilönä tai muuna yhteyshenkilönä, ja yksi henkilö voi olla
usean yksikön yhteyshenkilö.

## Yksikkötyypit ja kentät

Ylläpitäjä määrittää yksiköiden lajit kohdassa **Asetukset > Rekisteri > Yksikkötyypit ja niiden kentät**,
kullekin omat kenttänsä, kuten kiinteistötunnus tai mittarin numero. Kenttiä
voi lisätä myös kaikille henkilöille. Yksikkötyypin tai kentän poistamista
edeltää varmuuskopio, koska poisto vie tiedot jokaiselta yksiköltä.

## Yksiköiden ja henkilöiden käsittely

- **Yksiköt** ja **Henkilöt** listaavat rekisterin. Hae ja suodata listaa ja lataa sitten näkemäsi **Vie CSV-tiedostona** -toiminnolla.
- **Lisää** yksikkö tai henkilö listan yläpuolella olevalla painikkeella. Yksikön sivulla voit lisätä olemassa olevan henkilön yhteyshenkilöksi tai luoda uuden.
- **Arkistoi** poistamisen sijaan: arkistoitu yksikkö tai henkilö säilyy, mutta poistuu listoilta ja lähetyksistä.
- **Tunnisteet** ryhmittelevät yksiköitä, esimerkiksi kylän tai putkiosuuden mukaan, ja viestit voi lähettää kaikille, joilla on tietty tunniste.

Jokainen muutos ja jokainen kerta, kun joku avaa yksikön tai henkilön sivun,
tallennetaan historiaan. Ylläpitäjä ja Hallitus näkevät sen sivun alalaidassa.

## Tuonti laskentataulukosta

**Yksiköt > Tuo CSV** tuo yhden tyypin yksiköt, kullekin enintään yksi
yhteyshenkilö:

1. Valitse yksikkötyyppi ja tiedosto. Tallenna se Excelistä muodossa *CSV UTF-8*.
2. Tarkista, mikä sarake menee mihinkin kenttään. Samannimiset sarakkeet valitaan puolestasi.
3. Tarkista esikatselu. Jokainen rivi on merkitty OK, ohitetuksi (yksikkö on jo olemassa) tai sen virheet on näytetty. Mitään ei tuoda, jos yhdessäkin rivissä on virheitä.

Henkilöt yhdistetään rekisterissä jo oleviin ensin sähköpostin, sitten
puhelinnumeron perusteella, joten ketään ei lisätä kahteen kertaan.
Varmuuskopio otetaan ennen tuontia.

## Julkinen sivu

Vierailijat, jotka eivät ole kirjautuneet, näkevät organisaatiosi julkisen
sivun: nimen, logon, lyhyen kuvauksen ja yhteystiedot. Ylläpitäjä muokkaa
sitä kohdassa **Asetukset > Organisaatio**. **Ilmoitukset**, kuten "Vesi
poikki klo 18:00 asti", näkyvät julkisella sivulla ja jäsenten sivuilla.
