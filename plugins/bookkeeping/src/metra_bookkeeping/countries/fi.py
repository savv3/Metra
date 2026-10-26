"""Finland: the Accounting Act (kirjanpitolaki 1336/1997), the Accounting
Decree (kirjanpitoasetus 1339/1997) and the decree on the financial
statements of small and micro entities (PMA, 1753/2015).

The charts follow the usual Finnish numbering: 1 assets, 2 equity and
liabilities, 3 income, 4 to 9 expenses. They are starting points; the
treasurer adds, renames and retires accounts in the app. From general
knowledge of the law, not legal advice.
"""

import datetime
from decimal import Decimal

from django.utils.translation import gettext_lazy as _

from . import Account, Chart, Format, Line, SizeLimits, VatRate

CODE = "fi"
NAME = _("Finland")

# A financial year is 12 months; the first one, or one whose dates change,
# may be shorter or longer, up to 18 months (KPL 1:4).
YEAR_MONTHS = 12
FIRST_YEAR_MONTHS = (1, 18)

ASSET, LIABILITY, EQUITY, INCOME, EXPENSE = "asset", "liability", "equity", "income", "expense"

# VAT rates (arvonlisäverolaki 1501/1993) with the days they apply: the
# general rate went from 24 % to 25.5 % on 1.9.2024 and the reduced rate from
# 14 % to 13.5 % on 1.1.2026 (vero.fi). 0 % is for sales without VAT.
VAT_RATES = [
    VatRate(Decimal("25.5"), first=datetime.date(2024, 9, 1)),
    VatRate(Decimal("24"), first=datetime.date(2013, 1, 1), last=datetime.date(2024, 8, 31)),
    VatRate(Decimal("14"), first=datetime.date(2013, 1, 1), last=datetime.date(2025, 12, 31)),
    VatRate(Decimal("13.5"), first=datetime.date(2026, 1, 1)),
    VatRate(Decimal("10"), first=datetime.date(2013, 1, 1)),
    VatRate(Decimal("0")),
]

# The accounts postings from invoicing go to, by number, for each chart; the
# treasurer can choose others. Sales VAT, purchase VAT and the VAT settlement
# have accounts of their own, so the VAT return can be checked against the
# books: each month (or VAT period) the sales and purchase VAT are moved to
# the settlement account, and paying the tax clears it.
POSTING_ACCOUNTS = {
    "association": {
        "receivables": "1700",
        "bank": "1910",
        "sales": "3000",
        "reminder_fees": "3100",
        "sales_vat": "2935",
        "purchase_vat": "1765",
        "vat_settlement": "2939",
    },
    "cooperative": {
        "receivables": "1700",
        "bank": "1910",
        "sales": "3000",
        "reminder_fees": "3600",
        "sales_vat": "2935",
        "purchase_vat": "1765",
        "vat_settlement": "2939",
    },
}


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
    _a(
        "1765",
        ASSET,
        "Ostojen arvonlisävero",
        "Ingående moms",
        "VAT on purchases",
    ),
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
    _a("2935", LIABILITY, "Myynnin arvonlisävero", "Utgående moms", "VAT on sales"),
    _a(
        "2939",
        LIABILITY,
        "Arvonlisäverovelka (tilitettävä)",
        "Momsskuld (redovisas)",
        "VAT payable (settlement)",
    ),
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
    _a("5600", EXPENSE, "Eläkekulut", "Pensionskostnader", "Pension costs"),
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
        # Reminder fees go with the activity the invoices are for (an
        # accountant to confirm).
        _a("3100", INCOME, "Muistutusmaksut", "Påminnelseavgifter", "Reminder fees"),
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
        _a("5600", EXPENSE, "Eläkekulut", "Pensionskostnader", "Pension costs"),
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


# Financial statements (PMA 1753/2015). The Finnish names are the decree's
# own (Säädöskokoelma 1753/2015, annexes I, IV and V, read 26.10.2026). The
# Swedish names are the usual Finland-Swedish ones and are still to be
# checked word for word against Finlands författningssamling 1753/2015; the
# English ones are translations, never for filing. The decree's
# instructions to show some parts separately ("erikseen ...") are not part
# of the names; long-term amounts are shown under their line instead.
#
# Each line takes the accounts whose numbers fall in its ranges, so an
# account the treasurer adds lands on the line its number belongs to.


