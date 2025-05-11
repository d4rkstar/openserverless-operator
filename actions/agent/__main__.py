# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#

import json
import logging

import nuvolaris.config as cfg
import nuvolaris.couchdb_util as cu

USER_META_DBN = "users_metadata"


def fetch_user_data(db, token: str):
    logging.info(f"searching for api key token: {token}")
    try:
        selector = {"selector": {
            "env": {
                "$elemMatch": {
                    "key": "AUTH",
                    "value": token
                }
            }
        }}
        response = db.find_doc(USER_META_DBN, json.dumps(selector))

        if response['docs']:
            docs = list(response['docs'])
            if len(docs) > 0:
                return docs[0]

        logging.warning(f"Nuvolaris metadata for api key {token} not found!")
        return None
    except Exception as e:
        logging.error(f"failed to query Nuvolaris metadata for api key {token}. Reason: {e}")
        return None


def build_response():
    return {
        "statusCode": 200,
        "body": {}
    }


def build_error(message: str, status_code: int = 400):
    return {
        "statusCode": status_code,
        "body": message
    }


def main(args):
    cfg.clean()
    cfg.put("couchdb.host", args['couchdb_host'])
    cfg.put("couchdb.admin.user", args['couchdb_user'])
    cfg.put("couchdb.admin.password", args['couchdb_password'])

    # Access the headers
    headers = args.get('__ow_headers', {})
    # Normalize header keys to lowercase
    normalized_headers = {key.lower(): value for key, value in headers.items()}

    # Example: Get a specific header, e.g., "Authorization"
    auth_header = normalized_headers.get('authorization', '')
    if auth_header is '':
        return build_error("missing authorization header", 401)

    db = cu.CouchDB()
    # retrieve user data for the login
    user_data = fetch_user_data(db, auth_header)

    if user_data:
        return build_response()
    else:
        return build_error(f"Invalid token", 401)
