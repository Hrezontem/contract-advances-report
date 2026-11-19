import unittest
from datetime import date
from decimal import Decimal

from parser import Contract, Work, Payment
from calculator import (
    calculate_report,
    determine_work_status_on_date,
    get_payment_effective_amount,
    ZERO,
)


class TestCalculator(unittest.TestCase):
    def setUp(self):
        self.contract = Contract(
            contract_id="C-1",
            contractor="Тест Подрядчик",
            amount=Decimal("1000.00"),
            signed_at=date(2026, 1, 1),
        )

    def test_payment_status_filtering(self):
        # Queued payment
        p_queued = Payment("P1", "C-1", None, "", Decimal("100.00"), "queued", date(2026, 1, 1), None, None)
        self.assertEqual(get_payment_effective_amount(p_queued, date(2026, 1, 10)), ZERO)

        # Paid after target date
        p_future = Payment("P2", "C-1", None, "", Decimal("100.00"), "paid", date(2026, 1, 1), date(2026, 1, 15), None)
        self.assertEqual(get_payment_effective_amount(p_future, date(2026, 1, 10)), ZERO)

        # Paid before target date
        p_valid = Payment("P3", "C-1", None, "", Decimal("100.00"), "paid", date(2026, 1, 1), date(2026, 1, 5), None)
        self.assertEqual(get_payment_effective_amount(p_valid, date(2026, 1, 10)), Decimal("100.00"))

        # Refunded before target date -> 0
        p_ref_past = Payment("P4", "C-1", None, "", Decimal("100.00"), "refunded", date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 5))
        self.assertEqual(get_payment_effective_amount(p_ref_past, date(2026, 1, 10)), ZERO)

        # Refunded after target date -> money was paid and not yet returned on target date
        p_ref_future = Payment("P5", "C-1", None, "", Decimal("100.00"), "refunded", date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 15))
        self.assertEqual(get_payment_effective_amount(p_ref_future, date(2026, 1, 10)), Decimal("100.00"))

    def test_work_status_on_date(self):
        w = Work("W1", "C-1", "Test", Decimal("100.00"), "done", date(2026, 1, 10), None)
        # On 2026-01-05 it was planned
        self.assertEqual(determine_work_status_on_date(w, date(2026, 1, 5)), "planned")
        # On 2026-01-10 it is done
        self.assertEqual(determine_work_status_on_date(w, date(2026, 1, 10)), "done")

        # Cancelled
        w_canc = Work("W2", "C-1", "Test2", Decimal("100.00"), "cancelled", None, date(2026, 1, 8))
        self.assertEqual(determine_work_status_on_date(w_canc, date(2026, 1, 5)), "planned")
        self.assertEqual(determine_work_status_on_date(w_canc, date(2026, 1, 8)), "cancelled")

    def test_fifo_distribution_order_and_tie_breaking(self):
        # 3 works: W2 and W1 done on SAME DATE (2026-01-02), W3 planned
        w1 = Work("W1", "C-1", "Work 1", Decimal("100.00"), "done", date(2026, 1, 2), None)
        w2 = Work("W2", "C-1", "Work 2", Decimal("100.00"), "done", date(2026, 1, 2), None)
        w3 = Work("W3", "C-1", "Work 3", Decimal("100.00"), "planned", None, None)

        p = Payment("P1", "C-1", None, "Advance", Decimal("150.00"), "paid", date(2026, 1, 1), date(2026, 1, 1), None)

        report = calculate_report({"C-1": self.contract}, [w1, w2, w3], [p], date(2026, 1, 10))

        items = {item.work_id: item for item in report.works_report}
        # W1 comes first lexicographically among identical completed_at dates -> gets 100.00
        self.assertEqual(items["W1"].paid_fifo, Decimal("100.00"))
        self.assertEqual(items["W1"].remaining, Decimal("0.00"))

        # W2 gets remaining 50.00
        self.assertEqual(items["W2"].paid_fifo, Decimal("50.00"))
        self.assertEqual(items["W2"].remaining, Decimal("50.00"))

        # W3 gets 0.00
        self.assertEqual(items["W3"].paid_fifo, Decimal("0.00"))
        self.assertEqual(items["W3"].remaining, Decimal("100.00"))

    def test_direct_payment_with_fifo(self):
        w1 = Work("W1", "C-1", "Work 1", Decimal("100.00"), "done", date(2026, 1, 1), None)
        w2 = Work("W2", "C-1", "Work 2", Decimal("100.00"), "planned", None, None)

        p_direct = Payment("P1", "C-1", "W1", "Materials", Decimal("20.00"), "paid", date(2026, 1, 1), date(2026, 1, 1), None)
        p_advance = Payment("P2", "C-1", None, "Advance", Decimal("150.00"), "paid", date(2026, 1, 1), date(2026, 1, 1), None)

        report = calculate_report({"C-1": self.contract}, [w1, w2], [p_direct, p_advance], date(2026, 1, 10))
        items = {item.work_id: item for item in report.works_report}

        self.assertEqual(items["W1"].paid_direct, Decimal("20.00"))
        self.assertEqual(items["W1"].paid_fifo, Decimal("80.00"))
        self.assertEqual(items["W1"].paid_total, Decimal("100.00"))
        self.assertEqual(items["W1"].remaining, Decimal("0.00"))

        self.assertEqual(items["W2"].paid_fifo, Decimal("70.00"))
        self.assertEqual(items["W2"].remaining, Decimal("30.00"))

    def test_cancelled_work_frees_advance(self):
        w1 = Work("W1", "C-1", "Work 1", Decimal("100.00"), "cancelled", None, date(2026, 1, 5))
        w2 = Work("W2", "C-1", "Work 2", Decimal("100.00"), "planned", None, None)
        p = Payment("P1", "C-1", None, "Advance", Decimal("100.00"), "paid", date(2026, 1, 1), date(2026, 1, 1), None)

        report = calculate_report({"C-1": self.contract}, [w1, w2], [p], date(2026, 1, 10))
        items = {item.work_id: item for item in report.works_report}

        self.assertEqual(items["W1"].effective_price, Decimal("0.00"))
        self.assertEqual(items["W1"].paid_total, Decimal("0.00"))

        self.assertEqual(items["W2"].paid_fifo, Decimal("100.00"))
        self.assertEqual(items["W2"].remaining, Decimal("0.00"))

    def test_cancelled_work_with_direct_payment_flagged_as_disputed(self):
        # Cancelled work with actual direct payment
        w_canc = Work("W1", "C-1", "Cancelled Work", Decimal("100.00"), "cancelled", None, date(2026, 1, 5))
        w_ok = Work("W2", "C-1", "Active Work", Decimal("100.00"), "planned", None, None)

        p_direct_cancelled = Payment("P1", "C-1", "W1", "Prep", Decimal("30.00"), "paid", date(2026, 1, 2), date(2026, 1, 2), None)
        p_advance = Payment("P2", "C-1", None, "Advance", Decimal("50.00"), "paid", date(2026, 1, 3), date(2026, 1, 3), None)

        report = calculate_report({"C-1": self.contract}, [w_canc, w_ok], [p_direct_cancelled, p_advance], date(2026, 1, 10))
        items = {item.work_id: item for item in report.works_report}

        # W1 has direct payment 30.00, remaining 0.00, flagged as is_disputed
        self.assertTrue(items["W1"].is_disputed)
        self.assertEqual(items["W1"].paid_direct, Decimal("30.00"))
        self.assertEqual(items["W1"].remaining, Decimal("0.00"))

        # W2 gets advance 50.00
        self.assertEqual(items["W2"].paid_fifo, Decimal("50.00"))
        self.assertEqual(items["W2"].remaining, Decimal("50.00"))

        # Contract summary reflects disputed amount
        c_item = report.contracts_report[0]
        self.assertEqual(c_item.disputed_amount, Decimal("30.00"))

    def test_unallocated_advance_and_budget_discrepancy(self):
        w1 = Work("W1", "C-1", "Work 1", Decimal("50.00"), "done", date(2026, 1, 1), None)
        p = Payment("P1", "C-1", None, "Big Advance", Decimal("200.00"), "paid", date(2026, 1, 1), date(2026, 1, 1), None)

        # Contract amount 1000.00, work price 50.00 -> budget discrepancy 950.00
        report = calculate_report({"C-1": self.contract}, [w1], [p], date(2026, 1, 10))
        c_item = report.contracts_report[0]

        self.assertEqual(c_item.total_paid, Decimal("200.00"))
        self.assertEqual(c_item.remaining_to_pay, Decimal("0.00"))
        self.assertEqual(c_item.unallocated_advance, Decimal("150.00"))
        self.assertEqual(c_item.budget_discrepancy, Decimal("950.00"))


    def test_contract_filter(self):
        contract_2 = Contract("C-2", "Подрядчик 2", Decimal("500.00"), date(2026, 1, 1))
        w1 = Work("W1", "C-1", "Work 1", Decimal("50.00"), "done", date(2026, 1, 1), None)
        w2 = Work("W2", "C-2", "Work 2", Decimal("60.00"), "done", date(2026, 1, 1), None)

        report = calculate_report({"C-1": self.contract, "C-2": contract_2}, [w1, w2], [], date(2026, 1, 10), contract_id_filter="C-1")
        self.assertEqual(len(report.contracts_report), 1)
        self.assertEqual(report.contracts_report[0].contract_id, "C-1")
        self.assertEqual(len(report.works_report), 1)
        self.assertEqual(report.works_report[0].work_id, "W1")


if __name__ == "__main__":
    unittest.main()