def _l(key, fi, sv, en, *ranges, lines=(), **options):
    accounts = tuple(tuple(r.split("-")) if "-" in r else (r, r) for r in ranges)
    return Line(key, {"fi": fi, "sv": sv, "en": en}, accounts, tuple(lines), **options)


def _abc(key, fi, sv, en, *ranges, lines=()):
    return _l(key, fi, sv, en, *ranges, lines=lines, lettered=True)


APPROPRIATIONS = _l(
    "appropriations",
    "Tilinpäätössiirrot",
    "Bokslutsdispositioner",
    "Appropriations",
    lines=[
        _abc(
            "depreciation_difference",
            "Poistoeron muutos",
            "Förändring av avskrivningsdifferens",
            "Change in depreciation difference",
            "9700-9799",
        ),
        _abc(
            "untaxed_reserves",
            "Verotusperusteisten varausten muutos",
            "Förändring av frivilliga reserveringar",
            "Change in untaxed reserves",
            "9800-9899",
        ),
        _abc(
            "group_contribution",
            "Konserniavustus",
            "Koncernbidrag",
            "Group contribution",
            "9900-9999",
        ),
    ],
)

# Annex I: the income statement by nature of expense (kululajikohtainen),
# for cooperatives and companies.
ANNEX_I = Format(
    "annex_i",
    {"fi": "Tuloslaskelma", "sv": "Resultaträkning", "en": "Income statement"},
    source="PMA 1753/2015, liite I",
    sides=(
        _l(
            "income_statement",
            "",
            "",
            "",
            lines=[
                _l("net_sales", "LIIKEVAIHTO", "OMSÄTTNING", "NET SALES", "3000-3599"),
                _l(
                    "inventory_change",
                    "Valmiiden ja keskeneräisten tuotteiden varastojen muutos",
                    "Förändring av lager av färdiga varor och varor under tillverkning",
                    "Change in inventories of finished goods and work in progress",
                ),
                _l(
                    "own_use",
                    "Valmistus omaan käyttöön",
                    "Tillverkning för eget bruk",
                    "Production for own use",
                ),
                _l(
                    "other_operating_income",
                    "Liiketoiminnan muut tuotot",
                    "Övriga rörelseintäkter",
                    "Other operating income",
                    "3600-3799",
                ),
                _l(
                    "materials_and_services",
                    "Materiaalit ja palvelut",
                    "Material och tjänster",
                    "Materials and services",
                    lines=[
                        _abc(
                            "materials",
                            "Aineet, tarvikkeet ja tavarat",
                            "Material, förnödenheter och varor",
                            "Raw materials and consumables",
                            lines=[
                                _abc(
                                    "purchases",
                                    "Ostot tilikauden aikana",
                                    "Inköp under räkenskapsperioden",
                                    "Purchases during the financial year",
                                    "4000-4389",
                                ),
                                _abc(
                                    "stock_change",
                                    "Varastojen muutos",
                                    "Förändring av lager",
                                    "Change in inventories",
                                    "4390-4399",
                                ),
                            ],
                        ),
                        _abc(
                            "external_services",
                            "Ulkopuoliset palvelut",
                            "Externa tjänster",
                            "External services",
                            "4400-4999",
                        ),
                    ],
                ),
                _l(
                    "personnel",
                    "Henkilöstökulut",
                    "Personalkostnader",
                    "Personnel expenses",
                    lines=[
                        _abc(
                            "wages",
                            "Palkat ja palkkiot",
                            "Löner och arvoden",
                            "Wages and fees",
                            "5000-5499",
                        ),
                        _abc(
                            "social_costs",
                            "Henkilösivukulut",
                            "Lönebikostnader",
                            "Social security expenses",
                            lines=[
                                _abc(
                                    "pensions",
                                    "Eläkekulut",
                                    "Pensionskostnader",
                                    "Pension expenses",
                                    "5600-5699",
                                ),
                                _abc(
                                    "other_social_costs",
                                    "Muut henkilösivukulut",
                                    "Övriga lönebikostnader",
                                    "Other social security expenses",
                                    "5500-5599",
                                    "5700-5999",
                                ),
                            ],
                        ),
                    ],
                ),
                _l(
                    "depreciation",
                    "Poistot ja arvonalentumiset",
                    "Avskrivningar och nedskrivningar",
                    "Depreciation and impairment",
                    lines=[
                        _abc(
                            "planned_depreciation",
                            "Suunnitelman mukaiset poistot",
                            "Avskrivningar enligt plan",
                            "Depreciation according to plan",
                            "6000-6899",
                        ),
                        _abc(
                            "fixed_asset_impairment",
                            "Arvonalentumiset pysyvien vastaavien hyödykkeistä",
                            "Nedskrivningar av tillgångar bland bestående aktiva",
                            "Impairment of non-current assets",
                            "6900-6949",
                        ),
                        _abc(
                            "current_asset_impairment",
                            "Vaihtuvien vastaavien poikkeukselliset arvonalentumiset",
                            "Exceptionella nedskrivningar av rörliga aktiva",
                            "Exceptional impairment of current assets",
                            "6950-6999",
                        ),
                    ],
                ),
                _l(
                    "other_operating_expenses",
                    "Liiketoiminnan muut kulut",
                    "Övriga rörelsekostnader",
                    "Other operating expenses",
                    "7000-7999",
                ),
                _l(
                    "operating_profit",
                    "LIIKEVOITTO (-TAPPIO)",
                    "RÖRELSEVINST (-FÖRLUST)",
                    "OPERATING PROFIT (LOSS)",
                    result=True,
                ),
                _l(
                    "financial",
                    "Rahoitustuotot ja -kulut",
                    "Finansiella intäkter och kostnader",
                    "Financial income and expenses",
                    lines=[
                        _abc(
                            "group_shares",
                            "Tuotot osuuksista saman konsernin yrityksissä",
                            "Intäkter från andelar i företag inom samma koncern",
                            "Income from group undertakings",
                        ),
                        _abc(
                            "associate_shares",
                            "Tuotot osuuksista omistusyhteysyrityksissä",
                            "Intäkter från andelar i ägarintresseföretag",
                            "Income from participating interests",
                        ),
                        _abc(
                            "other_investments",
                            "Tuotot muista pysyvien vastaavien sijoituksista",
                            "Intäkter från övriga placeringar bland bestående aktiva",
                            "Income from other non-current investments",
                            "3900-3999",
                        ),
                        _abc(
                            "interest_income",
                            "Muut korko- ja rahoitustuotot",
                            "Övriga ränte- och finansiella intäkter",
                            "Other interest and financial income",
                            "3800-3899",
                        ),
                        _abc(
                            "investment_impairment",
                            "Arvonalentumiset pysyvien vastaavien sijoituksista",
                            "Nedskrivningar av placeringar bland bestående aktiva",
                            "Impairment of non-current investments",
                            "8900-8949",
                        ),
                        _abc(
                            "securities_impairment",
                            "Arvonalentumiset vaihtuvien vastaavien rahoitusarvopapereista",
                            "Nedskrivningar av finansiella värdepapper bland rörliga aktiva",
                            "Impairment of current securities",
                            "8950-8999",
                        ),
                        _abc(
                            "interest_expenses",
                            "Korkokulut ja muut rahoituskulut",
                            "Räntekostnader och övriga finansiella kostnader",
                            "Interest and other financial expenses",
                            "8000-8899",
                        ),
                    ],
                ),
                _l(
                    "profit_before_appropriations",
                    "VOITTO (TAPPIO) ENNEN TILINPÄÄTÖSSIIRTOJA JA VEROJA",
                    "VINST (FÖRLUST) FÖRE BOKSLUTSDISPOSITIONER OCH SKATTER",
                    "PROFIT (LOSS) BEFORE APPROPRIATIONS AND TAXES",
                    result=True,
                ),
                APPROPRIATIONS,
                _l("income_taxes", "Tuloverot", "Inkomstskatter", "Income taxes", "9000-9599"),
                _l(
                    "other_taxes",
                    "Muut välittömät verot",
                    "Övriga direkta skatter",
                    "Other direct taxes",
                    "9600-9699",
                ),
                _l(
                    "profit",
                    "TILIKAUDEN VOITTO (TAPPIO)",
                    "RÄKENSKAPSPERIODENS VINST (FÖRLUST)",
                    "PROFIT (LOSS) FOR THE FINANCIAL YEAR",
                    result=True,
                ),
            ],
        ),
    ),
)


