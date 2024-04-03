import boto3
from flask import Blueprint, request, jsonify


bp = Blueprint('users', __name__)
boto3.setup_default_session(profile_name="dev")

"""
Adds a user to database.
Input:  
        {
            'username': username
            'userType': userType
        }
Output:
        {
            'message/error': string
        }
        HTTP Response Code   
"""
@bp.route('/adduser', methods=['POST'])
def add_user():
    data = request.json
    username = data.get('username')
    userType = data.get('userType')
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('test-userbase')
    
    try:
        table.put_item(
            Item={
                'username': username,
                'userType': userType,
                'uploads': [],
                'accessUploads': []
            }
        )
        return jsonify({'message': 'User added successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

# Input: Username
# Output: List of files a user has uploaded
@bp.route('/getUploads/<username>', methods=['GET'])
def getUploads(username):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('test-userbase')

    try:
        response = table.get_item(Key={'username': username}, ProjectionExpression='uploads')
        if 'Item' in response:
            attribute_value = response['Item'].get('uploads', {})
            return jsonify(attribute_value), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500 
    
# Separate route for user type, uploaded sets, sets that can be accessed
# update user table with info when a dataset is uploaded
    
# Input: Username
# Output: List of name of datasets user has access to
@bp.route('/getDownloadedSets/<username>', methods=['GET'])
def getDownloadedSets(username):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('test-userbase')

    try:
        response = table.get_item(Key={'username': username}, ProjectionExpression='accessUploads')
        if 'Item' in response:
            attribute_value = response['Item'].get('accessUploads', {})
            return jsonify({'uploads': attribute_value}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500 
    


# Input: username
# Output: String of user type (Validator or User)
@bp.route('/getUserType/<username>', methods=['GET'])
def getUserType(username):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('test-userbase')

    try:
        response = table.get_item(Key={'username': username}, ProjectionExpression='userType')
        if 'Item' in response:
            attribute_value = response['Item'].get('userType', {})
            return jsonify({'uploads': attribute_value}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500 
    

@bp.route('/deleteSet/<username>/<filename>', methods=['POST'])
def deleteSet(username, filename):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('test-userbase')

    try:
        response = table.get_item(Key={'username': username}, ProjectionExpression='uploads')
        db_folder_name = username+"-"+filename
        if 'Item' in response:
            upload_list = response['Item'].get('uploads', {})
            upload_list.remove(db_folder_name)
            table.update_item(Key={'username': username}, UpdateExpression="SET uploads = :val", ExpressionAttributeValues={':val': [upload_list],})
            return jsonify({'message: successfully updated'}),200
    except Exception as e:
            return jsonify({'error': str(e)}), 500
    

@bp.route('/fetchDescription/<filename>')
def fetchDescription(filename):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('test-uploadbase')

    try:
        response = table.get_item(Key={'uploadId': filename}, ProjectionExpression='description')
        if 'Item' in response:
            description = response['Item'].get('description', {})
            return jsonify({'description': description}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

@bp.route('/updateDescription/<filename>/<description>')
def updateDescription(filename, description):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('test-uploadbase')

    try:
        table.update_item(Key={'uploadId': filename}, UpdateExpression="SET description = :val", ExpressionAttributeValues={':val': [description],})
        return jsonify({'message: successfully updated'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
