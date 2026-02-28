import asyncio

from leetshell.app import LeetCodeApp


def main():
    app = LeetCodeApp()
    asyncio.run(app.run())


if __name__ == "__main__":
    main()
