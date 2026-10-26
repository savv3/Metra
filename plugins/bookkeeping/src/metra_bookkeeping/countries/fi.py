"""Finland: the Accounting Act (kirjanpitolaki 1336/1997), the Accounting
Decree (kirjanpitoasetus 1339/1997) and the decree on the financial
statements of small and micro entities (PMA, 1753/2015).

The charts follow the usual Finnish numbering: 1 assets, 2 equity and
liabilities, 3 income, 4 to 9 expenses. They are starting points; the
treasurer adds, renames and retires accounts in the app. From general
knowledge of the law, not legal advice.
"""

from django.utils.translation import gettext_lazy as _

from . import Account, Chart

CODE = "fi"
NAME = _("Finland")

# A financial year is 12 months; the first one, or one whose dates change,
# may be shorter or longer, up to 18 months (KPL 1:4).
YEAR_MONTHS = 12
FIRST_YEAR_MONTHS = (1, 18)

ASSET, LIABILITY, EQUITY, INCOME, EXPENSE = "asset", "liability", "equity", "income", "expense"


def _a(number, kind, fi, sv, en):
    return Account(number, kind, {"fi": fi, "sv": sv, "en": en})


ASSETS = [
    _a("1120", ASSET, "Koneet ja kalusto", "Maskiner och inventarier", "Machinery and equipment"),
    _a(
        "1160",
        ASSET,
        "Rakennukset ja rakennelmat",
        "Byggnader och konstruktioner",
        "Buildings and structures",
    ),
    _a("1300", ASSET, "Pitkäaikaiset sijoitukset", "Långfristiga placeringar", "Investments"),
    _a(
        "1500",
        ASSET,
        "Aineet ja tarvikkeet",
        "Material och förnödenheter",
        "Materials and supplies",
    ),
    _a("1700", ASSET, "Myyntisaamiset", "Kundfordringar", "Trade receivables"),
    _a("1760", ASSET, "Siirtosaamiset", "Resultatregleringar (aktiva)", "Accrued income"),
    _a("1763", ASSET, "Arvonlisäverosaaminen", "Momsfordran", "VAT receivable"),
    _a("1790", ASSET, "Muut saamiset", "Övriga fordringar", "Other receivables"),
    _a("1900", ASSET, "Käteisvarat", "Kassa", "Cash"),
    _a("1910", ASSET, "Pankkitili", "Bankkonto", "Bank account"),
    _a("1920", ASSET, "Säästötili", "Sparkonto", "Savings account"),
]

LIABILITIES = [
    _a(
        "2610",
        LIABILITY,
        "Lainat rahoituslaitoksilta",
        "Lån från kreditinstitut",
        "Loans from credit institutions",
    ),
    _a("2870", LIABILITY, "Saadut ennakot", "Erhållna förskott", "Advances received"),
    _a("2871", LIABILITY, "Ostovelat", "Leverantörsskulder", "Trade payables"),
    _a("2920", LIABILITY, "Muut velat", "Övriga skulder", "Other liabilities"),
    _a("2939", LIABILITY, "Arvonlisäverovelka", "Momsskuld", "VAT payable"),
    _a("2960", LIABILITY, "Siirtovelat", "Resultatregleringar (passiva)", "Accrued expenses"),
]

EXPENSES = [
    _a(
        "4000",
        EXPENSE,
        "Aineet ja tarvikkeet",
        "Material och förnödenheter",
        "Materials and supplies",
    ),
    _a("4400", EXPENSE, "Ostetut palvelut", "Köpta tjänster", "Purchased services"),
    _a("5000", EXPENSE, "Palkat ja palkkiot", "Löner och arvoden", "Wages and fees"),
    _a("5500", EXPENSE, "Henkilösivukulut", "Lönebikostnader", "Social security costs"),
    _a("6800", EXPENSE, "Poistot", "Avskrivningar", "Depreciation"),
    _a("7000", EXPENSE, "Toimitilakulut", "Lokalkostnader", "Premises"),
    _a("7100", EXPENSE, "Sähkö", "El", "Electricity"),
    _a(
        "7200",
        EXPENSE,
        "Korjaukset ja kunnossapito",
        "Reparationer och underhåll",
        "Repairs and maintenance",
    ),
    _a("7400", EXPENSE, "Vakuutukset", "Försäkringar", "Insurance"),
    _a(
        "7500",
        EXPENSE,
        "Kokous- ja edustuskulut",
        "Mötes- och representationskostnader",
        "Meetings and hospitality",
    ),
    _a("7600", EXPENSE, "Toimistokulut", "Kontorskostnader", "Office costs"),
    _a("7610", EXPENSE, "Puhelin ja posti", "Telefon och post", "Phone and postage"),
    _a("7620", EXPENSE, "Tietotekniikkakulut", "IT-kostnader", "IT costs"),
    _a("7650", EXPENSE, "Pankkikulut", "Bankkostnader", "Bank charges"),
    _a(
        "7700",
        EXPENSE,
        "Tilintarkastus ja toiminnantarkastus",
        "Revision och verksamhetsgranskning",
        "Audit fees",
    ),
    _a(
        "7800",
        EXPENSE,
        "Jäsenmaksut muille yhteisöille",
        "Medlemsavgifter till andra organisationer",
        "Membership fees paid",
    ),
    _a("7900", EXPENSE, "Muut kulut", "Övriga kostnader", "Other expenses"),
    _a("8800", EXPENSE, "Korkokulut", "Räntekostnader", "Interest expenses"),
]

