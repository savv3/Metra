# Registret

Registret innehåller **enheter** (till exempel hushåll, fastigheter eller
båtplatser) och **personer**. En person kopplas till en enhet som ägare,
faktureringskontakt eller annan kontakt, och en person kan vara kontakt för
flera enheter.

## Enhetstyper och fält

En administratör ställer in sorterna av enheter under **Inställningar >
Enhetstyper**, var och en med egna fält, som fastighetsbeteckning eller
mätarnummer. Fält kan också läggas till för alla personer. När en enhetstyp
eller ett fält tas bort tas först en säkerhetskopia, eftersom uppgifterna då
försvinner från alla enheter.

Ge enhetstypen också ett pluralnamn (till exempel "Stuga" och "Stugor"). Om
ni bara har en enhetstyp används dess eget namn i menyn, i rubrikerna och på
knapparna i stället för "Enheter", och listan saknar typfilter och typkolumn.
Med flera typer behålls de allmänna orden.

## Att arbeta med enheter och personer

- **Enheter** och **Personer** visar registret. Sök och filtrera listan och använd sedan **Exportera som CSV** för att ladda ner det du ser.
- **Lägg till** en enhet eller person med knappen ovanför listan. På en enhets sida lägger du till en befintlig person som kontakt eller skapar en ny.
- **Arkivera** i stället för att ta bort: en arkiverad enhet eller person sparas, men försvinner ur listorna och utskicken.
- **Taggar** grupperar enheter, till exempel en by eller en ledningssträcka, och meddelanden kan skickas till alla med en viss tagg.

Varje ändring, och varje gång någon öppnar en enhets eller persons sida,
sparas i historiken. Admin och Styrelse ser den längst ner på sidan.

## Import från ett kalkylblad

**Enheter > Importera CSV** tar in enheter av en typ, var och en med högst en kontakt:

1. Välj enhetstyp och fil. Spara filen från Excel som *CSV UTF-8*.
2. Kontrollera vilken kolumn som hör till vilket fält. Kolumner med matchande namn väljs åt dig.
3. Granska förhandsvisningen. Varje rad är markerad OK, överhoppad (enheten finns redan) eller visas med sina fel. Inget importeras så länge någon rad har fel.

Personer matchas mot dem som redan finns i registret via e-post och sedan
telefon, så ingen läggs till två gånger. En säkerhetskopia tas före
importen.

## Den offentliga sidan

Besökare som inte är inloggade ser organisationens offentliga sida: namn,
logotyp, en kort beskrivning och kontaktuppgifter. En administratör redigerar
den under **Inställningar > Organisation**. **Anslag**, som "Vattnet avstängt
till kl. 18", visas på den offentliga sidan och på medlemmarnas sidor.
