# Fakturering

## Inställningar och avgifter

Under **Inställningar > Fakturering > Faktureringsinställningar** ställer en administratör
in bankkonto, betalningsvillkor, moms, numrering och texterna på fakturorna.
**Inställningar > Fakturering > Avgiftsplaner** anger vad enheterna betalar: fasta avgifter
och avgifter per enhet av en avläsning (som per m³), om man vill i
prisnivåer, var och en med sin momssats.

## Att göra fakturor

**Fakturor > Faktureringsomgångar > Ny faktureringsomgång** väljer period,
avgiftsplaner och avläsningsomgång och gör ett fakturautkast för varje
enhet, adresserat till faktureringskontakten eller ägaren. Utkast där
avläsningen saknas eller ser konstig ut markeras **Kontrollera**: mata in
avläsningen och bygg om utkastet, eller redigera raderna.

**Utfärda alla kontrollerade utkast** på omgångens sida, eller **Utfärda
fakturan** på ett enskilt utkast, ger varje faktura dess nummer och datum och
låser den. En utfärdad faktura ändras aldrig: ett fel rättas med en
kreditnota (**Gör en kreditnota** på fakturan), som kan kreditera hela eller
en del av fakturan.

## Utskick

Utfärdade fakturor skickas med e-post som PDF med referensnummer, bankens
streckkod och en QR-kod för betalning. De som saknar e-post, eller vill ha
post, listas för utskrift, och **PDF med fakturor som skickas per post** på
omgångens sida ger deras brev i en fil. Medlemmarna hittar också sina
fakturor på sin egen sida.

## Betalningar och påminnelser

Registrera betalningar på fakturans sida med **Registrera en betalning**,
helt eller i delar. En faktura är **Betald** när inget återstår. Betalningar
ändras eller tas aldrig bort; för att ångra en registrerar du samma belopp
som en negativ betalning.

**Fakturor > Förfallen** visar obetalda fakturor efter förfallodagen.
**Skicka påminnelser till de valda** skickar en betalningspåminnelse via
var och ens önskade kanal (e-post eller sms, eller den andra om de saknar
adress för den), eller som brev till dem som vill ha post eller saknar båda,
med påminnelseavgiften om en sådan är inställd och
minst 14 dagar att betala.

## Bankfiler

I stället för att registrera varje betalning för hand kan du ladda ner bankens
fil över inkommande betalningar från din nätbank och ladda upp den under
**Fakturor > Bankfiler**. Metra läser XML-filer enligt ISO 20022: camt.054,
filen med referensbetalningar, och camt.053, kontoutdraget. Varje betalning
vars referensnummer hör till en faktura och som betalar exakt det som återstår
registreras på fakturan. Referensnumret kan vara det finländska eller RF-numret,
med eller utan mellanslag.

Betalningar utan referensnummer eller med ett okänt, delbetalningar och för
stora betalningar markeras **Att kontrollera**: registrera dem för hand på rätt
faktura. Utbetalningar visas men matchas inte. Om du laddar upp samma fil två
gånger ändras inget, och en betalning som redan har importerats från en
tidigare fil (till exempel filen med referensbetalningar före månadens
kontoutdrag) hoppas över. Varje importerad fil visar sina rader och vad som
hände med var och en.

## Till bokföraren

**Exportera som CSV** under fakturalistan ger alla utfärdade fakturor med
summor, moms, krediteringar, betalningar och vad som återstår. **Exportera
betalningar** ger betalningar och påminnelseavgifter för en period.
