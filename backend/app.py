import boto3
import datetime
import logging
import os
import shutil
from botocore.exceptions import ClientError
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from zipfile import ZipFile
from io import BytesIO

main_bucket = "bucket-for-testing-boto3"
zip_temp = "zip_temp"
download_temp = "Sanctum_Images"
datetime_format = "%d-%m-%Y-%H-%M-%S"
maxKeys = 100
isTruncated = False
nextContinuationToken = ""

app = Flask(__name__)
CORS(app)
boto3.setup_default_session(profile_name="dev")

# Test route on root path
# Input: None
# Output: List of existing buckets
@app.route('/', methods=['GET'])
def test_function():
    return jsonify(list_existing_buckets())

# Returns a list of the first `maxKeys` files in a bucket, organized in dictionaries containing 
#         the file name, location, type, size, and when it was last modified
# Input: None
# Output: List of files
@app.route('/display_files', methods=['GET'])
def display_files():
    client = boto3.client('s3')
    response = client.list_objects_v2(Bucket=main_bucket, MaxKeys=maxKeys)

    return display_helper(response)
    
# Returns the next `maxKeys` files in the bucket, organized as above
# Input: None
# Output: List of files
@app.route('/next_page', methods=['GET'])
def next_page():
    global nextContinuationToken
    global isTruncated

    if (not isTruncated):
        return jsonify({"error": "No files to show"}), 400
    
    client = boto3.client('s3')
    response = client.list_objects_v2(Bucket=main_bucket, MaxKeys=maxKeys, ContinuationToken=nextContinuationToken)
    
    return display_helper(response)

# Displays top level folders with corresponding metadata. Assumes username is appended to front
# Input: None
# Output: List of dictionaries with keyname and metadata. Ex: [{'Key': 'cancer-set', 'Metadata':{'Name':'Bill', 'Age': 14}}, {'Key': 'tumors', 'Metadata':{'Name':'Jack', 'Age': 49}}]
@app.route('/display_folders', methods=['GET'])
def display_all():
    top_level_folders = list()
    client = boto3.client('s3')
    paginator = client.get_paginator('list_objects')
    result = paginator.paginate(Bucket=main_bucket, Delimiter='/')
    try:
        for prefix in result.search('CommonPrefixes'):
            key = prefix.get('Prefix').split('-', 1)
            top_level_folders.append(key[1].strip())
    except Exception as e: 
        return jsonify({"error": f"{str(e)} - Either no prefixes found (empty bucket), or incorrect key schema (no username- appended to beginning of key)"})
    return top_level_folders