def _section(key, fi, sv, en, income, expenses, expense_lines=()):
    """A section of the non-profit income statement: income, expenses and
    the surplus or deficit (tuotto-/kulujäämä)."""
    return _l(
        key,
        fi,
        sv,
        en,
        lines=[
            _l(f"{key}_income", "Tuotot", "Intäkter", "Income", *income),
            _l(f"{key}_expenses", "Kulut", "Kostnader", "Expenses", *expenses, lines=expense_lines),
            _l(
                f"{key}_result",
                "Tuotto-/Kulujäämä",
                "Intäkts-/Kostnadsöverskott",
                "Surplus (deficit)",
                result=True,
            ),
        ],
    )


# Annex IV: the income statement of an association or foundation
# (aatteellinen yhteisö tai säätiö), PMA 2:3. The decree has no line for
# income taxes; an association that pays them (on business income) shows
# them on a line of their own before the surplus, which an accountant is to
# confirm.
ANNEX_IV = Format(
    "annex_iv",
    {"fi": "Tuloslaskelma", "sv": "Resultaträkning", "en": "Income statement"},
    source="PMA 1753/2015, liite IV",
    sides=(
        _l(
            "income_statement",
            "",
            "",
            "",
            lines=[
                _section(
                    "activities",
                    "Varsinainen toiminta",
                    "Ordinarie verksamhet",
                    "Activities",
                    income=["3000-3999"],
                    expenses=[],
                    expense_lines=[
                        _abc(
                            "activities_personnel",
                            "Henkilöstökulut",
                            "Personalkostnader",
                            "Personnel expenses",
                            "5000-5799",
                        ),
                        _abc(
                            "activities_depreciation",
                            "Poistot",
                            "Avskrivningar",
                            "Depreciation",
                            "5800-5899",
                        ),
                        _abc(
                            "activities_other",
                            "Muut kulut",
                            "Övriga kostnader",
                            "Other expenses",
                            "4000-4999",
                            "5900-5999",
                        ),
                    ],
                ),
                _section(
                    "fundraising",
                    "Varainhankinta",
                    "Medelanskaffning",
                    "Fundraising",
                    income=["6000-6499"],
                    expenses=["6500-6999"],
                ),
                _section(
                    "investment",
                    "Sijoitus- ja rahoitustoiminta",
                    "Placerings- och finansieringsverksamhet",
                    "Investment and financing",
                    income=["7000-7499"],
                    expenses=["7500-7999"],
                ),
                _l(
                    "general_grants",
                    "Yleisavustukset",
                    "Allmänna understöd",
                    "General grants",
                    "8000-8999",
                ),
                _l(
                    "result",
                    "Tilikauden tulos",
                    "Räkenskapsperiodens resultat",
                    "Result for the financial year",
                    result=True,
                ),
                APPROPRIATIONS,
                _l(
                    "income_taxes",
                    "Tuloverot",
                    "Inkomstskatter",
                    "Income taxes",
                    "9000-9699",
                    added=True,
                ),
                _l(
                    "surplus",
                    "Tilikauden ylijäämä (alijäämä)",
                    "Räkenskapsperiodens överskott (underskott)",
                    "Surplus (deficit) for the financial year",
                    result=True,
                ),
            ],
        ),
    ),
)

