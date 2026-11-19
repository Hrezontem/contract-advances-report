from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from parser import Contract, Work, Payment


ZERO = Decimal("0.00")


@dataclass
class WorkReportItem:
    work_id: str
    contract_id: str
    title: str
    status_on_date: str
    original_price: Decimal
    effective_price: Decimal
    paid_direct: Decimal
    paid_fifo: Decimal
    paid_total: Decimal
    remaining: Decimal
    is_disputed: bool = False  # прямой платёж по отменённой работе


@dataclass
class ContractReportItem:
    contract_id: str
    contractor: str
    contract_amount: Decimal
    works_amount_active: Decimal
    works_amount_total: Decimal
    total_paid: Decimal
    remaining_to_pay: Decimal
    unallocated_advance: Decimal
    budget_discrepancy: Decimal  # contract_amount - works_amount_active (контрольное расхождение)
    disputed_amount: Decimal     # прямые платежи по отменённым работам


@dataclass
class FinancialReport:
    as_of_date: date
    works_report: List[WorkReportItem]
    contracts_report: List[ContractReportItem]
    grand_total_contracts: Decimal
    grand_total_works: Decimal
    grand_total_paid: Decimal
    grand_total_remaining: Decimal
    grand_budget_discrepancy: Decimal
    grand_disputed_amount: Decimal


def determine_work_status_on_date(work: Work, as_of_date: date) -> str:
    if work.cancelled_at and work.cancelled_at <= as_of_date:
        return "cancelled"
    if work.completed_at and work.completed_at <= as_of_date:
        return "done"
    return "planned"


def get_payment_effective_amount(payment: Payment, as_of_date: date) -> Decimal:
    if payment.status == "queued":
        return ZERO

    if payment.status == "paid":
        if payment.paid_at and payment.paid_at <= as_of_date:
            return payment.amount
        return ZERO

    if payment.status == "refunded":
        if not payment.paid_at or payment.paid_at > as_of_date:
            return ZERO
        if payment.refunded_at and payment.refunded_at <= as_of_date:
            return ZERO
        return payment.amount

    return ZERO


