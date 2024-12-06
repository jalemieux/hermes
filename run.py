# run.py
import logging
from app import create_app

app = create_app()

logging.basicConfig(level=logging.INFO)

if __name__ == '__main__':
    app.run(debug=True)