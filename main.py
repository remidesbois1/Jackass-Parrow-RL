import sys


def main():
    # Select before importing App: headless must never load pygame/UI/assets.
    if sys.argv[1:2] == ["--headless"]:
        from src.headless.benchmark import main as headless_main

        headless_main(sys.argv[2:])
    else:
        from src.app import App

        app = App()
        app.start()
        app.execute()


if __name__ == "__main__":
    main()
