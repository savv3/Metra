# Kom igång

Metra håller ert register över hushåll eller andra enheter och de personer ni
kontaktar, samlar in avläsningar, skickar meddelanden och nyhetsbrev och gör
fakturor.

## Menyn

- **Enheter** och **Personer**: registret. Om ni bara har en enhetstyp används dess eget namn i menyn (till exempel **Stugor**).
- **Avläsningar**: avläsningsomgångar, till exempel den årliga avläsningen av vattenmätare.
- **Fakturor**: faktureringsomgångar, betalningar och påminnelser.
- **Utskick**: meddelanden, brådskande varningar och nyhetsbrev, med leveransstatus.
- **Inställningar**: organisationen, registrets enhetstyper och fält, avläsningstyper, faktureringsinställningar och avgiftsplaner, meddelandemallar, användare och roller, integrationer och säkerhetskopior. Se ”Inställningar” nedan.
- **Hjälp**: de här guiderna. Hjälplänken på varje sida öppnar guiden för just den sidan.

Ditt eget språk, ljust eller mörkt tema och tvåfaktorsinloggning finns i
menyn under ditt namn.

**Klockan** bredvid ditt namn visar hur många aviseringar du inte har läst,
till exempel en misslyckad säkerhetskopia eller ändringar som medlemmar
skickat in. Se [Aviseringar](/help/notifications/).

## Att ställa in en ny installation

Den första administratören som loggar in leds genom **installationsguiden**,
en sida i taget:

1. **Organisation**: namn, FO-nummer, adress och de offentliga kontaktuppgifterna.
2. **Språk**: ditt eget språk. Var och en väljer sitt eget.
3. **Logotyp**: visas på den offentliga sidan, medlemmarnas sidor, i brev och på fakturor.
4. **Enheter och fält**: enhetstyper och deras fält. **Lägg till exemplet vattenandelslag** ger hushåll med fastighetsbeteckning, mätarnummer och andra fält, och en vattenmätare som läses av varje år.
5. **E-post och sms**: visar vad som är inställt och skickar ett test till dig.
6. **Fakturor**: bankkonto, betalningsvillkor, moms och numrering.
7. **Bjud in styrelsen**: var och en får ett e-postmeddelande med en länk för att välja lösenord.

Alla steg kan hoppas över, och inget ändras förrän ett steg sparas.
Administratörer kan köra guiden igen under **Inställningar >
Installationsguide**.

## Inställningar

**Inställningar** i menyn samlar allt som en administratör ställer in,
ordnat efter uppgift:

- **Organisation**: namn, FO-nummer, kontaktuppgifter, logotyp och den offentliga sidan.
- **Register**: enhetstyper och deras fält, fält för personer och taggar.
- **Avläsningar**: avläsningstyper.
- **Fakturering**: faktureringsinställningar och avgiftsplaner. Avgiftsraderna ändras i själva avgiftsplanen.
- **Meddelanden**: meddelandemallar, anslag på den offentliga sidan och samtycken till nyhetsbrev.
- **Användare och roller**: vem som kan logga in och vad varje roll får göra.
- **Integrationer**: API-klienter, webhooks och andra kopplingar, när de är påslagna.
- **Säkerhetskopior** och **Installationsguide**.

Var och en ser bara det som den egna rollen får ändra, och menyn visar
Inställningar bara för dem som kan ändra något där.

## Medlemmar

Medlemmar loggar aldrig in. De får en personlig länk med sms, e-post eller
brev, där de anger sin avläsning och rättar sina kontaktuppgifter. Se
[Avläsningar](/help/readings/).

## Tillägg

Tillägg ger fler funktioner, till exempel sms via 46elks eller mötesprotokoll.
En admin ser tilläggen som är installerade på servern under **Inställningar >
Tillägg** och slår på eller av varje tillägg med **Slå på** och **Slå av**. Ett
tillägg som är avslaget försvinner direkt från menyn och sidorna, och dess data
sparas till nästa gång det slås på. Tillägg med inställningar, till exempel en
API-nyckel, eller med egna inställningssidor, till exempel mötestilläggets
mallar för föredragningslistor, har en knapp **Inställningar** där. De egna
sidorna finns också på sidan Inställningar, under det avsnitt de hör till. Ett sparat lösenord eller en
sparad nyckel visas aldrig igen: lämna fältet tomt för att behålla det, eller
skriv in ett nytt. En inställning som är grånad är angiven på servern och kan
inte ändras i appen. Nya tillägg installeras på servern, se
installationsanvisningen.

För att skicka sms öppnar du **Inställningar** för tillägget **46elks SMS**,
fyller i API-användarnamnet och lösenordet från ditt konto hos 46elks och
avsändaren som visas i telefonen (högst 11 bokstäver och siffror), och
skickar ett test-sms från samma sida eller installationsguiden. Med **Testläge** kontrollerar
46elks meddelandena utan att skicka dem.
