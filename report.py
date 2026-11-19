import csv
from decimal import Decimal
from pathlib import Path
from typing import Optional
from calculator import FinancialReport


def format_money(val: Decimal) -> str:
    return f"{val:,.2f}".replace(",", " ").replace(".", ",")


def render_console_table(report: FinancialReport) -> str:
    lines = []
    date_str = report.as_of_date.strftime("%d.%m.%Y")
    lines.append("=" * 115)
    lines.append(f"ФИНАНСОВЫЙ ОТЧЁТ ПО РАБОТАМ И ДОГОВОРАМ НА ДАТУ {date_str}")
    lines.append("=" * 115)
    lines.append("")

    lines.append("1. ОТЧЁТ ПО РАБОТАМ:")
    lines.append("-" * 115)
    header = (
        f"{'Договор':<8} | {'Работа':<7} | {'Статус':<9} | {'Цена (руб)':>13} | "
        f"{'Прямо (руб)':>12} | {'FIFO (руб)':>12} | {'Выплачено':>13} | {'Остаток раб.':>13} | {'Название'}"
    )
    lines.append(header)
    lines.append("-" * 115)

    has_disputed = False
    for w in report.works_report:
        title_suffix = ""
        if w.is_disputed:
            title_suffix = " [!] СПОРНАЯ СУММА (прямой платёж по отменённой работе)"
            has_disputed = True
        line = (
            f"{w.contract_id:<8} | {w.work_id:<7} | {w.status_on_date:<9} | "
            f"{format_money(w.effective_price):>13} | {format_money(w.paid_direct):>12} | "
            f"{format_money(w.paid_fifo):>12} | {format_money(w.paid_total):>13} | "
            f"{format_money(w.remaining):>13} | {w.title}{title_suffix}"
        )
        lines.append(line)

    lines.append("-" * 115)
    total_works_price = sum((w.effective_price for w in report.works_report), Decimal("0.00"))
    total_works_direct = sum((w.paid_direct for w in report.works_report), Decimal("0.00"))
    total_works_fifo = sum((w.paid_fifo for w in report.works_report), Decimal("0.00"))
    total_works_paid = sum((w.paid_total for w in report.works_report), Decimal("0.00"))
    total_works_rem = sum((w.remaining for w in report.works_report), Decimal("0.00"))

    total_line = (
        f"{'ИТОГО':<8} | {'':<7} | {'':<9} | "
        f"{format_money(total_works_price):>13} | {format_money(total_works_direct):>12} | "
        f"{format_money(total_works_fifo):>12} | {format_money(total_works_paid):>13} | "
        f"{format_money(total_works_rem):>13} |"
    )
    lines.append(total_line)
    lines.append("-" * 115)
    lines.append("")

    lines.append("2. ИТОГИ ПО ДОГОВОРАМ:")
    lines.append("-" * 115)
    c_header = (
        f"{'Договор':<8} | {'Подрядчик':<20} | {'Сумма дог.':>13} | {'Сумма работ':>13} | "
        f"{'Выплачено':>12} | {'Остаток раб.':>13} | {'Нераспред.':>11} | {'Разн(Дог-Раб)':>13}"
    )
    lines.append(c_header)
    lines.append("-" * 115)

    for c in report.contracts_report:
        c_line = (
            f"{c.contract_id:<8} | {c.contractor[:20]:<20} | {format_money(c.contract_amount):>13} | "
            f"{format_money(c.works_amount_active):>13} | {format_money(c.total_paid):>12} | "
            f"{format_money(c.remaining_to_pay):>13} | {format_money(c.unallocated_advance):>11} | "
            f"{format_money(c.budget_discrepancy):>13}"
        )
        lines.append(c_line)

    lines.append("-" * 115)
    grand_unallocated = sum((c.unallocated_advance for c in report.contracts_report), Decimal("0.00"))

    grand_line = (
        f"{'ИТОГО':<8} | {'':<20} | {format_money(report.grand_total_contracts):>13} | "
        f"{format_money(report.grand_total_works):>13} | {format_money(report.grand_total_paid):>12} | "
        f"{format_money(report.grand_total_remaining):>13} | {format_money(grand_unallocated):>11} | "
        f"{format_money(report.grand_budget_discrepancy):>13}"
    )
    lines.append(grand_line)
    lines.append("=" * 115)
    lines.append("Примечание к сводке:")
    lines.append("- «Остаток раб.»: остаток к доплате по действующим работам.")
    lines.append("- «Разн(Дог-Раб)»: контрольное расхождение между суммой договора и суммой действующих работ.")
    lines.append("  (не является автоматическим долгом; возникает из-за отмен работ, резерва сметы или отсутствия ДС).")
    if report.grand_disputed_amount > Decimal("0.00"):
        lines.append(f"- [!] Обнаружены спорные прямые платежи по отменённым работам: {format_money(report.grand_disputed_amount)} руб.")
    lines.append("=" * 115)

    return "\n".join(lines)


def export_works_csv(report: FinancialReport, output_path: Path):
    with open(output_path, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            "Договор",
            "Работа",
            "Название",
            "Статус_на_дату",
            "Цена_руб",
            "Прямая_оплата_руб",
            "FIFO_аванс_руб",
            "Всего_выплачено_руб",
            "Остаток_по_работе_руб",
            "Спорная_сумма_флаг",
        ])
        for w in report.works_report:
            writer.writerow([
                w.contract_id,
                w.work_id,
                w.title,
                w.status_on_date,
                str(w.effective_price),
                str(w.paid_direct),
                str(w.paid_fifo),
                str(w.paid_total),
                str(w.remaining),
                "ДА" if w.is_disputed else "НЕТ",
            ])


def export_contracts_csv(report: FinancialReport, output_path: Path):
    with open(output_path, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            "Договор",
            "Подрядчик",
            "Сумма_договора_руб",
            "Сумма_активных_работ_руб",
            "Сумма_всех_работ_руб",
            "Выплачено_руб",
            "Остаток_по_работам_руб",
            "Нераспределенный_аванс_руб",
            "Разница_договора_и_работ_руб",
            "Спорные_прямые_платежи_руб",
        ])
        for c in report.contracts_report:
            writer.writerow([
                c.contract_id,
                c.contractor,
                str(c.contract_amount),
                str(c.works_amount_active),
                str(c.works_amount_total),
                str(c.total_paid),
                str(c.remaining_to_pay),
                str(c.unallocated_advance),
                str(c.budget_discrepancy),
                str(c.disputed_amount),
            ])
