"""Demo data for ENV=local and DEMO_MODE: Acme, its approvers, the four vendors
from the contract's GET /vendors example, and policy 2026.11.1 exactly as the
contract's GET /policies example states it (a test keeps the two equal).

Full account numbers here are made-up test values ending in the contract's last
four digits; Sri Lakshmi's matches the canonical test vectors.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.engine import unit_of_work
from app.db.models import (
    Approver,
    Company,
    OrgNode,
    OrgRule,
    Policy,
    Vendor,
    VendorBankAccount,
)

# ---- M2+ organisation tree ------------------------------------------------------------
# node_id, parent, kind, name, settings, rules [(code, text, CEL, min_tier, hard_flag)]
ORG = [
    (
        "org_acme_group",
        None,
        "group",
        "Acme Group",
        {},
        [
            (
                "very_large",
                "Above Rupees 1 crore: two people and a call-back.",
                "payment.amount_paise > 1000000000",
                3,
                False,
            ),
        ],
    ),
    (
        "org_acme",
        "org_acme_group",
        "company",
        "Acme Engineering",
        {},
        [
            (
                "new_payee_large",
                "A new payee above Rupees 10 lakh needs a Controller.",
                "payment.payee.is_new && payment.amount_paise > 100000000",
                2,
                True,
            ),
        ],
    ),
    (
        "org_acme_chennai",
        "org_acme",
        "plant",
        "Chennai plant",
        {"approval_windows_ist": ["11:00", "16:00"]},
        [],
    ),
    ("org_acme_ap", "org_acme_chennai", "department", "Accounts payable", {}, []),
    (
        "org_acme_treasury",
        "org_acme_chennai",
        "department",
        "Treasury",
        {"tier1_paise": 20000000},
        [],
    ),
]

# email, level, node. The M2 approvers gain a level and a place in the tree.
LEVELS = [
    ("ap.manager@acme.example", 1, "org_acme_ap"),
    ("controller@acme.example", 2, "org_acme_chennai"),
    ("cfo@acme.example", 3, "org_acme"),
    ("md@acme.example", 4, "org_acme_group"),
]

POLICY_2026_11_1 = {
    "version": "2026.11.1",
    "published_at": "2026-11-18T09:00:00+05:30",
    "tier_thresholds_paise": {"tier1": "50000000", "tier2": "250000000", "tier3": "10000000000"},
    "working_hours_ist": {"start": "09:00", "end": "19:00"},
    "rules": [
        {"code": "new_payee", "text": "First payment to this payee.", "enabled": True},
        {
            "code": "bank_details_changed",
            "text": "The payee's bank details changed in the last 30 days.",
            "enabled": True,
        },
        {
            "code": "amount_above_5_lakh",
            "text": "Amount is above Rupees 5,00,000.",
            "enabled": True,
        },
        {
            "code": "outside_working_hours",
            "text": "Raised outside 9 am to 7 pm IST.",
            "enabled": True,
        },
        {"code": "raised_by_agent", "text": "Raised by an AI agent.", "enabled": True},
        {
            "code": "instruction_by_chat",
            "text": "The instruction arrived by chat or email.",
            "enabled": True,
        },
    ],
    "approval_matrix": [
        {"up_to_paise": "250000000", "approvers": ["cfo@acme.example"]},
        {"up_to_paise": None, "approvers": ["cfo@acme.example", "md@acme.example"]},
    ],
}

APPROVERS = [
    ("apr_apm", "ap.manager@acme.example", "Meena Krishnan", "AP Manager"),
    ("apr_cfo", "cfo@acme.example", "Priya Raman", "CFO"),
    ("apr_md", "md@acme.example", "Arjun Mehta", "MD"),
    ("apr_ctrl", "controller@acme.example", "Kavya Iyer", "Controller"),
]

# vendor_id, legal name, gstin, months of history, accounts [(number, ifsc, name, days ago opened)]
VENDORS = [
    (
        "vd_sri_lakshmi",
        "Sri Lakshmi Castings",
        "33AABCS1429P1Z5",
        24,
        [("000123457781", "ABCD0123456", "Sri Lakshmi Castings", 730)],
    ),
    (
        "vd_kaveri_steel",
        "Kaveri Steel Traders",
        "33AAFCK9921M1Z8",
        18,
        [("556677885540", "EFGH0005540", "Kaveri Steel Traders", 540)],
    ),
    # The look-alike: a new vendor whose bank details changed three days ago.
    (
        "vd_sri_laxmi",
        "Sri Laxmi Castings",
        None,
        0,
        [
            ("000456781120", "IJKL0001120", "Sri Laxmi Castings", 10),
            ("000456783309", "IJKL0003309", "Sri Laxmi Castings", 3),
        ],
    ),
    (
        "vd_global_trade",
        "Global Trade Solutions",
        None,
        0,
        [("000112239032", "WXYZ0004411", "Global Trade Solutions", 2)],
    ),
]


def seed_if_empty(sessions: sessionmaker[Session], company_id: str = "co_acme") -> bool:
    with unit_of_work(sessions) as s:
        if s.scalar(select(Company).where(Company.company_id == company_id)):
            return False
        now = datetime.now(timezone.utc)
        s.add(
            Company(
                company_id=company_id,
                name="Acme Engineering Pvt Ltd",
                payer_account="50100004521",
                payer_ifsc="HDFC0000452",
                created_at=now,
            )
        )
        s.flush()
        for approver_id, email, name, role in APPROVERS:
            s.add(
                Approver(
                    approver_id=approver_id,
                    company_id=company_id,
                    email=email,
                    display_name=name,
                    role=role,
                    active=True,
                    created_at=now,
                )
            )
        for vendor_id, legal, gstin, months, accounts in VENDORS:
            s.add(
                Vendor(
                    vendor_id=vendor_id,
                    company_id=company_id,
                    legal_name=legal,
                    gstin=gstin,
                    onboarded_at=now - timedelta(days=30 * months + accounts[0][3] * (months == 0)),
                    created_at=now,
                )
            )
            s.flush()
            for i, (number, ifsc, bank_name, days_ago) in enumerate(accounts):
                nxt = accounts[i + 1][3] if i + 1 < len(accounts) else None
                s.add(
                    VendorBankAccount(
                        vendor_id=vendor_id,
                        account_number=number,
                        ifsc=ifsc,
                        name_at_bank=bank_name,
                        valid_from=now - timedelta(days=days_ago),
                        valid_to=None if nxt is None else now - timedelta(days=nxt),
                        changed_by=None if i == 0 else "clerk@acme.example",
                        verification=None if i == 0 else "not verified",
                    )
                )
        s.add(
            Policy(
                company_id=company_id,
                version=POLICY_2026_11_1["version"],
                document=POLICY_2026_11_1,
                active=True,
                published_at=datetime.fromisoformat(POLICY_2026_11_1["published_at"]),
            )
        )
    seed_m2plus_if_missing(sessions, company_id)
    return True


def seed_m2plus_if_missing(sessions: sessionmaker[Session], company_id: str = "co_acme") -> bool:
    """The M2+ organisation tree, its rules, and approver levels. Separate from the
    M2 seed so a local database made before M2+ gains them too."""
    with unit_of_work(sessions) as s:
        if s.get(OrgNode, ORG[0][0]) is not None:
            return False
        if s.get(Company, company_id) is None:
            return False
        now = datetime.now(timezone.utc)
        for node_id, parent, kind, name, settings, rules in ORG:
            s.add(
                OrgNode(
                    node_id=node_id,
                    parent_id=parent,
                    kind=kind,
                    name=name,
                    company_id=None if kind == "group" else company_id,
                    settings=settings,
                    created_at=now,
                )
            )
            s.flush()
            for code, text, expression, min_tier, hard in rules:
                s.add(
                    OrgRule(
                        rule_id=f"rl_{code}",
                        node_id=node_id,
                        code=code,
                        text=text,
                        expression=expression,
                        min_tier=min_tier,
                        hard_flag=hard,
                        enabled=True,
                        created_at=now,
                    )
                )
        s.flush()
        for email, level, node_id in LEVELS:
            approver = s.scalar(select(Approver).where(Approver.email == email))
            if approver is None:
                # A database seeded before M2+ lacks the AP Manager; add whoever is missing.
                approver_id, _, name, role = next(a for a in APPROVERS if a[1] == email)
                approver = Approver(
                    approver_id=approver_id,
                    company_id=company_id,
                    email=email,
                    display_name=name,
                    role=role,
                    active=True,
                    created_at=now,
                )
                s.add(approver)
            approver.level, approver.node_id = level, node_id
    return True
