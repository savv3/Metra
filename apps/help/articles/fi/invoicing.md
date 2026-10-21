# Laskutus

## Asetukset ja maksut

Kohdassa **Asetukset > Laskutus > Laskutusasetukset** ylläpitäjä määrittää pankkitilin,
maksuehdot, ALV:n, numeroinnin ja laskujen tekstit. **Asetukset > Laskutus >
Maksusuunnitelmat** määrää, mitä yksiköt maksavat: kiinteät maksut ja
lukeman yksikköä kohti perittävät maksut (esimerkiksi per m³), tarvittaessa
hintaportaittain, kukin omalla ALV-kannallaan.

## Laskujen tekeminen

**Laskut > Laskutuskierrokset > Uusi laskutuskierros** valitsee jakson,
maksusuunnitelmat ja lukemakierroksen sekä tekee jokaiselle yksikölle
laskuluonnoksen, joka osoitetaan sen laskutusyhteyshenkilölle tai omistajalle.
Luonnokset, joista lukema puuttuu tai joiden lukema on outo, merkitään
**Tarkista**: syötä lukema ja muodosta luonnos uudelleen tai muokkaa sen
rivejä.

**Laadi kaikki tarkistetut luonnokset** ajon sivulla tai **Laadi lasku**
yksittäisellä luonnoksella antaa jokaiselle laskulle numeron ja päivämäärät
ja lukitsee sen. Laadittua laskua ei koskaan muuteta: virhe korjataan
hyvityslaskulla (**Tee hyvityslasku** laskulla), joka voi hyvittää laskun
kokonaan tai osittain.

## Lähettäminen

Laaditut laskut lähtevät sähköpostilla PDF-tiedostona, jossa ovat
viitenumero, pankkiviivakoodi ja maksun QR-koodi. Ne, joilla ei ole
sähköpostia tai jotka haluavat postin, listataan tulostusta varten, ja
ajon sivun **Postitettavien laskujen PDF** antaa heidän
kirjeensä yhtenä tiedostona. Jäsenet löytävät laskunsa myös omalta
sivultaan.

## Maksut ja muistutukset

Kirjaa maksut laskun sivulla painikkeella **Kirjaa maksu**, kokonaan tai
osissa. Lasku on **Maksettu**, kun mitään ei ole maksamatta. Maksuja ei
koskaan muuteta tai poisteta; voit kumota maksun kirjaamalla saman summan
negatiivisena maksuna.

**Laskut > Erääntynyt** listaa maksamattomat laskut, joiden eräpäivä on
ohi. **Lähetä muistutukset valituille** lähettää maksumuistutuksen
kunkin ensisijaisella kanavalla (sähköposti tai tekstiviesti, tai toinen, jos
siihen ei ole osoitetta) tai kirjeenä niille, jotka toivovat postia tai joilla
ei ole kumpaakaan; mukana on muistutusmaksu, jos
sellainen on määritetty, ja maksuaikaa on vähintään 14 päivää.

## Pankkitiedostot

Sen sijaan että kirjaisit jokaisen maksun käsin, lataa verkkopankistasi pankin
tiedosto saapuneista maksuista ja lähetä se kohdassa **Laskut > Pankkitiedostot**.
Metra lukee ISO 20022 -standardin XML-tiedostot: camt.054, viitemaksujen
tiedosto, ja camt.053, tiliote. Jokainen maksu, jonka viite kuuluu laskulle ja
joka maksaa täsmälleen jäljellä olevan summan, kirjataan kyseiselle laskulle.
Viite voi olla kansallinen viite tai RF-viite, välilyönneillä tai ilman.

Maksut, joilla ei ole viitettä tai joiden viite on tuntematon, osamaksut ja
liian suuret maksut merkitään **Tarkastettava**: kirjaa ne käsin oikealle
laskulle. Lähtevät maksut näytetään mutta niitä ei kohdisteta. Saman tiedoston
lataaminen kahdesti ei muuta mitään, ja maksu, joka on jo tuotu aiemmasta
tiedostosta (esimerkiksi viitemaksujen tiedosto ennen kuukauden tiliotetta),
ohitetaan. Jokaisen tuodun tiedoston kohdalla näkyvät sen rivit ja se, mitä
kullekin tapahtui.

## Kirjanpitäjälle

**Vie CSV-tiedostona** laskuluettelon alla antaa jokaisen laaditun laskun
loppusummineen, ALV:eineen, hyvityksineen, maksuineen ja maksamattomine
saatavineen. **Vie maksut** antaa jakson maksut ja muistutusmaksut.
