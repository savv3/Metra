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

# A registered association (yhdistys). The non-profit income statement
# (PMA 1753/2015, Annex IV) shows income and expenses separately for the
# association's own activities, fundraising, and investment and financing,
# then general grants. Each has its own range of account numbers, so every
# account (also one added later) belongs to one section by its number.
ASSOCIATION_SECTIONS = [
    ("3000", "3999", "activities_income"),
    ("4000", "5999", "activities_expenses"),
    ("6000", "6499", "fundraising_income"),
    ("6500", "6999", "fundraising_expenses"),
    ("7000", "7499", "investment_income"),
    ("7500", "7999", "investment_expenses"),
    ("8000", "8999", "general_grants"),
    ("9000", "9999", "taxes"),
]

ASSOCIATION = Chart(
    name=_("Association"),
    description=_(
        "For a registered association (yhdistys): activities, fundraising and membership "
        "fees, with a surplus or deficit."
    ),
    sections=ASSOCIATION_SECTIONS,
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
        # The association's own activities (varsinainen toiminta).
        _a(
            "3000", INCOME, "Toiminnan tuotot", "Intäkter av verksamheten", "Income from activities"
        ),
        _a("3200", INCOME, "Toiminta-avustukset", "Verksamhetsbidrag", "Grants for activities"),
        _a(
            "4000",
            EXPENSE,
            "Aineet ja tarvikkeet",
            "Material och förnödenheter",
            "Materials and supplies",
        ),
        _a("4400", EXPENSE, "Ostetut palvelut", "Köpta tjänster", "Purchased services"),
        _a("4600", EXPENSE, "Toimitilakulut", "Lokalkostnader", "Premises"),
        _a("4610", EXPENSE, "Sähkö", "El", "Electricity"),
        _a(
            "4620",
            EXPENSE,
            "Korjaukset ja kunnossapito",
            "Reparationer och underhåll",
            "Repairs and maintenance",
        ),
        _a("4700", EXPENSE, "Vakuutukset", "Försäkringar", "Insurance"),
        _a(
            "4750",
            EXPENSE,
            "Kokous- ja edustuskulut",
            "Mötes- och representationskostnader",
            "Meetings and hospitality",
        ),
        _a("4800", EXPENSE, "Toimistokulut", "Kontorskostnader", "Office costs"),
        _a("4810", EXPENSE, "Puhelin ja posti", "Telefon och post", "Phone and postage"),
        _a("4820", EXPENSE, "Tietotekniikkakulut", "IT-kostnader", "IT costs"),
        _a("4850", EXPENSE, "Pankkikulut", "Bankkostnader", "Bank charges"),
        _a(
            "4870",
            EXPENSE,
            "Tilintarkastus ja toiminnantarkastus",
            "Revision och verksamhetsgranskning",
            "Audit fees",
        ),
        _a(
            "4880",
            EXPENSE,
            "Jäsenmaksut muille yhteisöille",
            "Medlemsavgifter till andra organisationer",
            "Membership fees paid",
        ),
        _a("4990", EXPENSE, "Muut kulut", "Övriga kostnader", "Other expenses"),
        _a("5000", EXPENSE, "Palkat ja palkkiot", "Löner och arvoden", "Wages and fees"),
        _a("5500", EXPENSE, "Henkilösivukulut", "Lönebikostnader", "Social security costs"),
        _a("5800", EXPENSE, "Poistot", "Avskrivningar", "Depreciation"),
        # Fundraising (varainhankinta).
        _a("6000", INCOME, "Jäsenmaksut", "Medlemsavgifter", "Membership fees"),
        _a("6100", INCOME, "Lahjoitukset", "Donationer", "Donations"),
        _a(
            "6200",
            INCOME,
            "Muut varainhankinnan tuotot",
            "Övriga intäkter av medelanskaffning",
            "Other fundraising income",
        ),
        _a(
            "6500",
            EXPENSE,
            "Varainhankinnan kulut",
            "Kostnader för medelanskaffning",
            "Fundraising expenses",
        ),
        # Investment and financing (sijoitus- ja rahoitustoiminta).
        _a("7000", INCOME, "Korkotuotot", "Ränteintäkter", "Interest income"),
        _a("7100", INCOME, "Muistutusmaksut", "Påminnelseavgifter", "Reminder fees"),
        _a("7500", EXPENSE, "Korkokulut", "Räntekostnader", "Interest expenses"),
        # General grants (yleisavustukset) and income taxes.
        _a("8000", INCOME, "Yleisavustukset", "Allmänna understöd", "General grants"),
        _a("9000", EXPENSE, "Tuloverot", "Inkomstskatter", "Income taxes"),
    ],
)

# The standard income statement (by nature of expense) for cooperatives and
# companies: net sales, other operating income, then expenses by kind.
COOPERATIVE_SECTIONS = [
    ("3000", "3599", "net_sales"),
    ("3600", "3799", "other_operating_income"),
    ("3800", "3999", "financial_income"),
    ("4000", "4999", "materials_and_services"),
    ("5000", "5999", "personnel"),
    ("6000", "6999", "depreciation"),
    ("7000", "7999", "other_operating_expenses"),
    ("8000", "8999", "financial_expenses"),
    ("9000", "9999", "taxes"),
]

# A cooperative (osuuskunta) such as a water cooperative, or a company: the
# standard income statement with net sales, and a profit or loss.
COOPERATIVE = Chart(
    name=_("Cooperative or company"),
    description=_(
        "For a cooperative (osuuskunta), such as a water cooperative, or a company: net "
        "sales, with a profit or loss."
    ),
    sections=COOPERATIVE_SECTIONS,
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
