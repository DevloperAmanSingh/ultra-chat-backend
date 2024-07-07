from flask import Blueprint, request, jsonify
from pymongo import MongoClient
import requests
import logging
import os

crud_blueprint = Blueprint('crud', __name__)
logging.basicConfig(level=logging.DEBUG)
mongo_uri = os.getenv('MONGO_URI')
mongo_client = MongoClient(mongo_uri)
db = mongo_client['discord_oauth']
users_collection = db['users']

# Utility function to get the user from the token

def get_token_from_user_id(id):
    logging.debug(f"Searching for user with ID: {id}")
    user = users_collection.find_one({'id': id})
    if not user:
        logging.warning(f"User with ID {id} not found in database")
        return None
    
    tokenkwa = user.get('token')
    token = tokenkwa.get('access_token')
    logging.warning(token)
    if not token:
        logging.warning(f"No token found for user with ID {id}")
        return None
    
    logging.debug(f"Token found for user with ID {id}")
    headers = {'Authorization': f'Bearer {token}'}
    logging.debug(f"Headers: {headers}")
    
    response = requests.get('https://discord.com/api/users/@me', headers=headers)
    logging.debug(f"Response: {response.json()}")
    return response.json()



# Middleware to check authentication
def authenticate(func):
    def wrapper(*args, **kwargs):
        user_id = request.headers.get('ID')  # Assuming user_id is passed in headers
        logging.debug(f"Headers: {request.headers}")
        if not user_id:
            logging.warning("User ID not found in headers")
            return jsonify({'error': 'Unauthorized'}), 401
        
        logging.debug(f"User ID in headers: {user_id}")
        user_info = get_token_from_user_id(user_id)  # Implement this function to retrieve token from user_id
        
        if not user_info:
            logging.warning("Failed to retrieve user info from token")
            return jsonify({'error': 'Unauthorized'}), 401
        
        logging.info(f"Authenticated User: {user_info['id']}")
        
        if user_info['id'] != user_id:
            logging.warning("Mismatch between user_id and user_info['id']")
            return jsonify({'error': 'Unauthorized'}), 401
        
        user = users_collection.find_one({'id': user_info['id']})
        if not user:
            logging.warning("User not found in database")
            return jsonify({'error': 'User not found'}), 404
        
        request.user = user
        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper

@crud_blueprint.route('/summarizer', methods=['POST'])
@authenticate
def create_summary():
    data = request.json
    logging.debug(f"Data: {data}")
    user_id = request.headers.get('ID')#  takes in discord id as user_id
    content = data.get('content')      # Get content from request parameters
    logging.debug(f"User ID: {user_id}")
    logging.debug(f"Content: {content}")

    if not user_id or not content:
        return jsonify({'error': 'Missing user_id or content in request parameters'}), 400

    summary = {
        'id': str(len(request.user.get('summaries', [])) + 1),
        'content': content
    }
    
    users_collection.update_one(
        {'id': user_id},
        {'$push': {'summaries': summary}}
    )

    return jsonify({'message': 'Summary created successfully'}), 201


@crud_blueprint.route('/summarizer', methods=['GET'])
@authenticate
def get_summaries():
    user_id = request.headers.get('ID')
    logging.debug(f"user_id: {user_id}")

    user = users_collection.find_one({'id': user_id})
    if user:
        summaries = user.get('summaries', [])
        return jsonify(summaries), 200

    return jsonify({'error': 'User not found or no summaries available'}), 404


@crud_blueprint.route('/update-summary', methods=['PUT'])
@authenticate
def update_summary():
    data = request.json
    summary_id = data.get('summary_id')
    content = data.get('content')
    user_id = request.headers.get('ID')  # Assuming 'user_id' is passed in headers

    if not summary_id or not content or not user_id:
        return jsonify({'error': 'summary_id, content, and user_id are required'}), 400

    result = users_collection.update_one(
        {'id': user_id, 'summaries.id': str(summary_id)},
        {'$set': {'summaries.$.content': content}}
    )

    if result.modified_count > 0:
        return jsonify({'message': 'Summary updated successfully'}), 200

    return jsonify({'error': 'Summary not found or not authorized'}), 404

@crud_blueprint.route('/delete-summary', methods=['DELETE'])
@authenticate
def delete_summary():
    data = request.json
    summary_id = data.get('summary_id')
    user_id = request.headers.get('ID')  # Assuming 'user_id' is passed in headers

    if not summary_id or not user_id:
        return jsonify({'error': 'summary_id and user_id are required'}), 400

    result = users_collection.update_one(
        {'id': user_id},
        {'$pull': {'summaries': {'id': str(summary_id)}}}
    )

    if result.modified_count > 0:
        return jsonify({'message': 'Summary deleted successfully'}), 200

    return jsonify({'error': 'Summary not found or not authorized'}), 404



def get_user_from_token(token):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get('https://discord.com/api/users/@me', headers=headers)
    if response.status_code == 200:
        return response.json()
    return None

def authenticate(token, user_id):
    user_info = get_user_from_token(token)
    if user_info and user_info['id'] == user_id:
        return user_info
    return None

@crud_blueprint.route('/is_authenticated', methods=['GET'])
def is_authenticated():
    user_id = request.headers.get('ID')
    logging.debug(f"User ID: {user_id}")
    user = users_collection.find_one({'id': user_id})
    tokenkwa = user.get('token')
    token = tokenkwa.get('access_token')
    logging.warning(token)
    if not token or not user_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_info = authenticate(token, user_id)
    if not user_info:
        return jsonify({'error': 'Unauthorized'}), 401
    
    return jsonify({'message': 'User is authenticated', 'user': user_info}), 200