"""Small camt files in the shape Finnish banks send them."""

NS54 = "urn:iso:std:iso:20022:tech:xsd:camt.054.001.02"
NS53 = "urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"
IBAN = "FI2112345600000785"


def tx(amount, reference="", message="", name="Anna Andersson", ref_id="", debit=False):
    party = "Cdtr" if debit else "Dbtr"
    refs = f"<Refs><AcctSvcrRef>{ref_id}</AcctSvcrRef></Refs>" if ref_id else ""
    remittance = ""
    if reference:
        remittance = (
            "<RmtInf><Strd><CdtrRefInf><Tp><CdOrPrtry><Cd>SCOR</Cd></CdOrPrtry></Tp>"
            f"<Ref>{reference}</Ref></CdtrRefInf></Strd></RmtInf>"
        )
    elif message:
        remittance = f"<RmtInf><Ustrd>{message}</Ustrd></RmtInf>"
    return (
        f'<TxDtls>{refs}<AmtDtls><TxAmt><Amt Ccy="EUR">{amount}</Amt></TxAmt></AmtDtls>'
        f"<RltdPties><{party}><Nm>{name}</Nm></{party}>"
        f"<{party}Acct><Id><IBAN>FI4950009420028730</IBAN></Id></{party}Acct></RltdPties>"
        f"{remittance}</TxDtls>"
    )


def entry(total, details, booked="2026-10-15", ref="", debit=False, status="BOOK"):
    indicator = "DBIT" if debit else "CRDT"
    archive = f"<AcctSvcrRef>{ref}</AcctSvcrRef>" if ref else ""
    return (
        f'<Ntry><Amt Ccy="EUR">{total}</Amt><CdtDbtInd>{indicator}</CdtDbtInd>'
        f"<Sts>{status}</Sts><BookgDt><Dt>{booked}</Dt></BookgDt><ValDt><Dt>{booked}</Dt></ValDt>"
        f"{archive}<BkTxCd/><NtryDtls>{''.join(details)}</NtryDtls></Ntry>"
    )


def camt054(*entries, msg_id="N1"):
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><Document xmlns="{NS54}"><BkToCstmrDbtCdtNtfctn>'
        f"<GrpHdr><MsgId>{msg_id}</MsgId><CreDtTm>2026-10-16T06:00:00</CreDtTm></GrpHdr>"
        f"<Ntfctn><Id>{msg_id}</Id><Acct><Id><IBAN>{IBAN}</IBAN></Id></Acct>"
        f"{''.join(entries)}</Ntfctn></BkToCstmrDbtCdtNtfctn></Document>"
    ).encode()


def camt053(*entries, msg_id="S1"):
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><Document xmlns="{NS53}"><BkToCstmrStmt>'
        f"<GrpHdr><MsgId>{msg_id}</MsgId><CreDtTm>2026-11-01T06:00:00</CreDtTm></GrpHdr>"
        f"<Stmt><Id>{msg_id}</Id><Acct><Id><IBAN>{IBAN}</IBAN></Id></Acct>"
        "<FrToDt><FrDtTm>2026-10-01T00:00:00</FrDtTm><ToDtTm>2026-10-31T23:59:59</ToDtTm></FrToDt>"
        f"{''.join(entries)}</Stmt></BkToCstmrStmt></Document>"
    ).encode()
