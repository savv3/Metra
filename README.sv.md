[English](README.md) · **Svenska** · [Suomi](README.fi.md)

# Metra

En enkel webbapp som du kan driva på egen server, för små företag och
föreningar som vill hålla ordning på sina medlemmar och kunder. Fri och
öppen källkod under MIT-licensen.

Metra har ett register över hushåll eller andra enheter och deras kontakter,
samlar in årliga avläsningar som vattenmätare, skickar sms, e-post och
akuta meddelanden, skickar nyhetsbrev och gör fakturor. Den körs på en liten
server med Docker och säkerhetskopierar sig själv externt varje natt.
Registertyper och fält ställs in av en administratör, så inget är bundet
till en viss sorts organisation.

## Vem passar Metra för?

Metra passar alla som har en lista över hushåll eller medlemmar, fakturerar
dem en eller två gånger om året och ibland snabbt behöver nå alla. Den byggdes
först för ett vattenandelslag med ungefär 50 hushåll. Andra som passar bra:

- **Vägföreningar och väglag**, med andelar per fastighet, en årsavgift och
  meddelanden om avstängda vägar.
- **Fiber- och byanätsföreningar**, med anslutningar per hushåll, månads-
  eller årsavgifter och meddelanden om avbrott.
- **Bostadsrättsföreningar och små bostadsaktiebolag**, med lägenheter som
  enheter, avgifter och meddelanden om vattenavstängning eller underhåll.
- **Hamn- och båtföreningar**, med båtplatser som enheter, säsongsavgifter
  och stormvarningar.
- **Koloni- och stugföreningar**, med lotter, årsavgifter och vatten som
  slås på eller av efter säsong.
- **Jaktlag och fiskelag**, med medlemmar, andelar och avgifter.
- **Idrottsföreningar och små ideella föreningar**, med medlemmar,
  medlemsavgifter och nyhetsbrev.
- **Små serviceföretag**, till exempel sotare, slamtömning eller snöplogning,
  med kunder per adress, årliga fakturor och besöksaviseringar.

## Funktioner

- Ett register över enheter, personer och kontakter som går att anpassa, med
  import och export av CSV
- Roller, tvåstegsinloggning för personalen och en logg över alla ändringar
- Årliga avläsningar, som styrelsen eller medlemmarna själva matar in
- Självbetjäning för medlemmar via personliga länkar, utan lösenord
- Sms (46elks) och e-post, akuta meddelanden och en offentlig sida med
  aktuella meddelanden
- Nyhetsbrev med sparat samtycke och avregistrering med ett klick
- Fakturering med finska referensnummer, bankstreckkod, QR-kod för
  betalning, kreditnotor och betalningspåminnelser
- Säkerhetskopior varje natt, krypterade och kopierade till S3, SFTP eller
  FTPS
- Aviseringar under en klocka för personalen, till exempel en misslyckad
  säkerhetskopia eller sms som inte kom fram, och var och en väljer vad den får
- Möten (ett tillägg att slå på): kallelse med föredragningslista, närvaro
  och röster, protokoll som justeras av protokolljusterarna och visas för
  medlemmarna
- Bokföring (ett tillägg att slå på): dubbel bokföring enligt den finska
  bokföringslagen, med numrerade verifikat och kvitton, dagbok och huvudbok
- Tillägg (plugins), och svenska, engelska och finska i appen (den finska
  är maskinöversatt och ogranskad, och appen säger det)

**Status:** tidig utveckling. Registret, avläsningar, självbetjäning,
meddelanden, nyhetsbrev och fakturering finns; se
[docs/architecture.md](docs/architecture.md) (på engelska) för planen och
vad som kommer härnäst.

## Kom igång

```sh
cp .env.example .env    # ange sedan METRA_DOMAIN och METRA_SECRET_KEY
docker compose up -d --build
```

Den övriga dokumentationen finns på engelska:

- [INSTALL.md](INSTALL.md): installation, inställningar, e-post och sms,
  säkerhetskopior och utveckling
- [Användarguide](docs/user-guide.md): avläsningar, självbetjäning,
  meddelanden, nyhetsbrev, fakturering, import och roller
- [Flera organisationer på en server](docs/multiple-organisations.md)
- [Tillägg](docs/plugins.md)
- [REST-API](docs/api.md): tillägget `api`, för andra system med tokens
- [AGENTS.md](AGENTS.md): regler för den som bidrar med kod
- [SECURITY.md](SECURITY.md): rapportera ett säkerhetsproblem

## Licens

MIT, se [LICENSE](LICENSE).
