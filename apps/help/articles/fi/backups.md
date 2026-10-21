# Varmuuskopiot ja palautus

Metra tekee **varmuuskopioita**: kopioita koko rekisteristä ja kaikista ladatuista tiedostoista.

## Milloin varmuuskopio tehdään

- joka yö,
- kun Metran uusi versio käynnistyy, ennen kuin se muuttaa mitään,
- ennen CSV-tuontia, ennen yksikkötyypin tai kentän poistamista ja ennen palautusta,
- aina kun ylläpitäjä napsauttaa **Ota tilannevedos nyt** kohdassa **Asetukset > Varmuuskopiot**.

Jos riskialttiin toiminnon edellä ei voida tehdä varmuuskopiota, toiminto
keskeytetään.

Jokainen varmuuskopio säilytetään 7 päivää, minkä jälkeen säilytetään yksi
viikossa 4 viikon ajan ja yksi kuukaudessa vuoden ajan. Käsin otetut
varmuuskopiot säilyvät, kunnes ylläpitäjä poistaa ne. Jos asennus on
määritetty sitä varten, jokainen varmuuskopio lähetetään lisäksi salattuna
palvelimen ulkopuoliseen tallennustilaan.

## Varmuuskopiot-sivu

**Asetukset > Varmuuskopiot** listaa kaikki varmuuskopiot: milloin ja miksi
ne on otettu, Metran version, koon sekä sen, onko varmuuskopio tällä
palvelimella, palvelimen ulkopuolella vai molemmissa. Viimeaikaiset ongelmat
näkyvät sivun yläreunassa.

## Varmuuskopion palauttaminen

Varmuuskopion palauttaminen Varmuuskopiot-sivulta tulee seuraavaan
versioon: ylläpitäjä valitsee varmuuskopion, näkee mitä se sisältää ja mitä
poistettaisiin, ja vahvistaa palautuksen. Siihen asti palvelinta ylläpitävä
henkilö voi palauttaa varmuuskopion asennusoppaan ohjeiden mukaan.
