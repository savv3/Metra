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

Palautus palauttaa koko rekisterin ja kaikki tiedostot sellaisiksi kuin ne
olivat varmuuskopion ottohetkellä. Vain ylläpitäjät voivat tehdä sen.

1. Avaa **Asetukset > Varmuuskopiot** ja valitse varmuuskopion vierestä **Palauta…**.
2. Anna salasanasi tai kaksivaiheisen tunnistautumisen koodi uudelleen.
3. Tarkista, mitä muuttuu: montako yksikköä, henkilöä, lukemaa, viestiä, laskua ja maksua on nyt ja varmuuskopiossa. Varmuuskopion jälkeen laaditut laskut ja kirjatut maksut luetellaan, ja ne on vahvistettava erikseen, koska ne voivat jo olla kirjanpidossa.
4. Valitse ruutu ja valitse **Palauta tämä tilannevedos**.

Ensin otetaan varmuuskopio nykyisistä tiedoista, joten palautuksen voi perua
palauttamalla sen (luettelossa "Ennen palautusta"). Palautuksen aikana kaikki
näkevät lyhyen "Palaamme pian" -sivun; se kestää yleensä alle minuutin, ja
sinun on ehkä kirjauduttava uudelleen sen jälkeen. Jos jokin menee pieleen,
juuri ennen palautusta olleet tiedot palautetaan automaattisesti.

Metran uudemman version tekemää varmuuskopiota ei voi palauttaa. Jos sovellus
ei käynnisty lainkaan, palvelimen ylläpitäjä voi palauttaa varmuuskopion
komentoriviltä asennusohjeen mukaisesti.
