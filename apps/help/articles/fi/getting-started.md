# Aloitus

Metra pitää kirjaa taloudistasi tai muista yksiköistä ja yhteyshenkilöistä,
kerää lukemat, lähettää viestejä ja uutiskirjeitä sekä tekee laskut.

## Valikko

- **Yksiköt** ja **Henkilöt**: rekisteri. Jos yksikkötyyppejä on vain yksi, valikko käyttää sen omaa nimeä (esimerkiksi **Mökit**).
- **Lukemat**: lukemakierrokset, esimerkiksi vuosittainen vesimittarin luenta.
- **Laskut**: laskutusajot, maksut ja muistutukset.
- **Lähetykset**: viestit, kiireelliset hälytykset ja uutiskirjeet toimitustiloineen.
- **Asetukset**: organisaatio, rekisterin yksikkötyypit ja kentät, lukematyypit, laskutusasetukset ja maksusuunnitelmat, viestipohjat, käyttäjät ja roolit, integraatiot ja varmuuskopiot. Katso ”Asetukset” alempana.
- **Ohje**: nämä oppaat. Jokaisen sivun Ohje-linkki avaa kyseisen sivun oppaan.

Oma kielesi, vaalea tai tumma teema ja kaksivaiheinen tunnistautuminen ovat
valikossa nimesi alla.

Nimesi vieressä oleva **kello** näyttää, montako ilmoitusta et ole lukenut,
esimerkiksi epäonnistuneen varmuuskopion tai jäsenten lähettämät muutokset.
Katso [Ilmoitukset](/help/notifications/).

## Uuden asennuksen käyttöönotto

Ensimmäinen kirjautuva ylläpitäjä käy läpi **käyttöönoton ohjatun
toiminnon** sivu kerrallaan:

1. **Organisaatio**: nimi, Y-tunnus, osoite ja julkiset yhteystiedot.
2. **Kieli**: oma kielesi. Jokainen valitsee omansa.
3. **Logo**: näkyy julkisella sivulla, jäsenten sivuilla, kirjeissä ja laskuissa.
4. **Yksiköt ja kentät**: yksikkötyypit ja niiden kentät. **Lisää vesiosuuskunnan esimerkki** luo taloudet, joilla on kiinteistötunnus, mittarin numero ja muita kenttiä, sekä vuosittaisen vesimittarin.
5. **Sähköposti ja tekstiviesti**: näyttää, mitä on otettu käyttöön, ja lähettää sinulle testiviestin.
6. **Laskut**: pankkitili, maksuehdot, ALV ja numerointi.
7. **Kutsu hallitus**: jokainen saa sähköpostiviestin, jossa on linkki salasanan valitsemiseen.

Minkä tahansa vaiheen voi ohittaa, eikä mikään muutu, ennen kuin vaihe
tallennetaan. Ylläpitäjät voivat ajaa ohjatun toiminnon uudelleen kohdassa
**Asetukset > Käyttöönotto**.

## Asetukset

Valikon **Asetukset** kokoaa kaiken, minkä ylläpitäjä määrittää, tehtävien
mukaan ryhmiteltynä:

- **Organisaatio**: nimi, Y-tunnus, yhteystiedot, logo ja julkinen sivu.
- **Rekisteri**: yksikkötyypit ja niiden kentät, henkilöiden kentät ja tunnisteet.
- **Lukemat**: lukematyypit.
- **Laskutus**: laskutusasetukset ja maksusuunnitelmat. Maksusuunnitelman maksurivejä muokataan itse suunnitelmassa.
- **Viestit**: viestipohjat, ilmoitukset julkisella sivulla ja uutiskirjeen suostumukset.
- **Käyttäjät ja roolit**: kuka voi kirjautua sisään ja mitä kukin rooli saa tehdä.
- **Integraatiot**: API-asiakkaat, webhookit ja muut yhteydet, kun ne ovat käytössä.
- **Varmuuskopiot** ja **Käyttöönotto**.

Kukin näkee vain sen, mitä oma rooli saa muuttaa, ja valikko näyttää
Asetukset vain niille, jotka voivat muuttaa siellä jotakin.

## Jäsenet

Jäsenet eivät koskaan kirjaudu sisään. He saavat henkilökohtaisen linkin
tekstiviestillä, sähköpostilla tai kirjeellä, ja sen kautta he ilmoittavat
lukemansa ja korjaavat yhteystietonsa. Katso [Lukemat](/help/readings/).

## Lisäosat

Lisäosat tuovat uusia toimintoja, kuten tekstiviestit 46elksin kautta tai
kokouspöytäkirjat. Ylläpitäjä näkee palvelimelle asennetut lisäosat kohdassa
**Asetukset > Lisäosat** ja ottaa kunkin käyttöön tai pois käytöstä
painikkeilla **Ota käyttöön** ja **Poista käytöstä**. Pois käytöstä oleva
lisäosa katoaa valikosta ja sivuilta heti, ja sen tiedot säilyvät, kunnes se
otetaan taas käyttöön. Lisäosilla, joilla on asetuksia, kuten API-avain, on
siellä **Asetukset**-painike. Tallennettua salasanaa tai avainta ei näytetä
enää koskaan: jätä kenttä tyhjäksi, jos haluat säilyttää sen, tai anna uusi.
Harmaana oleva asetus on asetettu palvelimella, eikä sitä voi muuttaa
sovelluksessa. Uusi lisäosa asennetaan palvelimella, katso asennusohje.

Tekstiviestejä varten avaa **46elks SMS** -lisäosan **Asetukset**, anna
46elks-tilisi API-käyttäjätunnus ja -salasana sekä puhelimessa näkyvä
lähettäjä (enintään 11 kirjainta ja numeroa) ja lähetä testiviesti
käyttöönotto-oppaasta. **Testitilassa** 46elks tarkistaa viestit lähettämättä
niitä.
