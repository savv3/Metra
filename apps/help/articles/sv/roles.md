# Användare, roller och tvåfaktorsinloggning

## Roller

Alla som arbetar i Metra har ett konto med en roll:

| Roll | Kan |
| --- | --- |
| Admin | Allt, också Inställningar |
| Styrelse | Se och ändra enheter, personer, kontakter och taggar, mata in avläsningar, skriva till ett hushåll, se historiken |
| Kassör | Se registret och sköta fakturering och betalningar |
| Läsbehörighet | Se registret |

En administratör bjuder in användare under **Inställningar > Användare och
roller > Användare > Lägg till användare**, eller med installationsguidens steg
**Bjud in styrelsen**. Du anger namn, e-post och roll, inget lösenord: den nya
användaren får ett e-postmeddelande med en länk där hen väljer sitt eget
lösenord, och en administratör slår sedan på tvåfaktorsinloggning. Länken
fungerar i några dagar och bara en gång.

Om länken har slutat fungera markerar du användaren i listan, väljer åtgärden
**Skicka en ny inbjudningslänk** och trycker **Kör**. Är e-posten inte
inställd visas länken en gång på sidan, så att du kan skicka den själv.

## Tvåfaktorsinloggning

Tvåfaktorsinloggning skyddar registret med en kod från en
autentiseringsapp i mobilen, som Aegis, Google Authenticator eller
1Password. Alla användare måste slå på den innan de kan använda Metra,
eftersom alla roller ser medlemmarnas personuppgifter. (En installation kan
ställas in så att bara administratörer måste använda den.)

Slå på den under **Mitt konto** i menyn under ditt namn och välj **Slå på
tvåfaktorsinloggning**. Skanna QR-koden med appen, skriv in den sexsiffriga
koden och spara reservkoderna på ett säkert ställe: med dem kommer du in om
du tappar mobilen. Därefter ber varje inloggning om en kod.

Vissa åtgärder, som att återställa en säkerhetskopia, ber om ditt lösenord
eller din kod igen även när du är inloggad.

## Historik

Varje ändring i registret, varje rolländring och varje öppnad enhets- eller
personsida sparas. Admin och Styrelse ser historiken längst ner på enhets-
och personsidorna.
