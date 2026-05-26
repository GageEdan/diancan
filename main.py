import os

from flask import Flask

from config import SECRET_KEY, DATA_DIR
from routes.pages import pages_bp
from routes.api import api_bp
from database import init_db

app = Flask(__name__)
app.secret_key = SECRET_KEY

app.register_blueprint(pages_bp)
app.register_blueprint(api_bp)

if __name__ == '__main__':
    os.makedirs(DATA_DIR, exist_ok=True)
    init_db()
    print('>>> 点餐系统启动中... http://localhost:5000')
    app.run(debug=True, host='0.0.0.0', port=5000)