INCOME_STATEMENTS = {"association": ANNEX_IV, "cooperative": ANNEX_I}

# Annex V: the balance sheet of a small entity (PMA 2:4). A micro entity
# may show only the groups (PMA 4:2), the roman-numbered lines here.
BALANCE_SHEET = Format(
    "annex_v",
    {"fi": "Tase", "sv": "Balansräkning", "en": "Balance sheet"},
    source="PMA 1753/2015, liite V",
    sides=(
        _l(
            "assets",
            "Vastaavaa",
            "Aktiva",
            "Assets",
            lines=[
                _l(
                    "non_current",
                    "PYSYVÄT VASTAAVAT",
                    "BESTÅENDE AKTIVA",
                    "NON-CURRENT ASSETS",
                    lines=[
                        _l(
                            "intangible",
                            "Aineettomat hyödykkeet",
                            "Immateriella tillgångar",
                            "Intangible assets",
                            lines=[
                                _abc(
                                    "development",
                                    "Kehittämismenot",
                                    "Utvecklingsutgifter",
                                    "Development costs",
                                    "1000-1019",
                                ),
                                _abc(
                                    "intangible_rights",
                                    "Aineettomat oikeudet",
                                    "Immateriella rättigheter",
                                    "Intangible rights",
                                    "1020-1039",
                                ),
                                _abc("goodwill", "Liikearvo", "Goodwill", "Goodwill", "1040-1059"),
                                _abc(
                                    "other_intangible",
                                    "Muut aineettomat hyödykkeet",
                                    "Övriga immateriella tillgångar",
                                    "Other intangible assets",
                                    "1060-1079",
                                ),
                                _abc(
                                    "intangible_advances",
                                    "Ennakkomaksut",
                                    "Förskottsbetalningar",
                                    "Advance payments",
                                    "1080-1099",
                                ),
                            ],
                        ),
                        _l(
                            "tangible",
                            "Aineelliset hyödykkeet",
                            "Materiella tillgångar",
                            "Tangible assets",
                            lines=[
                                _abc(
                                    "land",
                                    "Maa- ja vesialueet",
                                    "Mark- och vattenområden",
                                    "Land and water",
                                    "1100-1119",
                                ),
                                _abc(
                                    "buildings",
                                    "Rakennukset ja rakennelmat",
                                    "Byggnader och konstruktioner",
                                    "Buildings and structures",
                                    "1160-1179",
                                ),
                                _abc(
                                    "machinery",
                                    "Koneet ja kalusto",
                                    "Maskiner och inventarier",
                                    "Machinery and equipment",
                                    "1120-1159",
                                ),
                                _abc(
                                    "other_tangible",
                                    "Muut aineelliset hyödykkeet",
                                    "Övriga materiella tillgångar",
                                    "Other tangible assets",
                                    "1180-1189",
                                ),
                                _abc(
                                    "tangible_advances",
                                    "Ennakkomaksut ja keskeneräiset hankinnat",
                                    "Förskottsbetalningar och pågående nyanläggningar",
                                    "Advance payments and construction in progress",
                                    "1190-1199",
                                ),
                            ],
                        ),
                        _l(
                            "investments",
                            "Sijoitukset",
                            "Placeringar",
                            "Investments",
                            lines=[
                                _abc(
                                    "group_shares",
                                    "Osuudet saman konsernin yrityksissä",
                                    "Andelar i företag inom samma koncern",
                                    "Shares in group undertakings",
                                    "1200-1209",
                                ),
                                _abc(
                                    "group_receivables",
                                    "Saamiset saman konsernin yrityksiltä",
                                    "Fordringar hos företag inom samma koncern",
                                    "Receivables from group undertakings",
                                    "1210-1219",
                                ),
                                _abc(
                                    "associate_shares",
                                    "Osuudet omistusyhteysyrityksissä",
                                    "Andelar i ägarintresseföretag",
                                    "Participating interests",
                                    "1220-1229",
                                ),
                                _abc(
                                    "associate_receivables",
                                    "Saamiset omistusyhteysyrityksiltä",
                                    "Fordringar hos ägarintresseföretag",
                                    "Receivables from participating interests",
                                    "1230-1239",
                                ),
                                _abc(
                                    "other_shares",
                                    "Muut osakkeet ja osuudet",
                                    "Övriga aktier och andelar",
                                    "Other shares and holdings",
                                    "1240-1349",
                                ),
                                _abc(
                                    "other_investment_receivables",
                                    "Muut saamiset",
                                    "Övriga fordringar",
                                    "Other receivables",
                                    "1350-1399",
                                ),
                            ],
                        ),
                    ],
                ),
                _l(
                    "current",
                    "VAIHTUVAT VASTAAVAT",
                    "RÖRLIGA AKTIVA",
                    "CURRENT ASSETS",
                    lines=[
                        _l(
                            "inventories",
                            "Vaihto-omaisuus",
                            "Omsättningstillgångar",
                            "Inventories",
                            lines=[
                                _abc(
                                    "stock_materials",
                                    "Aineet ja tarvikkeet",
                                    "Material och förnödenheter",
                                    "Raw materials and consumables",
                                    "1400-1549",
                                ),
                                _abc(
                                    "work_in_progress",
                                    "Keskeneräiset tuotteet",
                                    "Varor under tillverkning",
                                    "Work in progress",
                                    "1550-1569",
                                ),
                                _abc(
                                    "finished_goods",
                                    "Valmiit tuotteet/tavarat",
                                    "Färdiga produkter/varor",
                                    "Finished goods",
                                    "1570-1589",
                                ),
                                _abc(
                                    "other_inventories",
                                    "Muu vaihto-omaisuus",
                                    "Övriga omsättningstillgångar",
                                    "Other inventories",
                                    "1590-1594",
                                ),
                                _abc(
                                    "inventory_advances",
                                    "Ennakkomaksut",
                                    "Förskottsbetalningar",
                                    "Advance payments",
                                    "1595-1599",
                                ),
                            ],
                        ),
                        _l(
                            "receivables",
                            "Saamiset",
                            "Fordringar",
                            "Receivables",
                            lines=[
                                _abc(
                                    "trade_receivables",
                                    "Myyntisaamiset",
                                    "Kundfordringar",
                                    "Trade receivables",
                                    "1700-1749",
                                ),
                                _abc(
                                    "group_current_receivables",
                                    "Saamiset saman konsernin yrityksiltä",
                                    "Fordringar hos företag inom samma koncern",
                                    "Receivables from group undertakings",
                                    "1600-1619",
                                ),
                                _abc(
                                    "associate_current_receivables",
                                    "Saamiset omistusyhteysyrityksiltä",
                                    "Fordringar hos ägarintresseföretag",
                                    "Receivables from participating interests",
                                    "1620-1639",
                                ),
                                _abc(
                                    "loan_receivables",
                                    "Lainasaamiset",
                                    "Lånefordringar",
                                    "Loan receivables",
                                    "1640-1699",
                                ),
                                _abc(
                                    "other_receivables",
                                    "Muut saamiset",
                                    "Övriga fordringar",
                                    "Other receivables",
                                    "1750-1759",
                                    "1763-1799",
                                ),
                                _abc(
                                    "unpaid_shares",
                                    "Maksamattomat osakkeet/osuudet",
                                    "Obetalda aktier/andelar",
                                    "Unpaid shares",
                                ),
                                _abc(
                                    "accrued_income",
                                    "Siirtosaamiset",
                                    "Resultatregleringar",
                                    "Prepayments and accrued income",
                                    "1760-1762",
                                ),
                            ],
                        ),
                        _l(
                            "securities",
                            "Rahoitusarvopaperit",
                            "Finansiella värdepapper",
                            "Securities",
                            lines=[
                                _abc(
                                    "group_securities",
                                    "Osuudet saman konsernin yrityksissä",
                                    "Andelar i företag inom samma koncern",
                                    "Shares in group undertakings",
                                ),
                                _abc(
                                    "other_securities_shares",
                                    "Muut osakkeet ja osuudet",
                                    "Övriga aktier och andelar",
                                    "Other shares and holdings",
                                    "1800-1849",
                                ),
                                _abc(
                                    "other_securities",
                                    "Muut arvopaperit",
                                    "Övriga värdepapper",
                                    "Other securities",
                                    "1850-1899",
                                ),
                            ],
                        ),
                        _l(
                            "cash",
                            "Rahat ja pankkisaamiset",
                            "Kassa och bank",
                            "Cash and bank",
                            "1900-1999",
                        ),
                    ],
                ),
            ],
        ),
        _l(
            "equity_and_liabilities",
            "Vastattavaa",
            "Passiva",
            "Equity and liabilities",
            lines=[
                _l(
                    "equity",
                    "OMA PÄÄOMA",
                    "EGET KAPITAL",
                    "EQUITY",
                    lines=[
                        _l(
                            "share_capital",
                            "Osake-, osuus- tai muu vastaava pääoma",
                            "Aktie-, andels- eller annat motsvarande kapital",
                            "Share capital or equivalent",
                            "2000-2019",
                        ),
                        _l(
                            "share_premium",
                            "Ylikurssirahasto",
                            "Överkursfond",
                            "Share premium",
                            "2020-2029",
                        ),
                        _l(
                            "revaluation",
                            "Arvonkorotusrahasto",
                            "Uppskrivningsfond",
                            "Revaluation reserve",
                            "2030-2039",
                        ),
                        _l(
                            "other_reserves",
                            "Muut rahastot",
                            "Övriga fonder",
                            "Other reserves",
                            lines=[
                                _abc(
                                    "invested_free_equity",
                                    "Sijoitetun vapaan oman pääoman rahasto",
                                    "Fonden för inbetalt fritt eget kapital",
                                    "Reserve for invested unrestricted equity",
                                    "2040-2044",
                                ),
                                _abc(
                                    "reserve_fund",
                                    "Vararahasto",
                                    "Reservfond",
                                    "Reserve fund",
                                    "2045-2049",
                                ),
                                _abc(
                                    "statutory_reserves",
                                    "Yhtiöjärjestyksen tai sääntöjen mukaiset rahastot",
                                    "Fonder enligt bolagsordningen eller stadgarna",
                                    "Reserves under the articles or rules",
                                    "2050-2059",
                                ),
                                _abc(
                                    "fair_value_reserve",
                                    "Käyvän arvon rahasto",
                                    "Fond för verkligt värde",
                                    "Fair value reserve",
                                    "2060-2069",
                                ),
                                _abc(
                                    "other_funds",
                                    "Muut rahastot",
                                    "Övriga fonder",
                                    "Other reserves",
                                    "2070-2199",
                                ),
                            ],
                        ),
                        _l(
                            "retained_earnings",
                            "Edellisten tilikausien voitto (tappio)",
                            "Vinst (förlust) från tidigare räkenskapsperioder",
                            "Retained earnings (loss)",
                            "2200-2399",
                        ),
                        _l(
                            "profit_for_year",
                            "Tilikauden voitto (tappio)",
                            "Räkenskapsperiodens vinst (förlust)",
                            "Profit (loss) for the financial year",
                            computed="result",
                        ),
                    ],
                ),
                _l(
                    "accumulated_appropriations",
                    "TILINPÄÄTÖSSIIRTOJEN KERTYMÄ",
                    "ACKUMULERADE BOKSLUTSDISPOSITIONER",
                    "ACCUMULATED APPROPRIATIONS",
                    lines=[
                        _l(
                            "depreciation_difference",
                            "Poistoero",
                            "Avskrivningsdifferens",
                            "Depreciation difference",
                            "2400-2449",
                        ),
                        _l(
                            "untaxed_reserves",
                            "Verotusperusteiset varaukset",
                            "Frivilliga reserveringar",
                            "Untaxed reserves",
                            "2450-2499",
                        ),
                    ],
                ),
                _l(
                    "provisions",
                    "PAKOLLISET VARAUKSET",
                    "OBLIGATORISKA RESERVERINGAR",
                    "PROVISIONS",
                    lines=[
                        _l(
                            "pension_provisions",
                            "Eläkevaraukset",
                            "Pensionsreserveringar",
                            "Provisions for pensions",
                            "2500-2519",
                        ),
                        _l(
                            "tax_provisions",
                            "Verovaraukset",
                            "Skattereserveringar",
                            "Provisions for taxation",
                            "2520-2539",
                        ),
                        _l(
                            "other_provisions",
                            "Muut pakolliset varaukset",
                            "Övriga obligatoriska reserveringar",
                            "Other provisions",
                            "2540-2599",
                        ),
                    ],
                ),
                _l(
                    "liabilities",
                    "VIERAS PÄÄOMA",
                    "FRÄMMANDE KAPITAL",
                    "LIABILITIES",
                    lines=[
                        _abc(
                            "bonds",
                            "Joukkovelkakirjalainat",
                            "Obligationslån",
                            "Bonds",
                            "2600-2604",
                        ),
                        _abc(
                            "convertible_bonds",
                            "Vaihtovelkakirjalainat",
                            "Konvertibla lån",
                            "Convertible bonds",
                            "2605-2609",
                        ),
                        _abc(
                            "bank_loans",
                            "Lainat rahoituslaitoksilta",
                            "Lån från kreditinstitut",
                            "Loans from credit institutions",
                            "2610-2699",
                        ),
                        _abc(
                            "pension_loans",
                            "Takaisinlainat työeläkevakuutuslaitoksilta",
                            "Pensionslån",
                            "Pension loans",
                            "2700-2799",
                        ),
                        _abc(
                            "advances_received",
                            "Saadut ennakot",
                            "Erhållna förskott",
                            "Advances received",
                            "2860-2870",
                        ),
                        _abc(
                            "trade_payables",
                            "Ostovelat",
                            "Leverantörsskulder",
                            "Trade payables",
                            "2871-2879",
                        ),
                        _abc(
                            "bills_payable",
                            "Rahoitusvekselit",
                            "Växelskulder",
                            "Bills of exchange payable",
                            "2880-2889",
                        ),
                        _abc(
                            "group_payables",
                            "Velat saman konsernin yrityksille",
                            "Skulder till företag inom samma koncern",
                            "Payables to group undertakings",
                            "2800-2829",
                        ),
                        _abc(
                            "associate_payables",
                            "Velat omistusyhteysyrityksille",
                            "Skulder till ägarintresseföretag",
                            "Payables to participating interests",
                            "2830-2849",
                        ),
                        _abc(
                            "other_liabilities",
                            "Muut velat",
                            "Övriga skulder",
                            "Other liabilities",
                            "2850-2859",
                            "2890-2959",
                        ),
                        _abc(
                            "accrued_expenses",
                            "Siirtovelat",
                            "Resultatregleringar",
                            "Accruals and deferred income",
                            "2960-2999",
                        ),
                    ],
                ),
            ],
        ),
    ),
)

