import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def parse_date(value: Optional[str]) -> Optional[date]:
    if not value or not value.strip():
        return None
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def parse_decimal(value: Optional[str]) -> Decimal:
    if not value or not value.strip():
        return Decimal("0.00")
    try:
        return Decimal(value.strip()).quantize(Decimal("0.01"))
    except InvalidOperation as e:
        raise ValueError(f"Некорректная сумма: {value}") from e


class Contract:
    def __init__(self, contract_id: str, contractor: str, amount: Decimal, signed_at: Optional[date]):
        self.contract_id = contract_id
        self.contractor = contractor
        self.amount = amount
        self.signed_at = signed_at


class Work:
    def __init__(
        self,
        work_id: str,
        contract_id: str,
        title: str,
        price: Decimal,
        status: str,
        completed_at: Optional[date],
        cancelled_at: Optional[date],
    ):
        self.work_id = work_id
        self.contract_id = contract_id
        self.title = title
        self.price = price
        self.status = status
        self.completed_at = completed_at
        self.cancelled_at = cancelled_at


class Payment:
    def __init__(
        self,
        payment_id: str,
        contract_id: str,
        work_id: Optional[str],
        purpose: str,
        amount: Decimal,
        status: str,
        created_at: Optional[date],
        paid_at: Optional[date],
        refunded_at: Optional[date],
    ):
        self.payment_id = payment_id
        self.contract_id = contract_id
        self.work_id = work_id if work_id and work_id.strip() else None
        self.purpose = purpose
        self.amount = amount
        self.status = status
        self.created_at = created_at
        self.paid_at = paid_at
        self.refunded_at = refunded_at


def load_data(data_dir: Path) -> Tuple[Dict[str, Contract], List[Work], List[Payment]]:
    contracts_file = data_dir / "contracts.csv"
    works_file = data_dir / "works.csv"
    payments_file = data_dir / "payments.csv"

    if not contracts_file.exists():
        raise FileNotFoundError(f"Файл не найден: {contracts_file}")
    if not works_file.exists():
        raise FileNotFoundError(f"Файл не найден: {works_file}")
    if not payments_file.exists():
        raise FileNotFoundError(f"Файл не найден: {payments_file}")

    contracts: Dict[str, Contract] = {}
    with open(contracts_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row["contract_id"].strip()
            contracts[cid] = Contract(
                contract_id=cid,
                contractor=row["contractor"].strip(),
                amount=parse_decimal(row["amount"]),
                signed_at=parse_date(row.get("signed_at")),
            )

    works: List[Work] = []
    with open(works_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            works.append(
                Work(
                    work_id=row["work_id"].strip(),
                    contract_id=row["contract_id"].strip(),
                    title=row["title"].strip(),
                    price=parse_decimal(row["price"]),
                    status=row["status"].strip(),
                    completed_at=parse_date(row.get("completed_at")),
                    cancelled_at=parse_date(row.get("cancelled_at")),
                )
            )

    payments: List[Payment] = []
    with open(payments_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            payments.append(
                Payment(
                    payment_id=row["payment_id"].strip(),
                    contract_id=row["contract_id"].strip(),
                    work_id=row.get("work_id"),
                    purpose=row.get("purpose", "").strip(),
                    amount=parse_decimal(row["amount"]),
                    status=row["status"].strip(),
                    created_at=parse_date(row.get("created_at")),
                    paid_at=parse_date(row.get("paid_at")),
                    refunded_at=parse_date(row.get("refunded_at")),
                )
            )

    return contracts, works, payments
