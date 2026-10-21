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

Att återställa en säkerhetskopia från sidan Säkerhetskopior kommer i nästa
version: en administratör väljer en säkerhetskopia, ser vad den innehåller
och vad som skulle tas bort, och bekräftar. Tills dess kan den som sköter
servern återställa en enligt installationsguiden.
