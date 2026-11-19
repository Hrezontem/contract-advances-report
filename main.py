import argparse
from datetime import datetime, date
from pathlib import Path
import sys
from typing import Optional, Tuple

from parser import load_data
from calculator import calculate_report
from report import render_console_table, export_works_csv, export_contracts_csv


def prompt_user(prompt_text: str, default: str) -> str:
    try:
        val = input(f"{prompt_text} [{default}]: ").strip()
        return val if val else default
    except (EOFError, KeyboardInterrupt):
        print("\nЗавершение работы.")
        sys.exit(0)


def interactive_wizard() -> Tuple[date, Path, Optional[str], bool, Path]:
    print("\n" + "=" * 65)
    print("      НАСТРОЙКА ПАРАМЕТРОВ ФИНАНСОВОГО ОТЧЁТА (CLI)")
    print("=" * 65)

    # 1. Папка с данными
    while True:
        data_dir_str = prompt_user("1. Папка с данными", "data")
        data_path = Path(data_dir_str)
        if data_path.exists() and (data_path / "contracts.csv").exists():
            break
        print(f"   [!] Ошибка: папка '{data_dir_str}' не найдена или не содержит contracts.csv. Повторите ввод.")

    # Предзагрузка договоров для отображения выбора
    try:
        contracts, _, _ = load_data(data_path)
        available_cids = sorted(contracts.keys())
    except Exception as e:
        print(f"   [!] Ошибка чтения данных: {e}")
        available_cids = []

    # 2. Дата отчёта
    while True:
        date_str = prompt_user("2. Дата отчёта (ГГГГ-ММ-ДД)", "2026-11-10")
        try:
            as_of_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            break
        except ValueError:
            print("   [!] Неверный формат даты. Требуется ГГГГ-ММ-ДД (например, 2026-11-10).")

    # 3. Фильтр договора
    contract_filter: Optional[str] = None
    if available_cids:
        cids_display = ", ".join(available_cids)
        while True:
            choice = prompt_user(f"3. Выберите договор (все / {cids_display})", "все")
            if choice.lower() in ("все", "all", "*", ""):
                contract_filter = None
                break
            elif choice.upper() in available_cids:
                contract_filter = choice.upper()
                break
            else:
                print(f"   [!] Неизвестный договор '{choice}'. Допустимо: все, {cids_display}")

    # 4. Экспорт CSV
    export_choice = prompt_user("4. Экспортировать отчёт в CSV? (y/n / д/н)", "n").lower()
    export_csv = export_choice in ("y", "yes", "д", "да", "1")

    # 5. Папка для экспорта
    out_dir = Path(".")
    if export_csv:
        out_dir_str = prompt_user("5. Папка для сохранения CSV файлов", ".")
        out_dir = Path(out_dir_str)

    print("-" * 65 + "\n")
    return as_of_date, data_path, contract_filter, export_csv, out_dir


def main():
    parser = argparse.ArgumentParser(
        description="Формирование отчёта по оплате договоров и работ на заданную дату."
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Запустить интерактивный пошаговый мастер настройки",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Путь к папке с файлами contracts.csv, works.csv, payments.csv (по умолчанию: data)",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Дата отчёта в формате ГГГГ-ММ-ДД (по умолчанию: 2026-11-10)",
    )
    parser.add_argument(
        "--contract",
        type=str,
        default=None,
        help="Номер договора для фильтрации (например, D-1). По умолчанию: все договоры.",
    )
    parser.add_argument(
        "--export-csv",
        action="store_true",
        help="Экспортировать отчёт в CSV файлы (report_works.csv, report_contracts.csv)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Папка для сохранения CSV файлов (по умолчанию текущая)",
    )

    args = parser.parse_args()

    # Если передан флаг -i или программа запущена без аргументов в интерактивном терминале
    is_interactive = args.interactive or (len(sys.argv) == 1 and sys.stdin.isatty())

    if is_interactive:
        as_of_date, data_path, contract_filter, export_csv, out_dir = interactive_wizard()
    else:
        date_str = args.date if args.date else "2026-11-10"
        try:
            as_of_date = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        except ValueError:
            print(f"Ошибка: Неверный формат даты '{date_str}'. Ожидается ГГГГ-ММ-ДД.", file=sys.stderr)
            sys.exit(1)
        data_path = Path(args.data_dir)
        contract_filter = args.contract.strip() if args.contract else None
        export_csv = args.export_csv
        out_dir = Path(args.output_dir)

    try:
        contracts, works, payments = load_data(data_path)
    except Exception as e:
        print(f"Ошибка загрузки данных: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        report = calculate_report(
            contracts,
            works,
            payments,
            as_of_date,
            contract_id_filter=contract_filter,
        )
    except Exception as e:
        print(f"Ошибка расчёта отчёта: {e}", file=sys.stderr)
        sys.exit(1)

    console_output = render_console_table(report)
    print(console_output)

    if export_csv:
        out_dir.mkdir(parents=True, exist_ok=True)
        suffix = f"_{contract_filter}" if contract_filter else ""
        works_csv = out_dir / f"report_works_{as_of_date}{suffix}.csv"
        contracts_csv = out_dir / f"report_contracts_{as_of_date}{suffix}.csv"
        export_works_csv(report, works_csv)
        export_contracts_csv(report, contracts_csv)
        print(f"\nОтчёты выгружены в CSV:\n  - {works_csv}\n  - {contracts_csv}")


if __name__ == "__main__":
    main()
