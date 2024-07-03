from flask import Flask
import os
from pymongo import MongoClient

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Database configuration
mongo_uri = os.getenv('MONGO_URI')
mongo_client = MongoClient(mongo_uri)
db = mongo_client['discord_oauth']
users_collection = db['users']

# Importing routes
from auth import auth_blueprint
from crud import crud_blueprint

app.register_blueprint(auth_blueprint)
app.register_blueprint(crud_blueprint)

if __name__ == '__main__':
    app.run(debug=True, port=5001, host='0.0.0.0')
