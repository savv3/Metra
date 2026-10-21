# Säkerhetskopior och återställning

Metra sparar **säkerhetskopior**: kopior av hela registret och alla
uppladdade filer.

## När en säkerhetskopia tas

- varje natt,
- när en ny version av Metra startar, innan den ändrar något,
- före en CSV-import, före borttagning av en enhetstyp eller ett fält, och före en återställning,
- när en administratör klickar på **Ta en säkerhetskopia nu** under **Inställningar > Säkerhetskopior**.

Om säkerhetskopian före en riskabel åtgärd inte kan tas, stoppas åtgärden.

Varje säkerhetskopia sparas i 7 dagar, därefter en per vecka i 4 veckor och
en per månad i ett år. Säkerhetskopior som tagits manuellt finns kvar tills
en administratör tar bort dem. När installationen är inställd för det
skickas varje säkerhetskopia också, krypterad, till en lagring utanför
servern.

## Sidan Säkerhetskopior

**Inställningar > Säkerhetskopior** visar varje säkerhetskopia med när och
varför den togs, Metras version, storleken och om den finns på den här
servern, externt eller båda. Senaste problem visas överst.

## Att återställa en säkerhetskopia

En återställning gör hela registret och alla filer som de var när
säkerhetskopian togs. Bara administratörer kan göra det.

1. Öppna **Inställningar > Säkerhetskopior** och välj **Återställ…** bredvid säkerhetskopian.
2. Skriv in ditt lösenord eller din tvåfaktorskod igen.
3. Kontrollera vad som ändras: hur många enheter, personer, avläsningar, meddelanden, fakturor och betalningar det finns nu och i säkerhetskopian. Fakturor som utfärdats och betalningar som registrerats efter säkerhetskopian listas och måste bekräftas separat, eftersom de redan kan finnas i bokföringen.
4. Kryssa i rutan och välj **Återställ den här säkerhetskopian**.

Först tas en säkerhetskopia av uppgifterna som de är nu, så att en
återställning kan ångras genom att återställa den ("Före en återställning"
i listan). Medan återställningen pågår ser alla en kort sida "Tillbaka om en
stund"; det tar oftast mindre än en minut, och du kan behöva logga in på nytt
efteråt. Om något går fel läggs uppgifterna från strax innan tillbaka av sig
själva.

En säkerhetskopia som gjorts av en nyare version av Metra kan inte
återställas. Om appen inte startar alls kan den som sköter servern återställa
en säkerhetskopia från kommandoraden enligt installationsguiden.
