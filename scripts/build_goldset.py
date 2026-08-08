"""Build and validate the CircularOS gold set from the real SEBI circular pair.

Produces two JSONL files under ``data/goldsets/``:
  * ``obligations.jsonl`` — hand-annotated gold obligations (and negative examples)
    from the Aug-2024 stockbroker master circular.
  * ``changeset.jsonl``   — labeled changes (and cosmetic non-changes) between the
    Aug-2024 and Jun-2025 circulars.

ANTI-FABRICATION GUARANTEE
--------------------------
Every annotation carries a verbatim ``quote`` and this script validates, at build
time, that the quote actually occurs in the real PDF text (whitespace- and
punctuation-normalized substring match): obligation quotes against Aug-2024, and
each change's ``old_text``/``new_text`` against Aug-2024 / Jun-2025 respectively.
The build FAILS if any quote cannot be located. A gold record therefore cannot
reference text that is not in the source documents.

The structured fields (actor, action, difficulty, materiality, …) are the human
first-pass annotator's reading of that real span. See ``data/goldsets/README.md``
for the honest verification status.

Usage:
    python scripts/build_goldset.py            # validate + write JSONL
    python scripts/build_goldset.py --check     # validate only, don't write
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

AUG_PDF = "data/goldsets/circulars/stockbrokers_master_2024-08-09.pdf"
JUN_PDF = "data/goldsets/circulars/stockbrokers_master_2025-06-17.pdf"
AUG_DOC = "stockbrokers_master_2024-08-09"
JUN_DOC = "stockbrokers_master_2025-06-17"
OUT_DIR = "data/goldsets"


# ── provenance normalization ──────────────────────────────────────────
_SMART = {
    "’": "'", "‘": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", " ": " ",
}


def prov_norm(s: str) -> str:
    """Normalize for substring provenance checks: unify smart quotes/dashes,
    collapse all whitespace. Applied to BOTH the source text and the quote."""
    for k, v in _SMART.items():
        s = s.replace(k, v)
    return re.sub(r"\s+", " ", s).strip()


def load_pdf_text(path: str) -> str:
    import fitz

    doc = fitz.open(path)
    parts = [doc[i].get_text("text") for i in range(doc.page_count)]
    doc.close()
    return prov_norm("\n".join(parts))


# ── obligation authoring helper ───────────────────────────────────────
def mkobl(ref, page, quote, ob, norm=None, actor=None, action=None, obj=None,
      conditions=None, exceptions=None, frequency=None, deadline=None,
      evidence=None, penalty=None, difficulty="medium", tags=None, notes=""):
    return {
        "clause_ref": ref, "page": page, "quote": quote, "is_obligation": ob,
        "normalized_obligation": norm, "actor": actor, "action": action,
        "object": obj, "conditions": conditions, "exceptions": exceptions,
        "frequency": frequency, "deadline": deadline,
        "evidence_requirement": evidence, "penalty_reference": penalty,
        "difficulty": difficulty, "tags": tags or [], "notes": notes,
    }


# Every `quote` below is a verbatim span of the Aug-2024 circular (validated).
OBLIGATIONS = [
    # ── I. Registration & II. Supervision ──────────────────────────────
    mkobl("1.1", 10, 'no person shall be eligible to be elected as a member if he has been convicted of an offence involving fraud or dishonesty', False,
      tags=["negative", "cross-reference", "definition"], difficulty="hard",
      notes="Legal eligibility citation of Rule 8(1)(e) SCRR 1957, not an operational obligation on the broker; negative to test precision on rule-citation clauses."),
    mkobl("3.1", 10, 'a Stock Broker has to apply in Form A, Schedule I of the aforesaid Regulations, duly recommended by the Stock Exchange of which he is a member, for registration as a Stock Broker by SEBI', True,
      "A stock broker must apply for registration in Form A (Schedule I) duly recommended by its stock exchange.",
      actor="Stock Broker", action="apply for registration", obj="Form A application", difficulty="medium",
      tags=["cross-reference"], notes="Procedural registration obligation with regulatory cross-reference."),
    mkobl("4.1", 11, 'The applications for grant of registration / requisite approvals are processed by SEBI based on information communicated by the Exchange/ members to SEBI', False,
      tags=["negative", "informational"], difficulty="easy",
      notes="Descriptive of SEBI's process; no obligation cast on a regulated entity."),
    mkobl("13.1.1", 19, 'The Stock Exchange or the Clearing Corporation, as the case may be, shall, in consultation with SEBI, formulate a policy for annual inspection of their members in various segments and follow up action thereon', True,
      "Stock Exchanges/Clearing Corporations must formulate a policy for annual inspection of members, in consultation with SEBI.",
      actor="Stock Exchange / Clearing Corporation", action="formulate inspection policy", obj="annual inspection policy",
      frequency="yearly", difficulty="medium", tags=["multi-actor"]),
    mkobl("14.2.10", 23, 'Stock Brokers who do not fall under any of the above category shall be inspected by the Stock Exchanges at least once in three years', True,
      "Stock exchanges must inspect stock brokers not otherwise flagged at least once every three years.",
      actor="Stock Exchanges", action="inspect", obj="stock brokers", frequency="on-occurrence",
      deadline="at least once in three years", difficulty="medium", tags=["conditional", "implicit-deadline"]),
    mkobl("14.2.7", 22, 'Stock Exchange shall frame internal policy for selection of stock brokers for inspection based on inputs/alerts from Risk Based Supervision', True,
      "Stock exchanges must frame an internal policy for risk-based selection of brokers for inspection.",
      actor="Stock Exchange", action="frame selection policy", obj="inspection selection policy", difficulty="medium"),
    mkobl("15.1", 24, 'SEBI constituted a committee on "Enhanced Supervision of Stock Brokers", which included representatives from Stock Exchanges, Depositories and Brokers', False,
      tags=["negative", "informational"], difficulty="easy",
      notes="Background narrative about a committee; no operative obligation."),
    mkobl("16.2", 38, 'The Stock Exchanges should ensure that system audit of stock brokers / trading members is conducted in accordance with the prescribed guidelines', True,
      "Stock exchanges must ensure system audits of brokers are conducted per the prescribed guidelines.",
      actor="Stock Exchanges", action="ensure system audit conducted", obj="system audit", difficulty="medium",
      tags=["cross-reference"]),
    mkobl("17.3", 44, "Stock Exchanges/ Clearing Corporations/ Depositories, shall devise a mechanism to detect diversion of clients' securities and to share information among themselves", True,
      "MIIs must devise a mechanism to detect diversion of client securities and share information among themselves.",
      actor="Stock Exchanges / Clearing Corporations / Depositories", action="devise detection mechanism",
      obj="diversion of client securities", difficulty="hard", tags=["multi-actor"]),
    mkobl("17.3.3", 44, 'Stock Exchange shall seek clarification from the concerned stock broker on the mismatches reported by Depository and identify transfer to a non- client/third party, without any trade obligation', True,
      "The stock exchange must seek clarification from the broker on depository-reported mismatches and identify third-party transfers.",
      actor="Stock Exchange", action="seek clarification / identify transfers", obj="reported mismatches",
      difficulty="hard", tags=["conditional", "multi-actor"]),

    # ── QSB (sec 18) ───────────────────────────────────────────────────
    mkobl("18.1", 46, 'SEBI, vide Gazette Notification dated January 17, 2023, amended the SEBI (Stock Broker) Regulations, 1992 for designating certain stock brokers', False,
      tags=["negative", "informational"], difficulty="medium",
      notes="Background on the QSB designation power; not itself an operative obligation."),
    mkobl("18.2", 46, 'The stock broker designated as a QSB shall be required to meet enhanced obligations and discharge responsibilities to ensure appropriate governance structure', True,
      "A stock broker designated as a QSB must meet enhanced obligations across governance, risk, infrastructure and investor services.",
      actor="Qualified Stock Broker (QSB)", action="meet enhanced obligations", obj="governance/risk/infrastructure standards",
      difficulty="medium", notes="Umbrella QSB obligation."),
    mkobl("18.4.3", 47, 'The values shall be calculated on an annual basis', True,
      "QSB-designation parameter values must be calculated on an annual basis.",
      actor="Stock Exchanges", action="calculate designation values", obj="QSB parameters", frequency="yearly",
      difficulty="easy"),
    mkobl("18.4.4", 48, 'those QSBs which no longer belong to the list, shall continue to comply with the enhanced obligations and responsibilities, for an additional period of 3 financial years', True,
      "A broker exiting the QSB list must continue complying with QSB obligations for a further 3 financial years.",
      actor="Qualified Stock Broker (QSB)", action="continue compliance", obj="enhanced QSB obligations",
      deadline="additional period of 3 financial years", difficulty="hard", tags=["conditional", "implicit-deadline"]),

    # ── III. Dealings with client ──────────────────────────────────────
    mkobl("19.1", 57, 'It shall be mandatory for the broker to use unique client code for all clients', True,
      "Brokers must use a unique client code for all clients and maintain client PAN.",
      actor="Broker", action="use unique client code", obj="all clients", evidence="Permanent Account Number (PAN)",
      difficulty="easy"),
    mkobl("20.12", 60, 'Stock Broker shall make available these standard documents to the clients, either in electronic or physical form, depending upon the preference of the client as part of account opening kit', True,
      "Stock brokers must provide the standard account-opening documents to clients in the client's preferred form.",
      actor="Stock Broker", action="make available documents", obj="standard account-opening documents",
      difficulty="easy"),
    mkobl("21.1", 62, "Submission of 'choice of nomination' for trading accounts has been made voluntary as a step towards ease of doing business", False,
      tags=["negative", "informational"], difficulty="medium",
      notes="States nomination is voluntary — informational, deliberately NOT an obligation (tests precision on 'voluntary' clauses)."),
    mkobl("22.1.1", 63, 'Unless otherwise specifically agreed to by a Client, the settlement of funds shall be done within twenty-four hours of the payout', True,
      "Client funds must be settled within twenty-four hours of payout unless a running account is authorized.",
      actor="Stock Broker", action="settle funds", obj="client funds", deadline="within twenty-four hours of the payout",
      conditions=["unless the client authorizes a running account"], difficulty="hard", tags=["conditional"]),
    mkobl("22.3", 65, 'The stock broker shall have documentary evidence of financial details provided by the clients who opt to deal in the derivative segment', True,
      "Brokers must hold documentary evidence of financial details for clients dealing in the derivative segment.",
      actor="Stock Broker", action="obtain/hold documentary evidence", obj="client financial details",
      conditions=["client opts to deal in the derivative segment"], evidence="documentary evidence of financial details",
      difficulty="medium", tags=["conditional"]),
    mkobl("22.5", 66, 'All the documents in both the mandatory and the non-mandatory parts shall be printed in minimum font size of 11', True,
      "Client documents (mandatory and non-mandatory) must be printed in minimum font size 11.",
      actor="Stock Broker", action="print documents", obj="client documents", difficulty="easy"),
    mkobl("23.1", 67, 'It shall be compulsory for all Member brokers to keep the money of the clients in a separate account and their own money in a separate account', True,
      "Member brokers must keep client money and their own money in separate accounts.",
      actor="Member Broker", action="segregate accounts", obj="client vs own money", difficulty="easy"),
    mkobl("27.1", 71, 'Brokers should not accept cash from the client whether against obligations or as margin for purchase of securities and / or give cash against sale of securities to the clients', True,
      "Brokers must not accept cash from, or give cash to, clients for securities obligations/margins.",
      actor="Broker", action="not accept/give cash", obj="client cash", difficulty="easy",
      notes="Prohibition-type obligation."),
    mkobl("29.2", 72, 'The broker shall disclose this information upfront to his new clients at the time of entering into the Know Your Client agreement', True,
      "Brokers must disclose proprietary-trading information upfront to new clients at KYC agreement.",
      actor="Broker", action="disclose upfront", obj="proprietary trading disclosure",
      deadline="at the time of entering into the Know Your Client agreement", difficulty="medium", tags=["conditional"]),

    # Authorised persons (sec 32) & alerts (sec 33)
    mkobl("32.7.4", 77, 'Stock Broker shall notify changes, if any, in the authorised person to all registered clients of that branch at least thirty days before the change', True,
      "Brokers must notify affected clients of authorised-person changes at least thirty days in advance.",
      actor="Stock Broker", action="notify changes", obj="authorised person change",
      deadline="at least thirty days before the change", difficulty="medium", tags=["conditional"]),
    mkobl("32.7.5", 77, 'Stock Broker shall conduct periodic inspection of branches assigned to authorised persons and records of the operations carried out by them', True,
      "Brokers must periodically inspect branches assigned to authorised persons and their records.",
      actor="Stock Broker", action="conduct periodic inspection", obj="authorised-person branches", difficulty="medium"),
    mkobl("33.2.2", 78, 'Stock Brokers shall upload the details of clients, such as, name, mobile number, address for correspondence and E-mail address', True,
      "Brokers must upload client contact details (name, mobile, address, email) to the exchange platform.",
      actor="Stock Brokers", action="upload client details", obj="client contact details", difficulty="easy"),
    mkobl("33.2.3", 79, 'Stock Brokers shall ensure that the mobile numbers/E-mail addresses of their employees /remisiers/authorized persons are not uploaded on behalf of clients', True,
      "Brokers must ensure employees'/APs' contact details are not uploaded in place of clients'.",
      actor="Stock Brokers", action="ensure correct contact upload", obj="client mobile/email", difficulty="medium",
      notes="Anti-substitution safeguard."),

    # Unauthorised trading (sec 34)
    mkobl("34.2", 80, 'all brokers shall execute trades of clients only after keeping evidence of the client placing such order', True,
      "Brokers must execute client trades only after retaining evidence of the client's order.",
      actor="Broker", action="execute trades only with order evidence", obj="client orders",
      evidence="physical record / telephone recording / email / internet log / SMS / other verifiable record",
      difficulty="hard", tags=["conditional"]),
    mkobl("34.3", 80, 'When a dispute arises, the broker shall produce the above mentioned records for the disputed trades', True,
      "On a dispute, brokers must produce the order-evidence records for the disputed trades.",
      actor="Broker", action="produce records", obj="order-evidence records",
      conditions=["a dispute arises"], difficulty="medium", tags=["conditional", "cross-reference"]),
    mkobl("34.4", 80, 'the stock broker shall mandatorily use telephone recording system to record the instructions and maintain telephone recordings as part of its records', True,
      "Where orders come by phone, brokers must record and retain the telephone instructions.",
      actor="Stock Broker", action="record & retain telephone instructions", obj="telephone order instructions",
      conditions=["order instructions received through the telephone"], evidence="telephone recordings",
      difficulty="medium", tags=["conditional"]),
    mkobl("34.5", 80, 'The Brokers are required to maintain the records specified at para 34.2 above for a minimum period', True,
      "Brokers must retain the order-evidence records for the minimum arbitration period (currently three years).",
      actor="Broker", action="maintain records", obj="order-evidence records", deadline="currently three years",
      difficulty="hard", tags=["cross-reference", "implicit-deadline"],
      notes="Deadline expressed by reference to arbitration acceptance period."),

    # PoA (sec 35)
    mkobl("35.1", 81, 'A Power of Attorney (PoA) is executed by the client in favour of the stock broker /stock broker and depository participant to authorize the broker to operate', False,
      tags=["negative", "informational"], difficulty="medium",
      notes="Definitional/descriptive of what a PoA is; not an obligation."),
    mkobl("35.5", 81, 'No stock broker or depository participant shall deny services to the client if the client refuses to execute a PoA in their favour', True,
      "Brokers/DPs must not deny services to a client who refuses to execute a PoA (except internet-based trading).",
      actor="Stock Broker / Depository Participant", action="not deny services", obj="client services",
      conditions=["client refuses to execute a PoA"], exceptions=["internet based trading is exempted"],
      difficulty="hard", tags=["conditional", "multi-actor"]),
    mkobl("35.8.1.3", 83, 'Be executed in the name of the concerned SEBI registered entity only and not in the name of any employee or representative of the stock broker /depository participant', True,
      "A PoA must be executed in the name of the SEBI-registered entity only, not an employee/representative.",
      actor="Stock Broker / Depository Participant", action="execute PoA in registered-entity name", obj="Power of Attorney",
      difficulty="medium"),
    mkobl("35.8.1.6", 84, 'Contain a clause by which the stock broker would return to the client(s), the securities or fund that may have been received by it erroneously', True,
      "A PoA must contain a clause requiring return of securities/funds received erroneously or without entitlement.",
      actor="Stock Broker", action="include return clause", obj="Power of Attorney", difficulty="medium"),
    mkobl("35.8.1.7", 84, 'Be revocable at any time. However, such revocation shall not be applicable for any outstanding settlement obligation arising out of the trades carried out prior to receiving request for revocation of PoA', True,
      "A PoA must be revocable at any time, except for settlement obligations from trades before the revocation request.",
      actor="Stock Broker", action="allow revocation", obj="Power of Attorney",
      exceptions=["outstanding settlement obligations from trades prior to the revocation request"],
      difficulty="hard", tags=["conditional", "exception" if False else "cross-reference"]),
    mkobl("35.8.1.8", 84, 'Be executed by all the joint holders (in case of a demat account held jointly)', True,
      "For a jointly held demat account, the PoA must be executed by all joint holders.",
      actor="Client", action="execute PoA (all joint holders)", obj="Power of Attorney",
      conditions=["demat account held jointly"], difficulty="medium", tags=["conditional"]),
    mkobl("35.8.1.9", 84, "Authorize the stock broker/depository participant to send consolidated summary of Client's scrip-wise buy and sell positions taken with average rates to the client by way of SMS / email on a daily basis", True,
      "The broker/DP must send the client a daily consolidated summary of scrip-wise positions by SMS/email.",
      actor="Stock Broker / Depository Participant", action="send consolidated summary", obj="scrip-wise buy/sell positions",
      frequency="daily", difficulty="medium", tags=["multi-actor"]),

    # DDPI (sec 36)
    mkobl("36.1", 86, 'While executing a PoA, authorization is given by client to the stock broker / stock broker and depository participant, to access the Beneficial Owner (BO) account of the client to meet settlement obligations', False,
      tags=["negative", "informational"], difficulty="medium",
      notes="Introductory/descriptive framing of DDPI vs PoA; obligations follow in later sub-paras."),
    mkobl("36.3", 87, 'shall be executed only if the client provides his/her explicit consent for the same, including internet based trading. The DDPI shall also be adequately stamped', True,
      "A DDPI may be executed only with the client's explicit consent and must be adequately stamped.",
      actor="Stock Broker", action="execute DDPI with consent", obj="Demat Debit and Pledge Instruction (DDPI)",
      conditions=["client provides explicit consent"], evidence="adequately stamped DDPI",
      difficulty="medium", tags=["conditional"]),
    mkobl("36.4", 87, 'the stock broker/stock broker and depository participant shall not directly / indirectly compel the clients to execute the DDPI or deny services to the client if the client refuses to execute the DDPI', True,
      "Brokers/DPs must not compel a client to execute a DDPI nor deny services for refusing.",
      actor="Stock Broker / Depository Participant", action="not compel / not deny services", obj="DDPI execution",
      conditions=["client refuses to execute the DDPI"], difficulty="medium", tags=["conditional", "multi-actor"]),
    mkobl("36.6", 87, 'the Depositories shall ensure matching and confirming the transfer of securities with client-wise net delivery obligation arising from the trade executed on the exchange', True,
      "Depositories must match/confirm DDPI securities transfers against client-wise net delivery obligations.",
      actor="Depositories", action="match & confirm transfer", obj="securities transfer vs net delivery obligation",
      difficulty="hard", tags=["cross-reference"]),
    mkobl("36.7", 87, 'The DDPI provided by the client shall be registered in the demat account of the client by TM /CM', True,
      "The TM/CM must register the client-provided DDPI in the client's demat account.",
      actor="Trading Member / Clearing Member", action="register DDPI", obj="client demat account",
      difficulty="medium", tags=["multi-actor"]),

    # Margin trading facility (sec 38)
    mkobl("38.2.4", 91, 'Stock Brokers shall ensure maintenance of the aforesaid margin at all times during the period that the margin trading facility is being availed by the client', True,
      "Brokers must ensure the required margin is maintained at all times while a client avails margin trading.",
      actor="Stock Brokers", action="ensure margin maintained", obj="margin trading margin",
      difficulty="medium", tags=["conditional"]),
    mkobl("38.5.3", 92, 'The stock broker shall not use the funds of any client for providing the margin trading facility to another client, even if the same is authorized by the first client', True,
      "Brokers must not use one client's funds to fund another client's margin trading, even if authorized.",
      actor="Stock Broker", action="not use client funds for another client", obj="client funds",
      difficulty="hard", tags=["conditional"], notes="Prohibition with an explicit no-exception ('even if authorized')."),
    mkobl("38.9.1", 94, 'The stock broker shall maintain separate client-wise ledgers for funds and securities of clients availing margin trading facility', True,
      "Brokers must maintain separate client-wise ledgers for funds and securities under margin trading.",
      actor="Stock Broker", action="maintain client-wise ledgers", obj="margin-trading funds and securities",
      difficulty="medium"),
    mkobl("38.4.3", 91, 'The stock brokers shall submit to the Stock Exchange a half-yearly', True,
      "Brokers must submit a half-yearly auditor certificate (as on 31 March / 30 September) confirming net worth.",
      actor="Stock Brokers", action="submit certificate", obj="net-worth certificate", frequency="half-yearly",
      deadline="as on 31st March and 30th September of each year", evidence="auditor certificate confirming net worth",
      difficulty="hard", tags=["implicit-deadline"]),
    mkobl("38.10.4", 95, 'The stock brokers wishing to extend margin trading facility to their clients shall be required to obtain prior permission from the exchange where the margin trading facility is proposed to be offered', True,
      "Brokers must obtain prior exchange permission before offering margin trading facility.",
      actor="Stock Brokers", action="obtain prior permission", obj="margin trading facility",
      conditions=["wishing to extend margin trading facility"], difficulty="medium", tags=["conditional"]),

    # Margin collection/reporting (sec 39-42)
    mkobl("39.1.1", 95, "The 'margins' for this purpose shall mean VaR margin, extreme loss margin (ELM), mark to market margin (MTM), delivery margin, special / additional margin or any other margin as prescribed by the Exchange", False,
      tags=["negative", "definition"], difficulty="hard",
      notes="Uses 'shall mean' — a definition, not an obligation. Key precision test: system must not extract an obligation from a definitional 'shall'."),
    mkobl("39.1.2", 95, 'the TMs/CMs in cash segment are also required to mandatorily collect upfront VaR margins and ELM from their clients. The TMs/CMs will have time till', True,
      "TMs/CMs must mandatorily collect upfront VaR margin and ELM from clients; other margins by T+2.",
      actor="Trading Member / Clearing Member", action="collect upfront margins", obj="VaR margin and ELM",
      deadline="upfront (VaR/ELM); T+2 working days for other margins", difficulty="hard",
      tags=["conditional", "multi-actor"]),
    mkobl("39.1.8", 96, 'the TMs/CMs shall report to the Stock Exchange on T+5 day the actual short-collection/ non-collection of all margins from clients', True,
      "TMs/CMs must report actual short/non-collection of all client margins to the exchange on T+5.",
      actor="Trading Member / Clearing Member", action="report short/non-collection", obj="client margin short-collection",
      deadline="T+5 day", frequency="on-occurrence", difficulty="hard", tags=["implicit-deadline", "multi-actor"],
      notes="Candidate for deadline-tightening diff checks against the Jun-2025 circular."),
    mkobl("40.2", 97, 'Clearing Corporations shall send minimum four snapshots of client wise margin requirement to TMs/CMs', True,
      "Clearing Corporations must send at least four client-wise margin snapshots per day to TMs/CMs.",
      actor="Clearing Corporations", action="send margin snapshots", obj="client-wise margin requirement",
      frequency="daily", deadline="minimum four snapshots in a day", difficulty="medium", tags=["multi-actor"]),
    mkobl("41.1", 98, "TM / CM shall, inter alia, accept collateral from clients in the form of securities, only by way of 'margin pledge', created in the Depository system", True,
      "TMs/CMs must accept securities collateral from clients only via a margin pledge in the depository system.",
      actor="Trading Member / Clearing Member", action="accept collateral only via margin pledge", obj="securities collateral",
      difficulty="medium", tags=["cross-reference", "multi-actor"]),
    mkobl("42.2", 105, 'a reporting mechanism, covering both cash and non-cash collateral, shall be specified by the CCs', True,
      "Clearing Corporations must specify a reporting mechanism covering cash and non-cash collateral.",
      actor="Clearing Corporations", action="specify reporting mechanism", obj="client collateral reporting",
      difficulty="medium"),
    mkobl("45.1.7", 119, 'TM / CM shall invoke the pledge only against the delivery obligation of the client', True,
      "TMs/CMs must invoke a client's pledge only against that client's delivery obligation.",
      actor="Trading Member / Clearing Member", action="invoke pledge only vs delivery obligation", obj="client pledge",
      difficulty="medium", tags=["multi-actor"]),
    mkobl("44.1", 116, "shares will be blocked in the demat account of the client in favour of Clearing Corporation. If sale transaction is not executed, shares shall continue to remain in the client's demat account", True,
      "Under the block mechanism, on a client sale the shares are blocked in the client's demat in favour of the CC.",
      actor="Depository / Clearing Corporation", action="block shares", obj="client securities for sale",
      conditions=["client intends to make a sale transaction"], difficulty="medium", tags=["conditional"]),

    # Running account (sec 47)
    mkobl("47.1.1", 122, 'The TM, after considering the End of the Day (EOD) obligation of funds across all the Exchanges, shall settle the running accounts at the choice of the clients on quarterly and monthly basis', True,
      "TMs must settle running accounts on the client's chosen quarterly/monthly cadence, considering EOD obligations.",
      actor="Trading Member", action="settle running accounts", obj="client running account", frequency="quarterly",
      difficulty="medium"),
    mkobl("47.1.3", 122, 'TM shall ensure that funds, if any, received from clients, whose running account has been settled, remain in the "Up Streaming Client Nodal Bank Account" and no such funds shall be used for settlement of running account of other clients', True,
      "TMs must keep settled clients' funds in the upstreaming nodal account and not use them for other clients.",
      actor="Trading Member", action="ring-fence settled client funds", obj="client funds in nodal account",
      difficulty="medium", notes="Anti-commingling obligation."),
    mkobl("50.2", 126, 'The processes specified at para 50.1 above, shall not be applicable to clients having arrangements with custodians registered with SEBI for clearing and settlement of trades', False,
      tags=["negative", "informational", "cross-reference"], difficulty="medium",
      notes="Carve-out/exception clause — states non-applicability, not an obligation."),

    # ── IV. Technology ─────────────────────────────────────────────────
    mkobl("52.2.2", 131, 'The stock exchange, before giving permission to brokers to start Internet based services shall ensure the fulfilment of the following minimum conditions', True,
      "Stock exchanges must ensure minimum conditions are met before permitting a broker's internet-based services.",
      actor="Stock Exchange", action="ensure conditions before permission", obj="internet-based trading permission",
      difficulty="medium", tags=["conditional"]),
    mkobl("54.3.10", 139, "The broker's server routing orders to the exchange trading system shall be located in India", True,
      "A broker's order-routing server for wireless trading must be located in India.",
      actor="Broker", action="locate routing server in India", obj="order-routing server", difficulty="easy"),
    mkobl("54.3.11", 139, 'Stock exchanges shall arrange for periodic systems audits of broker systems to ensure that requirements specified in the circulars are being met', True,
      "Stock exchanges must arrange periodic system audits of broker systems.",
      actor="Stock exchanges", action="arrange periodic system audits", obj="broker systems", frequency="on-occurrence",
      difficulty="medium", tags=["cross-reference"]),
    mkobl("55.1.1", 139, 'The broker shall capture the IP (Internet Protocol) address (from where the orders are originating), for all IBT/ STWT orders', True,
      "Brokers must capture the originating IP address for all IBT/STWT orders.",
      actor="Broker", action="capture IP address", obj="IBT/STWT orders", evidence="captured IP address",
      difficulty="easy"),
    mkobl("56.1", 140, 'Direct Market Access (DMA) is a facility which allows brokers to offer clients direct access to the exchange trading system through the broker’s infrastructure without manual intervention by the broker', False,
      tags=["negative", "definition"], difficulty="easy",
      notes="Definition of DMA; not an obligation."),
    mkobl("57.2.1", 151, 'Stock broker interested to offer Smart Order Routing facility shall apply to the respective stock exchanges', True,
      "A broker wishing to offer Smart Order Routing must apply to its stock exchanges.",
      actor="Stock broker", action="apply for SOR", obj="Smart Order Routing facility",
      conditions=["interested to offer Smart Order Routing"], difficulty="easy", tags=["conditional"]),
    mkobl("57.2.4", 152, 'Stock exchange shall communicate its decision to the broker within thirty calendar days from the date of receipt of complete application by the stock exchange', True,
      "The stock exchange must decide on a SOR application within thirty calendar days of a complete application.",
      actor="Stock exchange", action="communicate decision", obj="SOR application",
      deadline="within thirty calendar days from receipt of complete application", difficulty="medium",
      tags=["multi-actor"]),
    mkobl("57.2.9", 152, 'Stock broker shall maintain logs of all activities to facilitate audit trail', True,
      "Brokers must maintain logs of all SOR activities to enable an audit trail.",
      actor="Stock broker", action="maintain activity logs", obj="SOR activity logs", evidence="activity logs / audit trail",
      difficulty="easy"),
    mkobl("57.2.15", 153, 'The stock broker shall carry out appropriate validation of all risk parameters before the orders are placed in the Smart Order Routing system', True,
      "Brokers must validate all risk parameters before orders enter the SOR system.",
      actor="Stock broker", action="validate risk parameters", obj="orders in SOR system", difficulty="medium",
      tags=["conditional"]),
    mkobl("57.2.18", 153, 'Stock broker shall ensure that alternative mode of trading system is available in case of failure of Smart Order Routing facility', True,
      "Brokers must ensure an alternative trading mode is available if SOR fails.",
      actor="Stock broker", action="ensure alternative trading mode", obj="trading continuity",
      conditions=["failure of Smart Order Routing facility"], difficulty="medium", tags=["conditional"]),
    mkobl("57.2.22", 154, 'The broker server routing orders placed through Smart Order Routing system to the exchange trading system shall be located in India', True,
      "A broker's SOR order-routing server must be located in India.",
      actor="Broker", action="locate SOR routing server in India", obj="SOR routing server", difficulty="easy"),
    mkobl("58.1", 154, 'Any order that is generated using automated execution logic shall be known as algorithmic trading', False,
      tags=["negative", "definition"], difficulty="easy",
      notes="Definition of algorithmic trading via 'shall be known as'; not an obligation."),
    mkobl("59.2.2", 161, 'Stock brokers / trading members shall also engage system auditor(s) to examine reports of mock tests and UAT in order to certify that the tests were satisfactorily undertaken', True,
      "Brokers/TMs must engage system auditors to examine mock-test/UAT reports and certify them.",
      actor="Stock brokers / trading members", action="engage system auditors", obj="mock test / UAT reports",
      evidence="auditor certification", difficulty="hard", tags=["multi-actor"]),
    mkobl("59.4.1", 163, 'Stock brokers / trading members shall submit an undertaking to the respective stock exchanges', True,
      "Brokers/TMs using trading algorithms must submit an undertaking to their stock exchanges.",
      actor="Stock brokers / trading members", action="submit undertaking", obj="algorithmic trading undertaking",
      evidence="undertaking", difficulty="medium", tags=["multi-actor"]),
    mkobl("61.2", 166, 'The Stock Brokers are mandated to conduct comprehensive cyber audit at least once in a financial year', True,
      "Brokers must conduct a comprehensive cyber audit at least once per financial year and submit a compliance declaration.",
      actor="Stock Brokers", action="conduct cyber audit", obj="cyber security posture", frequency="yearly",
      deadline="at least once in a financial year",
      evidence="cyber audit report + MD/CEO/Partner/Proprietor compliance declaration", difficulty="hard"),
    mkobl("62.1", 180, 'Any set of applications / software / programs / executable / systems (computer systems) –cumulatively called application and systems', False,
      tags=["negative", "definition"], difficulty="hard",
      notes="Scoping/definitional clause for the AI/ML reporting framework; not an obligation."),
    mkobl("64.2", 182, 'Technical glitch shall mean any malfunction in the systems of stock broker including malfunction in its hardware, software, networks, processes', False,
      tags=["negative", "definition"], difficulty="medium",
      notes="Definition of 'technical glitch' via 'shall mean'; not an obligation."),

    # ── V. Change in status ────────────────────────────────────────────
    mkobl("67.3", 192, 'The Stock Exchanges shall submit a periodical report with details of the changes in status or constitution of the members, as per the format and in accordance with guidelines given at Annexure-33', True,
      "Stock exchanges must submit periodical reports on members' change in status/constitution per Annexure-33.",
      actor="Stock Exchanges", action="submit periodical report", obj="members' change in status/constitution",
      frequency="on-occurrence", difficulty="medium", tags=["cross-reference"]),
    mkobl("12.1", 17, 'The transferee shall obtain fresh registration from SEBI in the same capacity before the transfer of business if it is not registered with SEBI in the same capacity', True,
      "A transferee not already registered in the same capacity must obtain fresh SEBI registration before transfer.",
      actor="Transferee intermediary", action="obtain fresh registration", obj="SEBI registration",
      conditions=["not registered with SEBI in the same capacity"], deadline="before the transfer of business",
      difficulty="hard", tags=["conditional"]),
    mkobl("11.2", 17, 'All applications for registration / surrender / other requests shall be made through SEBI Intermediary Portal only', True,
      "All registration/surrender/other requests must be made only through the SEBI Intermediary Portal.",
      actor="Stock Broker", action="submit via SEBI Intermediary Portal", obj="registration/surrender requests",
      difficulty="easy"),

    # ── VII. Grievance / Investor charter ──────────────────────────────
    mkobl("72.1", 201, 'All the registered stock brokers shall designate an e-mail ID of the grievance redressal division/compliance officer exclusively for the purpose of registering complaints by investors', True,
      "Brokers must designate an exclusive grievance-redressal email ID for investor complaints and display it.",
      actor="Stock Brokers", action="designate grievance email ID", obj="investor complaints channel",
      difficulty="medium"),
    mkobl("73.1", 201, 'SEBI commenced processing of investor complaints in a centralized web based complaints redress system', False,
      tags=["negative", "informational"], difficulty="easy",
      notes="Descriptive of the SCORES system; not an obligation on a regulated entity."),
    mkobl("74.2", 202, 'Stock Brokers shall bring the Investor Charter to the notice of their clients', True,
      "Brokers must bring the Investor Charter to the notice of existing and new clients.",
      actor="Stock Brokers", action="bring Investor Charter to notice", obj="Investor Charter", difficulty="easy"),

    # ── VIII. Default / IX. Misc ───────────────────────────────────────
    mkobl("37.8", 89, 'Stock exchanges shall submit a report to SEBI every quarter regarding all such client code modifications where penalties have been waived', True,
      "Stock exchanges must submit a quarterly report to SEBI on penalty-waived client-code modifications.",
      actor="Stock exchanges", action="submit quarterly report", obj="client-code modification waivers",
      frequency="quarterly", difficulty="medium"),
    mkobl("37.9", 89, 'Stock exchanges shall undertake stringent disciplinary actions against stock brokers who undertake frequent client code modifications', True,
      "Stock exchanges must take stringent disciplinary action against brokers with frequent client-code modifications.",
      actor="Stock exchanges", action="take disciplinary action", obj="frequent client-code modifications",
      difficulty="medium", tags=["conditional"]),
    mkobl("78.1", 212, 'The Stock Exchanges shall ensure that brokers do not issue advertisements of their business, including in their internet sites, by subsidiaries, group companies etc. in contravention to Clause C(4) and C(5) of the Code of Conduct', True,
      "Stock exchanges must ensure brokers do not issue advertisements contravening the Code of Conduct.",
      actor="Stock Exchanges", action="ensure compliant advertising", obj="broker advertisements",
      difficulty="medium", tags=["cross-reference"]),
    mkobl("79.1", 212, 'Stock Exchanges shall quote SEBI Registration Number of the concerned Broker quoted on all correspondences with SEBI relating to them', True,
      "Stock exchanges must quote the broker's SEBI registration number on all SEBI correspondence.",
      actor="Stock Exchanges", action="quote SEBI registration number", obj="correspondence with SEBI", difficulty="easy"),
    mkobl("80.1", 212, 'every recognized stock exchange and its members are required to maintain and preserve the specified books of account and documents for a period ranging from two years to five years', True,
      "Exchanges and members must maintain and preserve specified books/documents for two to five years.",
      actor="Stock exchange and its members", action="maintain & preserve records", obj="books of account and documents",
      deadline="two years to five years", difficulty="hard", tags=["cross-reference", "multi-actor", "implicit-deadline"]),
    mkobl("81.1", 213, 'While a stock broker may use the brand name / logo of its group companies, it must display more prominently', True,
      "If a broker uses a group brand/logo, it must more prominently display its own SEBI-registered identity.",
      actor="Stock broker", action="display own identity prominently", obj="brand/identity display",
      conditions=["broker uses the brand name/logo of its group companies"], difficulty="medium", tags=["conditional"]),
    mkobl("83.3", 215, 'Outsourcing may be defined as the use of one or more than one third party – either within or outside the group – by a registered intermediary to perform the activities associated with services which the intermediary offers', False,
      tags=["negative", "definition"], difficulty="medium",
      notes="Definition of outsourcing; not an obligation."),
    mkobl("84.2", 222, 'Stock Brokers shall adhere to these guidelines for avoiding or dealing with or managing conflict of interest', True,
      "Brokers must adhere to the guidelines for managing conflicts of interest.",
      actor="Stock Brokers", action="adhere to conflict-of-interest guidelines", obj="conflict of interest",
      difficulty="easy", tags=["cross-reference"]),
    mkobl("2.4", 41, 'The Auditor shall not have any conflict of interest in conducting fair, objective and independent audit of the stock broker', True,
      "The system auditor must have no conflict of interest in auditing the stock broker.",
      actor="Auditor", action="avoid conflict of interest", obj="system audit independence", difficulty="medium",
      notes="Obligation cast on the auditor (non-broker actor)."),
    mkobl("2.1", 41, 'The Auditor shall have minimum three years of experience in IT audit of securities market participants', True,
      "The system auditor must have at least three years' IT-audit experience with securities-market participants.",
      actor="Auditor", action="meet experience threshold", obj="auditor eligibility", difficulty="medium"),

    # Upstreaming / nodal accounts (sec 93) & IRRA (sec 88)
    mkobl("93.2", 231, 'Stock brokers shall maintain the following designated bank account (s) to receive/pay funds from/to their clients', True,
      "Brokers must maintain the designated bank accounts prescribed for receiving/paying client funds.",
      actor="Stock brokers", action="maintain designated bank accounts", obj="client fund accounts", difficulty="medium"),
    mkobl("93.8", 232, 'SBs/CMs shall ensure that client funds are invested only in such MFOS that deploy funds into risk-free government bond overnight repo markets and overnight Tri-party Repo Dealing and Settlement (TREPS)', True,
      "SBs/CMs must ensure client funds are invested only in qualifying risk-free overnight instruments (MFOS/TREPS).",
      actor="Stock Brokers / Clearing Members", action="restrict investment of client funds", obj="client funds investment",
      difficulty="hard", tags=["multi-actor", "conditional"]),
    mkobl("88.3.12", 227, 'The TM shall continue to be responsible for all the activities on the IRRA with respect to all obligations including settlement and margin requirements', True,
      "The TM remains responsible for all IRRA activities, including settlement and margin obligations.",
      actor="Trading Member", action="remain responsible for IRRA activities", obj="IRRA obligations",
      difficulty="medium", notes="Investor Risk Reduction Access (IRRA) responsibility."),
    mkobl("92.4", 230, 'SBs/CMs shall be required to provide a certificate, by its statutory auditor confirming the implementation of provisions at para 91 of this circular', True,
      "SBs/CMs must provide a statutory-auditor certificate confirming implementation of the para-91 provisions.",
      actor="Stock Brokers / Clearing Members", action="provide auditor certificate", obj="implementation certificate",
      evidence="statutory auditor certificate", difficulty="medium", tags=["cross-reference", "multi-actor"]),

    # A few more client-dealing obligations for breadth
    mkobl("13.2.4", 20, 'The Stock Exchange/Clearing Corporation shall analyze the audit reports so received and take appropriate follow up action', True,
      "Exchanges/CCs must analyze received audit reports and take appropriate follow-up action.",
      actor="Stock Exchange / Clearing Corporation", action="analyze reports & follow up", obj="audit reports",
      difficulty="easy", tags=["multi-actor"]),
    mkobl("33.2.1", 78, 'Stock Exchanges shall provide a platform to stock brokers to upload the details of their clients', True,
      "Stock exchanges must provide a platform for brokers to upload client details.",
      actor="Stock Exchanges", action="provide upload platform", obj="client details platform", difficulty="easy"),
    mkobl("57.2.21", 154, 'Stock exchange shall synchronise their system clocks with atomic clock before the start of market', True,
      "Stock exchanges must synchronise system clocks with the atomic clock before market open.",
      actor="Stock exchange", action="synchronise system clocks", obj="system clocks",
      deadline="before the start of market", difficulty="easy"),
    mkobl("38.3.1", 91, 'The stock broker shall list out situations/conditions in which the securities may be liquidated and such situations/conditions shall be included in the "Rights and Obligations Document"', True,
      "Brokers must list securities-liquidation situations and include them in the Rights and Obligations Document.",
      actor="Stock broker", action="list & document liquidation conditions", obj="Rights and Obligations Document",
      difficulty="medium", tags=["cross-reference"]),
    mkobl("38.7.2", 93, 'The Stock Exchanges shall disclose on their websites the scrip wise gross outstanding in margin accounts with all brokers to the market', True,
      "Stock exchanges must disclose scrip-wise gross outstanding in margin accounts on their websites.",
      actor="Stock Exchanges", action="disclose scrip-wise outstanding", obj="margin account outstanding", difficulty="medium"),
    mkobl("10.3", 16, 'Prior approval from SEBI will be required to be obtained by the stock broker only in cases where integration leads to change in control of the stock broker/clearing member', True,
      "Brokers must obtain prior SEBI approval where integration leads to a change in control.",
      actor="Stock broker", action="obtain prior SEBI approval", obj="change in control",
      conditions=["integration leads to change in control"], difficulty="medium", tags=["conditional"]),
    mkobl("12.3", 18, 'If the transferor ceases to exist, its certificate of registration shall be surrendered', True,
      "If the transferor ceases to exist, its certificate of registration must be surrendered.",
      actor="Transferor intermediary", action="surrender registration certificate", obj="certificate of registration",
      conditions=["transferor ceases to exist"], difficulty="easy", tags=["conditional"]),
    mkobl("32.7.1", 76, 'The stock broker shall be responsible for all acts of omission and commission of his authorised person(s) and/or their employees, including liabilities arising there from', True,
      "The broker is responsible for all acts/omissions of its authorised persons and their employees.",
      actor="Stock broker", action="bear responsibility", obj="acts of authorised persons", difficulty="medium"),
    mkobl("20.13", 61, 'Stock Exchanges / stock brokers shall continue to make the documents mentioned in para 20.1.3 to 20.1.5 above, available on their website', True,
      "Exchanges/brokers must keep the specified account-opening documents available on their websites.",
      actor="Stock Exchanges / stock brokers", action="publish documents on website", obj="account-opening documents",
      difficulty="easy", tags=["multi-actor", "cross-reference"]),
    mkobl("54.3.11b", 139, 'Stock exchange shall also include securities trading using wireless technology in their ongoing investor awareness and educational programme', True,
      "Stock exchanges must include wireless-technology trading in their investor awareness programmes.",
      actor="Stock exchange", action="include in investor awareness", obj="wireless trading awareness", difficulty="easy",
      notes="clause_ref reflects para 54.3.12 in the body; kept distinct id."),

    # ── additional breadth (supervision, AP, SOR, algo, IRRA, registration) ──
    mkobl("14.2.1", 22, 'Stock Brokers servicing investors, getting disabled on account of funds shortages on more than three times in a month shall be inspected irrespective of the fact of when they were last inspected', True,
      "Brokers disabled for funds shortage more than thrice a month must be inspected regardless of last inspection.",
      actor="Stock Exchanges", action="inspect", obj="stock brokers with frequent disablement",
      conditions=["funds-shortage disablement more than three times in a month"], difficulty="medium", tags=["conditional"]),
    mkobl("13.3.3", 21, 'The Stock Exchanges / Clearing Corporations shall take appropriate action against the associates of defaulter member', True,
      "Exchanges/CCs must take appropriate action against associates of a defaulter member.",
      actor="Stock Exchanges / Clearing Corporations", action="take action against associates", obj="associates of defaulter member",
      difficulty="easy", tags=["multi-actor"]),
    mkobl("32.8.1", 77, 'The Stock Exchange shall maintain a database of all the authorised persons which shall include the following', True,
      "Stock exchanges must maintain a database of all authorised persons.",
      actor="Stock Exchange", action="maintain database", obj="authorised persons database", difficulty="medium"),
    mkobl("33.2.4", 79, 'Stock Brokers shall ensure that separate mobile number/E-mail address is uploaded for each client', True,
      "Brokers must ensure a separate mobile/email is uploaded for each client.",
      actor="Stock Brokers", action="ensure per-client contact", obj="client mobile/email", difficulty="easy"),
    mkobl("38.8.1", 93, 'The Stock Exchanges shall frame a Rights and Obligations document laying down the rights and obligations of stock brokers and clients for the purpose of margin trading facility', True,
      "Stock exchanges must frame a Rights and Obligations document for margin trading.",
      actor="Stock Exchanges", action="frame Rights and Obligations document", obj="margin trading rights/obligations",
      difficulty="medium", tags=["cross-reference"]),
    mkobl("38.9.2", 94, 'The stock broker shall maintain a separate record of details of the funds used and sources of funds for the purpose of margin trading', True,
      "Brokers must maintain a separate record of funds used and their sources for margin trading.",
      actor="Stock broker", action="maintain funds record", obj="margin trading funds/sources", difficulty="medium"),
    mkobl("57.2.2", 152, 'Stock broker shall submit a third party system audit of its Smart Order Routing system and software', True,
      "Brokers must submit a third-party system audit of their SOR system and software.",
      actor="Stock broker", action="submit third-party audit", obj="SOR system and software",
      evidence="third-party system audit", difficulty="medium"),
    mkobl("57.2.6", 152, 'Stock exchange shall ensure that brokers adhere to the best execution policy while using Smart Order Routing', True,
      "Stock exchanges must ensure brokers adhere to best-execution policy when using SOR.",
      actor="Stock exchange", action="ensure best-execution adherence", obj="Smart Order Routing", difficulty="medium"),
    mkobl("57.2.14", 153, 'Stock exchange shall ensure that Smart Order Routing is not used to place orders at venues other than the recognised stock exchanges', True,
      "Stock exchanges must ensure SOR is not used to route orders to unrecognised venues.",
      actor="Stock exchange", action="ensure venue restriction", obj="SOR order venues", difficulty="medium"),
    mkobl("57.2.17", 153, 'Stock exchange shall have necessary surveillance mechanism in place to monitor trading done through Smart Order Routing', True,
      "Stock exchanges must have a surveillance mechanism to monitor SOR trading.",
      actor="Stock exchange", action="maintain surveillance mechanism", obj="SOR trading", difficulty="medium"),
    mkobl("59.2.3", 161, 'Stock exchanges shall monitor compliance of stock brokers / trading members, who use trading algorithm, with regard to the requirement of participation in mock trading session', True,
      "Stock exchanges must monitor algo-using brokers'/TMs' compliance with mock-trading participation.",
      actor="Stock exchanges", action="monitor compliance", obj="mock-trading participation",
      conditions=["brokers/TMs who use trading algorithm"], difficulty="medium", tags=["conditional"]),
    mkobl("88.5", 228, 'Stock exchanges shall issue guidelines in this regard giving details like cut-off times for enablement of IRRA service', True,
      "Stock exchanges must issue IRRA guidelines including enablement cut-off times.",
      actor="Stock exchanges", action="issue IRRA guidelines", obj="IRRA service guidelines", difficulty="medium"),
    mkobl("92.5", 230, 'Stock exchanges and clearing corporations shall verify the compliance of the provisions of the circular in their periodic inspections/reporting', True,
      "Exchanges and CCs must verify circular compliance in their periodic inspections/reporting.",
      actor="Stock exchanges and clearing corporations", action="verify compliance", obj="circular provisions",
      frequency="on-occurrence", difficulty="medium", tags=["multi-actor"]),
    mkobl("93.9", 232, 'SBs/CMs shall maintain a dedicated demat account', True,
      "SBs/CMs must maintain a dedicated demat account (Client Nodal MFOS Account) for MFOS units.",
      actor="Stock Brokers / Clearing Members", action="maintain dedicated demat account", obj="Client Nodal MFOS Account",
      difficulty="medium", tags=["multi-actor"]),
    mkobl("8.3", 15, 'The minimum net worth specified for members of commodity derivatives exchanges, shall have to be computed as prescribed in the Stock Brokers Regulations 1992', True,
      "Commodity-derivatives-exchange members' minimum net worth must be computed per the Stock Brokers Regulations 1992.",
      actor="Member (commodity derivatives exchange)", action="compute minimum net worth", obj="net worth",
      difficulty="medium", tags=["cross-reference"]),
    mkobl("12.2", 18, 'prior approval and fresh registration shall be obtained', True,
      "On a change in control (regulatory or non-regulatory process), prior approval and fresh registration must be obtained.",
      actor="Intermediary undergoing change in control", action="obtain prior approval & fresh registration", obj="change in control",
      conditions=["change in control via regulatory or non-regulatory process"], difficulty="hard", tags=["conditional"]),
    mkobl("2.5", 41, 'The Auditor shall not have any cases pending against its previous audited companies/firms, which fall under SEBI’s jurisdiction', True,
      "The system auditor must have no SEBI-jurisdiction cases pending against its previously audited firms.",
      actor="Auditor", action="be free of pending cases", obj="auditor eligibility", difficulty="medium"),
]


# ── change-set authoring ──────────────────────────────────────────────
def mkchg(ctype, summary, old_ref, new_ref, old_text, new_text, changed_fields,
      materiality, notes):
    return {
        "change_type": ctype, "obligation_summary": summary,
        "old_ref": old_ref, "new_ref": new_ref,
        "old_text": old_text, "new_text": new_text,
        "changed_fields": changed_fields, "materiality_expected": materiality,
        "notes": notes,
    }


# old_text validated against Aug-2024; new_text against Jun-2025.
CHANGES = [
    # ── CREATED: genuinely new sections in Jun-2025 (verified absent in Aug) ──
    mkchg("CREATED", "New framework: technology-based monitoring & supervision of stock-broker system audits",
      None, "Jun-2025 §17",
      None,
      "Framework for Monitoring and Supervision of System Audit of Stock Brokers (SBs) through Technology based Measures",
      [], "HIGH",
      "Entirely new section (0 occurrences in Aug-2024). Introduces a supervisory tech layer over system audits; its insertion is what shifts all subsequent Aug sections by +1 in Jun."),
    mkchg("CREATED", "New obligation: exchanges to build a web platform monitoring the whole system-audit lifecycle",
      None, "Jun-2025 §17.1",
      None,
      "Stock Exchanges shall develop web portal/ web based platform and create technology based mechanisms to monitor and supervise the entire system audit lifecycle of a stock broker",
      [], "HIGH",
      "New obligation on stock exchanges within the new §17."),
    mkchg("CREATED", "New obligation: capture auditor geo-location to confirm physical premises visit",
      None, "Jun-2025 §17.1",
      None,
      "exchanges shall capture the geo location of the auditor to ensure that physical visit is carried out by auditor in the premises of the stock broker",
      [], "MEDIUM",
      "New anti-fraud control on the audit process; no analogue in Aug-2024."),
    mkchg("CREATED", "New section: GIFT-IFSC Separate Business Unit facilitation for stock brokers",
      None, "Jun-2025 §71",
      None,
      "Facilitation to SEBI registered Stock Brokers to undertake securities market related activities in Gujarat International Finance Tech-city",
      [], "MEDIUM",
      "New section (0 occurrences in Aug-2024) enabling a Separate Business Unit (SBU) in GIFT-IFSC."),
    mkchg("CREATED", "New section: access to NDS-OM for trading in Government Securities via an SBU",
      None, "Jun-2025 §72",
      None,
      "Facilitation to SEBI registered Stock Brokers to access Negotiated Dealing System-Order Matching (NDS-OM) for trading in Government Securities",
      [], "MEDIUM",
      "New section (NDS-OM absent in Aug-2024)."),
    mkchg("CREATED", "New section: association of Board-regulated persons and their agents with certain persons",
      None, "Jun-2025 §88",
      None,
      "Association of persons regulated by the Board and their agents with certain persons",
      [], "MEDIUM",
      "New misc-part section (0 occurrences in Aug-2024)."),

    # ── MODIFIED: verified textual change ──────────────────────────────
    mkchg("MODIFIED", "Section title scope narrowed: 'Review of norms relating to trading by Members/ Sub-Brokers' -> '...by Members'",
      "Aug-2024 §31 (TOC)", "Jun-2025 §32 (TOC)",
      "Review of norms relating to trading by Members/ Sub-Brokers",
      "Review of norms relating to trading by Members",
      ["object"], "LOW",
      "Sub-Brokers reference dropped from the section title (sub-broker category has been phased out). Substance largely unchanged; low materiality."),

    # ── NOT_A_CHANGE: cosmetic renumberings (identical title/substance, +1) ──
    mkchg("NOT_A_CHANGE", "Section renumbered only: Enhanced obligations on QSBs (18 -> 19)",
      "Aug-2024 §18", "Jun-2025 §19",
      "18. Enhanced obligations and responsibilities on Qualified Stock Brokers (QSBs)",
      "19. Enhanced obligations and responsibilities on Qualified Stock Brokers (QSBs)",
      ["clause_number_only"], "NONE",
      "Confirmed by body diff: substance identical; only the number shifted due to the new §17."),
    mkchg("NOT_A_CHANGE", "Section renumbered only: Unique Client Code (19 -> 20)",
      "Aug-2024 §19", "Jun-2025 §20",
      "19. Unique Client Code", "20. Unique Client Code",
      ["clause_number_only"], "NONE", "Cosmetic renumbering."),
    mkchg("NOT_A_CHANGE", "Section renumbered only: Requirements relating to dealings between a Client and a Stock Broker (22 -> 23)",
      "Aug-2024 §22", "Jun-2025 §23",
      "22. Requirements relating to dealings between a Client and a Stock Broker",
      "23. Requirements relating to dealings between a Client and a Stock Broker",
      ["clause_number_only"], "NONE", "Cosmetic renumbering."),
    mkchg("NOT_A_CHANGE", "Section renumbered only: Prevention of Unauthorised Trading by Stock Brokers (34 -> 35)",
      "Aug-2024 §34", "Jun-2025 §35",
      "34. Prevention of Unauthorised Trading by Stock Brokers",
      "35. Prevention of Unauthorised Trading by Stock Brokers",
      ["clause_number_only"], "NONE", "Cosmetic renumbering."),
    mkchg("NOT_A_CHANGE", "Section renumbered only: Execution of Power of Attorney (PoA) (35 -> 36)",
      "Aug-2024 §35", "Jun-2025 §36",
      "35. Execution of Power of Attorney (PoA) by the Client in favour of the Stock Broker",
      "36. Execution of Power of Attorney (PoA) by the Client in favour of the Stock Broker",
      ["clause_number_only"], "NONE",
      "IMPORTANT honesty note: the 'DDPI replaces PoA' change predates this pair — both PoA (§35/§36) and DDPI (§36/§37) sections exist, substantively identical, in BOTH circulars. So it is a renumbering here, NOT a substantive change."),
    mkchg("NOT_A_CHANGE", "Section renumbered only: Execution of DDPI (36 -> 37)",
      "Aug-2024 §36", "Jun-2025 §37",
      "36. Execution of 'Demat Debit and Pledge Instruction' (DDPI) for transfer of securities",
      "37. Execution of 'Demat Debit and Pledge Instruction' (DDPI) for transfer of securities",
      ["clause_number_only"], "NONE", "Cosmetic renumbering; DDPI substance identical across the pair."),
    mkchg("NOT_A_CHANGE", "Section renumbered only: Collection and reporting of margins by TM/CM in Cash Segment (39 -> 40)",
      "Aug-2024 §39", "Jun-2025 §40",
      "39. Collection and reporting of margins by Trading Member (TM) /Clearing Member (CM) in Cash Segment",
      "40. Collection and reporting of margins by Trading Member (TM) /Clearing Member (CM) in Cash Segment",
      ["clause_number_only"], "NONE", "Cosmetic renumbering; margin-reporting substance unchanged."),
    mkchg("NOT_A_CHANGE", "Section renumbered only: Settlement of Running Account of Client's Funds lying with TM (47 -> 48)",
      "Aug-2024 §47", "Jun-2025 §48",
      "47. Settlement of Running Account of Client's Funds lying with Trading Member (TM)",
      "48. Settlement of Running Account of Client's Funds lying with Trading Member (TM)",
      ["clause_number_only"], "NONE", "Confirmed by body diff: substance identical; only number + embedded page numbers differ."),
    mkchg("NOT_A_CHANGE", "Section renumbered only: Enhancement of operational efficiency - Pay-out of securities directly to client demat (50 -> 51)",
      "Aug-2024 §50", "Jun-2025 §51",
      "50. Enhancement of operational efficiency and Risk Reduction-Pay-out of securities",
      "51. Enhancement of operational efficiency and Risk Reduction-Pay-out of securities",
      ["clause_number_only"], "NONE", "Cosmetic renumbering."),
    mkchg("NOT_A_CHANGE", "Section renumbered only: Electronic Contract Note (51 -> 52)",
      "Aug-2024 §51", "Jun-2025 §52",
      "51. Electronic Contract Note", "52. Electronic Contract Note",
      ["clause_number_only"], "NONE", "Cosmetic renumbering."),
    mkchg("NOT_A_CHANGE", "Section renumbered only: Cyber Security and Cyber resilience framework for Stock Brokers (61 -> 62)",
      "Aug-2024 §61", "Jun-2025 §62",
      "61. Cyber Security and Cyber resilience framework for Stock Brokers",
      "62. Cyber Security and Cyber resilience framework for Stock Brokers",
      ["clause_number_only"], "NONE",
      "Cosmetic renumbering; the cyber obligations (6-hour incident reporting, annual VAPT) exist in BOTH circulars."),
    mkchg("NOT_A_CHANGE", "Section unchanged in number and substance: Annual System Audit of Stock Brokers / Trading Members (16 -> 16)",
      "Aug-2024 §16", "Jun-2025 §16",
      "16. Annual System Audit of Stock Brokers / Trading Members",
      "16. Annual System Audit of Stock Brokers / Trading Members",
      [], "NONE",
      "Same number and substance (the new §17 was inserted AFTER §16). Included as a control: neither renumbered nor changed."),
]


# ── build / validate ──────────────────────────────────────────────────
def build():
    aug = load_pdf_text(AUG_PDF)
    jun = load_pdf_text(JUN_PDF)
    errors: list[str] = []

    # obligations
    ob_records = []
    for i, o in enumerate(OBLIGATIONS, start=1):
        q = prov_norm(o["quote"])
        if q not in aug:
            errors.append(f"obl {o['clause_ref']}: quote not found in Aug-2024 text: {o['quote'][:70]!r}")
        rec = {
            "id": f"obl-{i:04d}",
            "source": {"document": AUG_DOC, "clause_ref": o["clause_ref"], "exact_quote": o["quote"]},
            "is_obligation": o["is_obligation"],
            # Schema types normalized_obligation as a (non-null) string and marks it
            # optional; omit it for negative examples (is_obligation=false) rather
            # than emit null.
            **({"normalized_obligation": o["normalized_obligation"]}
               if o["normalized_obligation"] is not None else {}),
            "actor": o["actor"], "action": o["action"], "object": o["object"],
            "conditions": o["conditions"], "exceptions": o["exceptions"],
            "frequency": o["frequency"], "deadline": o["deadline"],
            "evidence_requirement": o["evidence_requirement"],
            "penalty_reference": o["penalty_reference"],
            "difficulty": o["difficulty"], "tags": o["tags"],
            "annotator_notes": o["notes"],
        }
        ob_records.append(rec)

    # changes
    ch_records = []
    for i, c in enumerate(CHANGES, start=1):
        if c["old_text"] is not None and prov_norm(c["old_text"]) not in aug:
            errors.append(f"chg {i}: old_text not found in Aug-2024: {c['old_text'][:70]!r}")
        if c["new_text"] is not None and prov_norm(c["new_text"]) not in jun:
            errors.append(f"chg {i}: new_text not found in Jun-2025: {c['new_text'][:70]!r}")
        ch_records.append({
            "id": f"chg-{i:04d}",
            "change_type": c["change_type"],
            "old_ref": c["old_ref"], "new_ref": c["new_ref"],
            "obligation_summary": c["obligation_summary"],
            "changed_fields": c["changed_fields"],
            "old_text": c["old_text"], "new_text": c["new_text"],
            "materiality_expected": c["materiality_expected"],
            "notes": c["notes"],
        })

    return ob_records, ch_records, errors


def composition(ob_records, ch_records):
    total = len(ob_records)
    pos = sum(1 for r in ob_records if r["is_obligation"])
    neg = total - pos
    from collections import Counter
    diff = Counter(r["difficulty"] for r in ob_records)
    tags = Counter(t for r in ob_records for t in r["tags"])
    ctypes = Counter(r["change_type"] for r in ch_records)
    print(f"\nOBLIGATIONS: {total} total  | positive={pos} negative={neg} ({neg*100//max(total,1)}%)")
    print(f"  difficulty: easy={diff['easy']} medium={diff['medium']} hard={diff['hard']}")
    print(f"  tags: {dict(tags)}")
    print(f"CHANGESET: {len(ch_records)} total  | {dict(ctypes)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="Validate only; do not write JSONL.")
    args = ap.parse_args()

    ob_records, ch_records, errors = build()

    if errors:
        print("VALIDATION FAILED — quotes not found in the real source documents:")
        for e in errors:
            print("  -", e)
        return 1
    print(f"Provenance validation PASSED: all {len(ob_records)} obligation quotes occur in Aug-2024; "
          f"all change texts occur in the correct document.")
    composition(ob_records, ch_records)

    if args.check:
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "obligations.jsonl"), "w") as f:
        for r in ob_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(OUT_DIR, "changeset.jsonl"), "w") as f:
        for r in ch_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(ob_records)} -> {OUT_DIR}/obligations.jsonl")
    print(f"Wrote {len(ch_records)} -> {OUT_DIR}/changeset.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