# Downloads an array of images from s3 bucket and sends them to frontend
# Input: files: Array of files to download
# Output: Zipped up directory containing downloaded files, 
#         Number of files that were not downloaded
@app.route('/download', methods=['POST'])
def download_files():
    data = request.get_json()
    
    if 'files' in data:
        try:
            files_not_found = download_files(data['files'], main_bucket)
            if os.path.exists(download_temp + ".zip"):
                send_file(download_temp + ".zip", as_attachment=True)
                return jsonify({"Files not found": files_not_found})
            else:
                return jsonify({"error": "requested file(s) not found"}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Incorrect input format"}), 400
    
# Uploads an array of files to the database, works with zip files and directories
# Input: 'files': Array of files, 'metadata': List of metadata for each file. Ex: [{"Name: Bob", "Age: 14"}, {"Name: Sally", "Age: 27"}]
# Output: Bool
@app.route('/upload', methods=['POST'])
def upload_files():
    if 'files' in request.files and 'user' in request.form:
        try:
            files = request.files.getlist('files')
            metadata_arr = request.form.get('metadata') # Assumes list of metadata for each file is given in a list. Ex: [{"Name: Bob", "Age: 14"}, {"Name: Sally", "Age: 27"}]
            # success = upload_files(files, metadata_arr, main_bucket)
            user = request.form['user']
            success = upload_files(files, user, main_bucket)
            return jsonify(success)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Incorrect input format"}), 400
    

# Updates metadata of object
# Input: Bucket, object key, and updated metadata
 # Output: Bool if success
@app.route('/metadata/<bucket>/<key>/<metadata>', methods=['POST'])
def update_metadata(bucket, key, metadata):
    boto3.setup_default_session(profile_name="dev")
    s3_client = boto3.client('s3')
    s3_client.copy_object(Key=key, Bucket=bucket,
               CopySource={"Bucket": bucket, "Key": key},
               Metadata=metadata,
               MetadataDirective="REPLACE")
    return True

## Functions

# Test method, displays an array of all existing buckets
def list_existing_buckets():
    s3_client = boto3.client('s3')
    response = s3_client.list_buckets()

    buckets = list()
    for bucket in response['Buckets']:
        buckets.append(bucket["Name"])
    return buckets

# # Accepts an array of files to upload to the 
# def upload_files(file_arr, metadata_arr, bucket):    
#     boto3.setup_default_session(profile_name="dev")
'''
# Accepts an array of files to upload to the s3 bucket
def upload_files(file_arr, user, bucket):    
    s3_client = boto3.client('s3')
    try:
        for metadata, file in zip(metadata_arr, file_arr):

            if file.filename.endswith(".zip"):
                unzip_files(file, user)
            else:
                s3_client.upload_fileobj(file, bucket, file.filename, ExtraArgs={'Metadata': metadata})
                s3_client.upload_fileobj(file, bucket, file.filename + "-" + user)
        if (os.path.exists(zip_temp)):
            upload_dir(zip_temp, bucket)
            shutil.rmtree(zip_temp)
    except ClientError as e:
        logging.error(e)
        return False
    return True
'''

# Accepts an array of files to upload to the s3 bucket, generates a folder automatically
def upload_files(file_arr, user, bucket):
    upload_temp = user + "-" + datetime.datetime.now().strftime(datetime_format)
    os.mkdir(upload_temp)
    try:
        for file in file_arr:
            if file.filename.endswith(".zip"):
                unzip_files(file, user, upload_temp)
            else:
                file.save(os.path.join(upload_temp, file.filename))
        if (os.path.exists(upload_temp)):
            upload_dir(upload_temp, bucket)
            shutil.rmtree(upload_temp)
    except Exception as e:
        logging.error(e)
        return False
    return True

# Handles uploads when a directory is passed
def upload_dir(directory, bucket):
    cmd = 'aws s3 cp ' + directory + ' s3://' + bucket + '/' + directory + ' --profile dev --recursive'
    print(cmd)
    os.system(cmd)

# Downloads a file into the temporary folder download_temp, then zips it up and deletes the original
def download_files(file_arr, bucket):
    s3 = boto3.client('s3')

    if os.path.exists(download_temp): # remove old download file if it exists
        shutil.rmtree(download_temp)
    os.mkdir(download_temp)

    if os.path.exists(download_temp + ".zip"): # remove old zip file if it exists
        os.remove(download_temp + ".zip")

    not_found = 0

    for file in file_arr:
        try:
            s3.download_file(bucket, file, os.path.join(download_temp, file))
        except ClientError as e:
            logging.error(e)
            not_found += 1
    if len([i for i in os.listdir(download_temp)]) > 0:
        shutil.make_archive(download_temp, "zip", download_temp)
    shutil.rmtree(download_temp)
    return not_found

# Internal function that handles zip files. Uses temporary folder zip_temp
def unzip_files(file_name, user, upload_temp):
    file_bytes = file_name.read()
    file_like_object = BytesIO(file_bytes)
    with ZipFile(file_like_object, 'r') as zip_ref:
        zip_ref.extractall(upload_temp)

# Searches bucket for all matches in search_param, returns a list of all matches
def bucket_search(search_param, bucket):
    client = boto3.client('s3')
    ret = list()
    paginator = client.get_paginator('list_objects_v2')

    page = paginator.paginate(Bucket=bucket)
    objects = page.search(f"Contents[?contains(Key, `{search_param}`)][]")
    for i in objects:
        ret.append(i)
    return ret

# Internal helper function, accepts a response from list_objects_v2 and returns a list of their characteristics
def display_helper(response):
    global isTruncated
    global nextContinuationToken

    isTruncated = response["IsTruncated"]
    if (isTruncated):
        nextContinuationToken = response["NextContinuationToken"]
    else:
        nextContinuationToken = ""
    files = list()
    if 'Contents' in response:
        for obj in response['Contents']:
            fileInfo = obj['Key'].split('/')
            if (fileInfo[0] != 'test_user-28-02-2024-16-29-16'):
                continue
            item = dict()
            try:
                item["Name"] = fileInfo[-1]
                item["Location"] =  '/'.join(fileInfo[:-1])
                item["Type"] = fileInfo[-1].split('.')[1]
            except IndexError:
                item["Name"] = obj['Key']
                item["Location"] = "/"
                item["Type"] = obj['Key'].split('.')[1]
            if 'LastModified' in obj:
                item["LastModified"] = obj["LastModified"]
            else:
                item["LastModified"] = None
            if 'Size' in obj:
                item["Size"] = obj['Size']
            else:
                item["Size"] = 0

            # for experimental file storage system
            try:
                extraInfo = fileInfo[0].split('-')
                item["UploadedBy"] = extraInfo[0]
                item["UploadedOn"] = datetime.datetime.strptime('-'.join(extraInfo[1:]), datetime_format)
            except Exception:
                print('failed')
            files.append(item)
        print(files)
        return files
    else:
        return jsonify({"error" : "Bucket is empty"}), 500

# display_files()
# next_page()
if __name__ == '__main__':
    app.run(debug=True)