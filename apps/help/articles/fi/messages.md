# Viestit ja uutiskirjeet

## Sähköpostiasetukset

Ylläpitäjä päättää, miten sähköposti lähetetään, kohdassa **Asetukset >
Sähköposti**, joka on myös yksi käyttöönoton vaiheista. Valitse **SMTP**, jos
haluat lähettää yhdistyksen oman sähköpostitilin kautta: anna
**Sähköpostipalvelin**, **Portti**, **Salaus**, **Käyttäjätunnus** ja
**Salasana**, jotka saat sähköpostin tarjoajaltasi. Lisäosa voi tarjota
sen sijaan lähetyspalvelun. Aseta **Lähettäjän osoite**, jonka jäsenet näkevät,
ja **Vastausosoite**, jos vastausten pitää mennä muualle. Kaikki Metran
sähköposti lähetetään näin, myös kirjautumiskoodit ja kutsut. **Lähetä
testisähköposti** tarkistaa, että lähetys toimii. Tallennettua salasanaa ei
näytetä enää koskaan: jätä kenttä tyhjäksi, jos haluat säilyttää sen. Harmaa
kenttä on asetettu palvelimella, eikä sitä voi muuttaa sovelluksessa.

### Mailgun

**Mailgun**-lisäosa lähettää sähköpostin sen sijaan Mailgunin kautta. Anna
**Lähetysverkkotunnus**, **API-avain** ja **Alue** kohdassa **Asetukset >
Lisäosat > Mailgun** ja valitse sitten **Mailgun** kohdassa **Asetukset >
Sähköposti**. Kun **Webhookien allekirjoitusavain** on annettu ja webhook on
lisätty Mailgunissa (katso asennusohje), jokaisen viestin tila näyttää, onko
se toimitettu. Kun sähköposti palautuu, viesti merkitään epäonnistuneeksi, ja
henkilön sivulla näkyy osoitteen vieressä **Palautui** sekä Mailgunin
ilmoittama syy. Tarkista osoite henkilöltä ja korjaa se; uusi osoite poistaa
merkinnän. Jos vastaanottaja merkitsi viestin roskapostiksi, se näkyy
viestissä.

**Lähetykset > Uusi viesti** kirjoittaa yhden viestin kaikille, tunnisteella
merkityille yksiköille tai henkilöille, tietyn tyyppisille yksiköille tai suodattamasi listan
yksiköille (**Lähetä viesti näille yksiköille** yksikkölistan alla). Valitse,
menevätkö viestit kunkin yksikön kaikille yhteyshenkilöille vai vain
pääyhteyshenkilölle, ja millä tavalla. Tavallinen valinta on **Kunkin
henkilön ensisijainen kanava**: sähköpostia toivovat saavat sähköpostin ja
tekstiviestiä toivovat tekstiviestin, tai toisen, jos heillä ei ole siihen
osoitetta (tai lähetys epäonnistuu). Näitä viestejä ei lähetetä kirjeinä, joten
postia toivovat saavat tekstiviestin tai muuten sähköpostin. Ensisijainen kanava
asetetaan kunkin henkilön sivulla. Kohdasta **Muut vaihtoehdot** voit sen
sijaan valita toiveista riippumatta:

- **Vain tekstiviesti** tai **Vain sähköposti**,
- **Tekstiviesti, tai sähköposti niille, joilla ei ole puhelinta**, tai
- **Sekä tekstiviesti että sähköposti**.

Tunniste tavoittaa niiden yksiköiden yhteyshenkilöt, joilla tunniste on, sekä
henkilöt, joilla se on itsellään, vaikka he eivät olisi minkään yksikön
yhteyshenkilöitä. Jos kukaan ei vastaa valintoja, tarkistussivu kertoo syyn,
esimerkiksi että tunnisteella merkityllä yksiköllä ei vielä ole
yhteyshenkilöitä.

Ensisijaista kanavaa käytettäessä kirjoita sekä tekstiviestin teksti että
sähköpostin aihe, koska vastaanottajat voivat saada kumman tahansa. Lomakkeessa
näkyvät vain valittuun tapaan tarvittavat tekstit. Paikkamerkit,
kuten `{first_name}` ja `{unit}`, täytetään kullekin henkilölle, ja laskuri
näyttää, kuinka monta tekstiviestiä teksti vaatii. Ennen kuin mitään
lähetetään, tarkistussivu näyttää, kuinka moni saa tekstiviestin ja kuinka
moni sähköpostin sekä ketä ei tavoiteta, jotta heille voi soittaa.

## Kiireelliset hälytykset

**Kiireellinen varoitus** (punainen painike) on tarkoitettu häiriöille, kuten
vesivuodolle. Se lähtee tekstiviestinä ja sähköpostina kaikille kaikkien
aktiivisten yksiköiden yhteyshenkilöille kerralla heidän toiveistaan
riippumatta, ja sen voi näyttää myös
ilmoituksena julkisella sivulla. Lähetyksen sivulla näkyy kunkin henkilön
toimitustila sitä mukaa kuin viestit lähtevät.

## Yksi talous

Yksikön sivulla **Lähetä viesti** kohdassa **Viestit** kirjoittaa viestin
kyseisen yksikön yhteyshenkilöille, oletuksena kunkin ensisijaisella kanavalla.
Samassa osiossa on lista kaikesta, mitä
heille on lähetetty: linkit, muistutukset, laskut ja viestit.

## Liitteet

Viesteihin ja uutiskirjeisiin voi liittää tiedostoja, esimerkiksi
vuosikokouksen esityslistan: PDF-tiedostoja, kuvia ja toimisto-ohjelmien
asiakirjoja. Sähköpostin vastaanottajat saavat ne liitteinä; tekstiviestin
vastaanottajat saavat tekstiviestin loppuun lyhyen linkin.

## Uutiskirjeet

Uutiskirjeet lähetetään vain sähköpostilla ja vain niille, jotka ovat
antaneet suostumuksensa. Henkilön vastaus tallennetaan hänen sivulleen
antoajankohtineen ja -tapoineen, ja jäsenet voivat muuttaa sitä omalla
sivullaan. **Lähetykset > Uusi uutiskirje** kirjoittaa ja lähettää
uutiskirjeen. Jokaisen uutiskirjeen lopussa on linkki tilauksen
peruuttamiseen.

Palveluviestit ja hälytykset eivät ole uutiskirjeitä: ne koskevat omaa
palveluasi, joten ne tavoittavat kaikki.
