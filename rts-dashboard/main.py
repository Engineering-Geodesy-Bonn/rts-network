import logging
from web.app import app


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


def main():
    app.run(debug=True, host="0.0.0.0", port=8050)


if __name__ == "__main__":
    main()