# A registered association (yhdistys): the non-profit income statement has
# the association's own activities, fundraising, investments and general
# grants, and the result is a surplus or deficit.
ASSOCIATION = Chart(
    name=_("Association"),
    description=_(
        "For a registered association (yhdistys): activities, fundraising and membership "
        "fees, with a surplus or deficit."
    ),
    accounts=[
        *ASSETS,
        _a("2050", EQUITY, "Rahastot", "Fonder", "Funds"),
        _a(
            "2250",
            EQUITY,
            "Edellisten tilikausien yli-/alijäämä",
            "Över-/underskott från tidigare räkenskapsperioder",
            "Surplus or deficit from previous years",
        ),
        _a(
            "2370",
            EQUITY,
            "Tilikauden yli-/alijäämä",
            "Räkenskapsperiodens över-/underskott",
            "Surplus or deficit for the year",
        ),
        *LIABILITIES,
        _a(
            "3000", INCOME, "Toiminnan tuotot", "Intäkter av verksamheten", "Income from activities"
        ),
        _a("3200", INCOME, "Toiminta-avustukset", "Verksamhetsbidrag", "Grants for activities"),
        _a(
            "3500",
            INCOME,
            "Varainhankinnan tuotot",
            "Medelanskaffningens intäkter",
            "Fundraising income",
        ),
        _a("3510", INCOME, "Jäsenmaksut", "Medlemsavgifter", "Membership fees"),
        _a("3520", INCOME, "Lahjoitukset", "Donationer", "Donations"),
        _a(
            "3600",
            INCOME,
            "Muistutusmaksut",
            "Påminnelseavgifter",
            "Reminder fees",
        ),
        _a("3700", INCOME, "Korkotuotot", "Ränteintäkter", "Interest income"),
        _a("3800", INCOME, "Yleisavustukset", "Allmänna understöd", "General grants"),
        *EXPENSES,
    ],
)

# A cooperative (osuuskunta) such as a water cooperative, or a company: the
# standard income statement with net sales, and a profit or loss.
COOPERATIVE = Chart(
    name=_("Cooperative or company"),
    description=_(
        "For a cooperative (osuuskunta), such as a water cooperative, or a company: net "
        "sales, with a profit or loss."
    ),
    accounts=[
        *ASSETS,
        _a("2000", EQUITY, "Osuuspääoma", "Andelskapital", "Share capital"),
        _a("2050", EQUITY, "Rahastot", "Fonder", "Funds"),
        _a(
            "2250",
            EQUITY,
            "Edellisten tilikausien voitto/tappio",
            "Vinst/förlust från tidigare räkenskapsperioder",
            "Profit or loss from previous years",
        ),
        _a(
            "2370",
            EQUITY,
            "Tilikauden voitto/tappio",
            "Räkenskapsperiodens vinst/förlust",
            "Profit or loss for the year",
        ),
        *LIABILITIES,
        _a("3000", INCOME, "Myynti", "Försäljning", "Sales"),
        _a(
            "3600",
            INCOME,
            "Muistutusmaksut",
            "Påminnelseavgifter",
            "Reminder fees",
        ),
        _a(
            "3700",
            INCOME,
            "Liiketoiminnan muut tuotot",
            "Övriga rörelseintäkter",
            "Other operating income",
        ),
        _a("3800", INCOME, "Korkotuotot", "Ränteintäkter", "Interest income"),
        *EXPENSES,
        _a("9000", EXPENSE, "Tuloverot", "Inkomstskatter", "Income taxes"),
    ],
)

CHARTS = {"association": ASSOCIATION, "cooperative": COOPERATIVE}