# Size classes (KPL 1:4a and 1:4b): micro and small limits of balance
# sheet total, turnover and average staff. The limits from 2024 are those of
# the government proposal HE 76/2024, for years starting on or after
# 1.1.2024; an accountant is to confirm they were enacted as proposed.
SIZE_LIMITS = [
    SizeLimits(
        datetime.date(2016, 1, 1),
        micro=(Decimal("350000"), Decimal("700000"), 10),
        small=(Decimal("6000000"), Decimal("12000000"), 50),
    ),
    SizeLimits(
        datetime.date(2024, 1, 1),
        micro=(Decimal("450000"), Decimal("900000"), 10),
        small=(Decimal("7500000"), Decimal("15000000"), 50),
    ),
]

# Financial statements are kept in Finnish or Swedish (KPL 3 ch.).
STATEMENT_LANGUAGES = ("fi", "sv")

# The words around the statements' lines, in the statements' languages.
TEXTS = {
    "total_assets": {"fi": "Vastaavaa yhteensä", "sv": "Aktiva sammanlagt", "en": "Total assets"},
    "total_equity_and_liabilities": {
        "fi": "Vastattavaa yhteensä",
        "sv": "Passiva sammanlagt",
        "en": "Total equity and liabilities",
    },
    "long_term": {
        "fi": "josta pitkäaikaista",
        "sv": "varav långfristigt",
        "en": "of which long-term",
    },
    "short_term": {
        "fi": "josta lyhytaikaista",
        "sv": "varav kortfristigt",
        "en": "of which short-term",
    },
    "business_id": {"fi": "Y-tunnus", "sv": "FO-nummer", "en": "Business ID"},
    "translation": {
        "fi": "",
        "sv": "",
        "en": "Translation. The statements are kept in Finnish or Swedish; this English "
        "version is not for filing.",
    },
}
