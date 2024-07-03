import logging
from flask import Blueprint, request, redirect, url_for, session, jsonify
import requests
from pymongo import MongoClient
from uuid import uuid4
import os

auth_blueprint = Blueprint('auth', __name__)

client_id = os.getenv('CLIENT_ID')
client_secret = os.getenv('CLIENT_SECRET')
redirect_uri = os.getenv('REDIRECT_URI')
scope = os.getenv('SCOPE')

# MongoDB setup
mongo_uri = os.getenv('MONGO_URI')
mongo_client = MongoClient(mongo_uri)
db = mongo_client['discord_oauth']
users_collection = db['users']

@auth_blueprint.route('/login')
def login():
    return redirect(f"https://discord.com/api/oauth2/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope={scope}")

@auth_blueprint.route('/callback')
def callback():
    code = request.args.get('code')
    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post('https://discord.com/api/oauth2/token', data=data, headers=headers)
    response.raise_for_status()
    tokens = response.json()
    session['token'] = tokens['access_token']
    
    headers = {'Authorization': f'Bearer {tokens["access_token"]}'}
    print("Headers: ", tokens["access_token"])
    user_info = requests.get('https://discord.com/api/users/@me', headers=headers).json()
    
    user_id = user_info['id']
    user_uuid = str(uuid4())

    # Check if user already exists
    existing_user = users_collection.find_one({'id': user_id})
    
    if existing_user:
        users_collection.update_one(
            {'id': user_id},
            {'$set': {
                'token': tokens,
                'username': user_info['username'],
                'discriminator': user_info['discriminator'],
            }}
        )
    else:
        users_collection.insert_one({
            'id': user_id,
            'uuid': user_uuid,
            'token': tokens,
            'username': user_info['username'],
            'discriminator': user_info['discriminator'],
        })
    
    return redirect(url_for('auth.profile'))


@auth_blueprint.route('/profile')
def profile():
    token = session.get('token')
        # print("Token: ", token)
    logging.debug(f"Token: {token}")
    if not token:
        return redirect(url_for('auth.login'))
    user_info = authenticate(token)
    if not user_info:
        return redirect(url_for('auth.login'))
    return jsonify(user_info)


def authenticate(token):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get('https://discord.com/api/users/@me', headers=headers)
    if response.status_code == 200:
        return response.json()
    return None