def calculate_report(
    contracts: Dict[str, Contract],
    works: List[Work],
    payments: List[Payment],
    as_of_date: date,
    contract_id_filter: Optional[str] = None,
) -> FinancialReport:
    if contract_id_filter:
        if contract_id_filter not in contracts:
            raise ValueError(f"Договор с номером '{contract_id_filter}' не найден в данных.")
        target_contracts = {contract_id_filter: contracts[contract_id_filter]}
    else:
        target_contracts = contracts

    works_by_contract: Dict[str, List[Work]] = {cid: [] for cid in target_contracts}
    for w in works:
        if w.contract_id in target_contracts:
            works_by_contract[w.contract_id].append(w)

    payments_by_contract: Dict[str, List[Payment]] = {cid: [] for cid in target_contracts}
    for p in payments:
        if p.contract_id in target_contracts:
            payments_by_contract[p.contract_id].append(p)

    all_work_reports: List[WorkReportItem] = []
    all_contract_reports: List[ContractReportItem] = []

    for contract_id, contract in sorted(target_contracts.items()):
        c_works = works_by_contract.get(contract_id, [])
        c_payments = payments_by_contract.get(contract_id, [])

        # 1. Сбор действующих платежей на дату
        direct_payments: Dict[str, Decimal] = {}
        unassigned_pool = ZERO
        contract_total_paid = ZERO

        for p in c_payments:
            eff_amount = get_payment_effective_amount(p, as_of_date)
            if eff_amount <= ZERO:
                continue

            contract_total_paid += eff_amount
            if p.work_id:
                direct_payments[p.work_id] = direct_payments.get(p.work_id, ZERO) + eff_amount
            else:
                unassigned_pool += eff_amount

        # 2. Обработка работ на дату
        work_items_map: Dict[str, WorkReportItem] = {}
        done_works: List[Work] = []
        planned_works: List[Work] = []

        total_works_price_active = ZERO
        total_works_price_all = ZERO
        contract_disputed_amount = ZERO

        for w in c_works:
            status_on_date = determine_work_status_on_date(w, as_of_date)
            total_works_price_all += w.price
            paid_direct = direct_payments.get(w.work_id, ZERO)

            if status_on_date == "cancelled":
                eff_price = ZERO
                is_disputed = paid_direct > ZERO
                if is_disputed:
                    contract_disputed_amount += paid_direct
                # Отменённая работа не требует доплат
                remaining = ZERO
            else:
                eff_price = w.price
                total_works_price_active += eff_price
                is_disputed = False
                remaining = max(ZERO, eff_price - paid_direct)

            item = WorkReportItem(
                work_id=w.work_id,
                contract_id=w.contract_id,
                title=w.title,
                status_on_date=status_on_date,
                original_price=w.price,
                effective_price=eff_price,
                paid_direct=paid_direct,
                paid_fifo=ZERO,
                paid_total=paid_direct,
                remaining=remaining,
                is_disputed=is_disputed,
            )
            work_items_map[w.work_id] = item

            if status_on_date == "done":
                done_works.append(w)
            elif status_on_date == "planned":
                planned_works.append(w)

        # 3. FIFO распределение общего аванса
        # Выполненные сортируются по дате приёмки, при равенстве - по work_id
        done_works_sorted = sorted(
            done_works,
            key=lambda item: (item.completed_at or date.min, item.work_id),
        )
        # Запланированные - по work_id
        planned_works_sorted = sorted(planned_works, key=lambda item: item.work_id)

        fifo_queue = done_works_sorted + planned_works_sorted

        remaining_pool = unassigned_pool
        for w in fifo_queue:
            item = work_items_map[w.work_id]
            needed = item.effective_price - item.paid_direct
            if needed > ZERO and remaining_pool > ZERO:
                allocated = min(needed, remaining_pool)
                item.paid_fifo = allocated
                item.paid_total = item.paid_direct + allocated
                item.remaining = max(ZERO, item.effective_price - item.paid_total)
                remaining_pool -= allocated

        for w in c_works:
            all_work_reports.append(work_items_map[w.work_id])

        # Суммы по договору
        remaining_to_pay = sum((work_items_map[w.work_id].remaining for w in c_works), ZERO)
        # Бюджетное расхождение: сумма договора минус сумма действующих работ
        budget_discrepancy = contract.amount - total_works_price_active

        contract_report = ContractReportItem(
            contract_id=contract.contract_id,
            contractor=contract.contractor,
            contract_amount=contract.amount,
            works_amount_active=total_works_price_active,
            works_amount_total=total_works_price_all,
            total_paid=contract_total_paid,
            remaining_to_pay=remaining_to_pay,
            unallocated_advance=remaining_pool,
            budget_discrepancy=budget_discrepancy,
            disputed_amount=contract_disputed_amount,
        )
        all_contract_reports.append(contract_report)

    grand_contracts = sum((c.contract_amount for c in all_contract_reports), ZERO)
    grand_works = sum((c.works_amount_active for c in all_contract_reports), ZERO)
    grand_paid = sum((c.total_paid for c in all_contract_reports), ZERO)
    grand_remaining = sum((c.remaining_to_pay for c in all_contract_reports), ZERO)
    grand_budget_discrepancy = sum((c.budget_discrepancy for c in all_contract_reports), ZERO)
    grand_disputed = sum((c.disputed_amount for c in all_contract_reports), ZERO)

    return FinancialReport(
        as_of_date=as_of_date,
        works_report=all_work_reports,
        contracts_report=all_contract_reports,
        grand_total_contracts=grand_contracts,
        grand_total_works=grand_works,
        grand_total_paid=grand_paid,
        grand_total_remaining=grand_remaining,
        grand_budget_discrepancy=grand_budget_discrepancy,
        grand_disputed_amount=grand_disputed,
    )
