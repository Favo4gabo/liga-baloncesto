"""Punto de entrada: python -m app.telegram_bot"""

from . import app
from .services.telegram_bot import run_polling


if __name__ == "__main__":
    with app.app_context():
        run_polling()
