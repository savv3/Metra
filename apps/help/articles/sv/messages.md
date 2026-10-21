# Meddelanden och nyhetsbrev

## E-postinställningar

En administratör bestämmer hur e-post skickas under **Inställningar > E-post**,
som också är ett steg i installationsguiden. Välj **SMTP** för att skicka via
föreningens eget e-postkonto: ange **E-postserver**, **Port**, **Kryptering**,
**Användarnamn** och **Lösenord** som din e-postleverantör ger dig. Ett tillägg
kan i stället erbjuda en sändningstjänst. Ange **Avsändaradress** som
medlemmarna ser, och en **Svarsadress** om svaren ska gå någon annanstans. All
e-post från Metra skickas på det här sättet, också inloggningskoder och
inbjudningar. **Skicka testmejl** kontrollerar att det fungerar. Ett sparat
lösenord visas aldrig igen: lämna fältet tomt för att behålla det. Ett fält som
är nedtonat är inställt på servern och kan inte ändras i appen.

### Mailgun

Tillägget **Mailgun** skickar i stället e-posten via Mailgun. Fyll i
**Avsändardomän**, **API-nyckel** och **Region** under **Inställningar >
Tillägg > Mailgun**, och välj sedan **Mailgun** under **Inställningar >
E-post**. När **Signeringsnyckel för webhooks** är ifylld och webhooken är
tillagd hos Mailgun (se installationsanvisningen) visar varje meddelandes
status om det levererades. När ett e-postmeddelande studsar markeras
meddelandet som misslyckat, och personens sida visar **Studsade** bredvid
adressen, med Mailguns orsak. Kontrollera adressen med personen och rätta den;
en ny adress tar bort markeringen. Ett meddelande som mottagaren markerat som
skräppost noteras på meddelandet.

## Att skriva till många hushåll

**Utskick > Nytt meddelande** skriver ett meddelande till alla, till enheter
eller personer med en tagg, till enheter av en typ, eller till enheterna i listan du har filtrerat
(**Skicka ett meddelande till de här enheterna** under enhetslistan). Välj om
det går till alla kontakter för varje enhet eller bara huvudkontakten, och
hur. Det vanliga valet är **Enligt var och ens önskade kanal**: de som vill ha
e-post får e-post och de som vill ha sms får sms, eller det andra om de saknar
adress för det (eller om det misslyckas). De här meddelandena skickas inte som
brev, så de som vill ha post får sms, eller annars e-post. Önskad kanal ställs
in på varje persons sida. Under **Andra alternativ** kan du i stället välja,
oavsett vad var och en önskar:

- **Endast SMS** eller **Endast e-post**,
- **SMS, eller e-post till dem som saknar telefon**, eller
- **Både SMS och e-post**.

En tagg når kontakterna för de enheter som har taggen och de personer som
själva har den, även om de inte är kontakt för någon enhet. Om ingen
motsvarar valen säger kontrollsidan varför, till exempel att den taggade
enheten ännu saknar kontakter.

Med önskad kanal skriver du både sms-texten och e-postens ämne, eftersom
mottagarna kan få vilket som helst. Formuläret visar bara de texter som det
valda sättet behöver. Platshållare
som `{first_name}` och `{unit}` fylls i för varje person, och en räknare visar
hur många sms texten blir. Innan något skickas visar en kontrollsida hur
många som får sms och e-post, och vilka som inte kan nås, så att någon kan
ringa dem.

## Brådskande varningar

**Brådskande varning** (den röda knappen) är för avbrott, som en vattenläcka.
Den går med sms och e-post till alla kontakter för alla aktiva enheter på en
gång, oavsett vad de önskar, och kan också visas som ett anslag på den offentliga sidan.
Utskickets sida visar varje persons leveransstatus medan det pågår.

## Ett hushåll

På en enhets sida skriver **Skicka meddelande** under **Meddelanden** till
den enhetens kontakter, i första hand via var och ens önskade kanal. Samma avsnitt visar allt de har fått: länkar,
påminnelser, fakturor och meddelanden.

## Bilagor

Meddelanden och nyhetsbrev kan ha filer med sig, till exempel kallelsen till
årsmötet: PDF, bilder och kontorsdokument. Den som får e-post får filerna
bifogade; den som får sms får en kort länk i slutet av meddelandet.

## Nyhetsbrev

Nyhetsbrev går bara med e-post, och bara till personer som har sagt ja. En
persons svar sparas på personens sida, med när och hur det gavs, och
medlemmar kan ändra det på sin egen sida. **Utskick > Nytt nyhetsbrev**
skriver och skickar ett. Varje nyhetsbrev slutar med en länk för att avsluta
prenumerationen.

Servicemeddelanden och varningar är inte nyhetsbrev: de gäller er egen
tjänst och når därför alla.
