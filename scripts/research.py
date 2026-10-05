import asyncio

from scripts.generate_research_report import main as generate_reports_main


def main() -> None:
    asyncio.run(generate_reports_main())


if __name__ == "__main__":
    main()
