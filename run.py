# run.py
import logging
from app import create_app

logging.basicConfig(level=logging.INFO)
logging.getLogger('werkzeug').setLevel(logging.DEBUG)
app = create_app()



if __name__ == '__main__':
    app.run(debug=True)