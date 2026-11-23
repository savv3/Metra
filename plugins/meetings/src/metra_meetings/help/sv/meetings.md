# Möten och protokoll

Med tillägget för möten kallar föreningen till, håller och protokollför sina
möten i Metra: årsmöten, extra möten och styrelsemöten. Justerade protokoll
sparas som föreningens handlingar och medlemmarna kan läsa dem på sin
personliga sida.

Tillägget slås på av den som sköter installationen
(`METRA_PLUGINS=meetings`). Därefter syns **Möten** under Kommunikation i huvudmenyn.

## Vem kan göra vad

- **Admin** kan göra allt, också ta bort ett möte som inte är justerat.
- **Styrelse** bereder möten, för närvaron och skriver protokollet.
- **Kassör** och **Läsbehörighet** kan se möten och deras protokoll.
- Mötets **protokolljusterare** justerar protokollet. Vem som helst med
  inloggning kan vara justerare, oberoende av roll.

## Bered mötet

1. Under **Möten**, klicka på **Nytt möte**. Välj typ av möte, skriv en
   rubrik, datum, tid och plats och annat som kallelsen ska nämna. Under
   **Föredragningslista** får mötet föredragningslistan från mallen för sin
   typ av möte (se nedan), en annan mall eller en tom föredragningslista.
2. Kryssa i **En röst per enhet** om varje enhet (hushåll eller medlem) har
   en röst. Annars har alla närvarande en röst.
3. Välj ordförande, sekreterare och protokolljusterare om ni redan vet vilka
   de är. Du kan ändra dem tills protokollet är justerat.
4. Kontrollera föredragningslistan och lägg till ärenden med **Lägg till ett
   ärende**, ett ärende (en paragraf, §) i taget. Ärendena visas i ordning
   efter sitt ordningsnummer; beskrivningen syns på föredragningslistan.

## Mallar för föredragningslistor

En mall för föredragningslista är den vanliga föredragningslistan för en typ
av möte. Metra börjar med en för årsmöten och en för styrelsemöten, med de
ärenden som föreningslagen förutsätter; anpassa dem till era stadgar. Du
hittar dem med **Mallar för föredragningslistor** på sidan Möten, under
**Inställningar** (**Organisation**) eller under **Inställningar > Tillägg >
Möten > Inställningar**.

Skriv ett ärende per rad, i ordning. **För** anger vilken typ av möte som
börjar med mallen; lämna det tomt för en mall som du väljer själv, till
exempel för en talkodag. Att ändra en mall ändrar inte möten som redan har
lagts till. Admin och styrelsen ändrar mallarna; de andra kan se dem.

## Kalla till mötet

Klicka på **Skicka kallelser**. Ett nytt meddelande öppnas med kallelsen
skriven, föredragningslistan bifogad som pdf och en kalenderfil bifogad, så
att mottagarna kan lägga in mötet i sin kalender med ett klick. Det är
inställt på att gå med e-post; välj vem som får det (till exempel alla, bara
varje enhets huvudkontakt eller de som är taggade som styrelse), kontrollera
texten och skicka som vilket meddelande som helst. Om du också väljer sms får
mottagare med sms en länk till filerna. När kallelsen är skickad markeras
mötet som kallat. Du kan skicka fler kallelser senare, till exempel till
någon som blev bortglömd.

För att skicka meddelanden till alla behövs rätten att skicka meddelanden,
som bara administratörer har om de inte ger den till styrelsen.

## Påminnelser

**Påminnelse, dagar före** på mötet anger när alla som fått kallelsen får en
påminnelse, med föredragningslistan och kalenderfilen igen. Den är 3 dagar om
du inte ändrar den; lämna fältet tomt för ingen påminnelse. Påminnelsen går
ut en gång, på morgonen den dagen, på samma sätt som kallelsen. Den hoppas
över om själva kallelsen gick ut samma dag eller senare. Vill du påminna
tidigare klickar du på **Skicka en påminnelse nu** under **Kallelser och
påminnelser** på mötets sida.

Om du ändrar datum, tid eller plats efter att kallelserna gått ut, erbjuder
mötets sida **Skicka en uppdaterad kallelse**. Alla som är kallade får då de
nya uppgifterna och en kalenderfil som flyttar mötet i deras kalender. Ett
möte som flyttats får sin påminnelse på nytt före det nya datumet.

Varje kallelse, påminnelse och uppdatering listas på mötets sida och under
**Meddelanden**, med vem som fick den.

## Under mötet

Öppna **Närvaro** och lägg till de närvarande från registret. När mötet har
en röst per enhet får den första närvarande för en enhet dess röst och de
andra ingen; skriv in en fullmakt om någon röstar för en annan enhet. Sidan
visar antalet närvarande och det sammanlagda antalet röster.

Efteråt, klicka på **Skriv protokollet** och skriv vad som diskuterades och
beslutades under varje ärende. Klicka sedan på **Markera som hållet**.

## Justera protokollet

När mötet är markerat som hållet ser varje protokolljusterare
**Granska och justera protokollet** på mötets sida och på sidan Möten. De
läser protokollet (också som pdf) och klickar på **Justera protokollet**.

Om protokollet ändras innan alla har justerat, tas de justeringar som
gjorts hittills bort, så att justerarna alltid godkänner den slutliga
texten. När alla justerare har justerat är protokollet **justerat** och kan
inte längre ändras. Ett fel som upptäcks senare rättas i protokollet från
ett senare möte.

## Vad medlemmarna ser

Justerade protokoll från möten där **Visa det justerade protokollet för
medlemmarna** är ikryssat listas på varje medlems personliga sida, det
senaste först, och öppnas som pdf. Protokoll som inte är justerade visas
aldrig för medlemmarna.
