#!/usr/bin/env python

#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

##
# Whisk Admin command line interface
##

import argparse
import json
import os
import random
import re
from subprocess import Popen, PIPE, STDOUT
import string
import sys
import traceback
import uuid
import wskprop
if sys.version_info.major >= 3:
    from urllib.parse import quote_plus
else:
    from urllib import quote_plus
try:
    import argcomplete
except ImportError:
    argcomplete = False
from wskutil import request

DB_PROTOCOL = 'DB_PROTOCOL'
DB_HOST     = 'DB_HOST'
DB_PORT     = 'DB_PORT'
DB_USERNAME = 'DB_USERNAME'
DB_PASSWORD = 'DB_PASSWORD'

DB_WHISK_AUTHS   = 'DB_WHISK_AUTHS'
DB_WHISK_ACTIONS = 'DB_WHISK_ACTIONS'
DB_WHISK_ACTIVATIONS = 'DB_WHISK_ACTIVATIONS'

LOGS_DIR = 'WHISK_LOGS_DIR'

# SCRIPT_DIR is going to be traversing all links and point to tools/cli/wsk
CLI_DIR = os.path.dirname(os.path.realpath(sys.argv[0]))
# ROOT_DIR is the repository root
ROOT_DIR = os.path.join(os.path.join(CLI_DIR, os.pardir), os.pardir)

def main():
    requiredprops = [
        DB_PROTOCOL, DB_HOST, DB_PORT, DB_USERNAME, DB_PASSWORD,
        DB_WHISK_AUTHS, DB_WHISK_ACTIONS, DB_WHISK_ACTIVATIONS,
        LOGS_DIR ]
    whiskprops = wskprop.importPropsIfAvailable(wskprop.propfile(ROOT_DIR))
    (valid, props, deferredInfo) = wskprop.checkRequiredProperties(requiredprops, whiskprops)

    exitCode = 0 if valid else 2
    if valid:
        try:
            args = parseArgs()
            if (args.verbose):
                print(deferredInfo)
            exitCode = {
              'user' : userCmd,
              'db'   : dbCmd,
              'syslog' : syslogCmd,
              'limits': limitsCmd
            }[args.cmd](args, props)
        except Exception as e:
            print('Exception: ', e)
            print('Informative: ', deferredInfo)
            traceback.print_exc()
            exitCode = 1
    sys.exit(exitCode)

def str_to_bool(value):
    if value.lower() in ("yes", "true"):
        return True
    elif value.lower() in ("no", "false"):
        return False
    else:
        raise argparse.ArgumentTypeError("%s is not a valid boolean." % value)

def parseArgs():
    parser = argparse.ArgumentParser(description='OpenWhisk admin command line tool')
    parser.add_argument('-v', '--verbose', help='verbose output', action='store_true')
    subparsers = parser.add_subparsers(title='available commands', dest='cmd')
    subparsers.required = True

    propmenu = subparsers.add_parser('user', help='manage users')
    propmenu.add_argument('-w', '--view', help='the subject view to query', default='subjects.v2.0.0')
    subparser = propmenu.add_subparsers(title='available commands', dest='subcmd')
    subparser.required = True

    subcmd = subparser.add_parser('create', help='create a user and show authorization key')
    subcmd.add_argument('subject', help='the subject to create')
    subcmd.add_argument('-u', '--auth', help='the uuid:key to initialize the subject authorization key with')
    subcmd.add_argument('-ns', '--namespace', help='create key for given namespace instead (defaults to subject id')
    subcmd.add_argument('-r', '--revoke', help='revoke existing key and create a new one', action='store_true')
    subcmd.add_argument('-g', '--genonly', help='generate a uuid and key but do not store them in the database', action='store_true')
    subcmd.add_argument('-s', '--silent', help='do not should the new key on the console', action='store_true')

    subcmd = subparser.add_parser('delete', help='delete a user')
    subcmd.add_argument('subject', help='the subject to delete')
    subcmd.add_argument('-ns', '--namespace', help='delete key for given namespace only')

    subcmd = subparser.add_parser('get', help='get authorization key for user')
    subcmd.add_argument('subject', help='the subject to get key for')
    subcmd.add_argument('-ns', '--namespace', help='the namespace to get the key for, defaults to subject id')
    subcmd.add_argument('-a', '--all', help='list all namespaces and their keys', action='store_true')

    subcmd = subparser.add_parser('whois', help='identify user from an authorization key')
    subcmd.add_argument('authkey', help='the credentials to look up')

    subcmd = subparser.add_parser('block', help='block one or more users')
    subcmd.add_argument('subjects', nargs='+', help='one or more users to block')

    subcmd = subparser.add_parser('unblock', help='unblock one or more users')
    subcmd.add_argument('subjects', nargs='+', help='one or more users to unblock')

    subcmd = subparser.add_parser('list', help='list authorization keys associated with a namespace')
    subcmd.add_argument('namespace', help='the namespace to lookup')
    subcmd.add_argument('-p', '--pick', metavar='N', help='show no more than N identities', type=int, default=1)
    subcmd.add_argument('-a', '--all', help='show all identities', action='store_true')
    subcmd.add_argument('-k', '--key', help='show only the keys', action='store_true')

    propmenu = subparsers.add_parser('limits', help='manage namespace-specific limits')
    subparser = propmenu.add_subparsers(title='available commands', dest='subcmd')
    subparser.required = True

    subcmd = subparser.add_parser('set', help='set limits for a given namespace')
    subcmd.add_argument('namespace', help='the namespace to set limits for')
    subcmd.add_argument('--invocationsPerMinute', help='invocations per minute allowed', type=int)
    subcmd.add_argument('--firesPerMinute', help='trigger fires per minute allowed', type=int)
    subcmd.add_argument('--concurrentInvocations', help='concurrent invocations allowed for this namespace', type=int)
    subcmd.add_argument('--allowedKinds', help='list of runtime kinds allowed in this namespace', nargs='+', type=str)
    subcmd.add_argument('--storeActivations', help='enable or disable storing of activations to datastore for this namespace', default=None, type=str_to_bool)

    subcmd = subparser.add_parser('get', help='get limits for a given namespace (if none exist, system defaults apply)')
    subcmd.add_argument('namespace', help='the namespace to get limits for')

    subcmd = subparser.add_parser('delete', help='delete limits for a given namespace (system defaults apply)')
    subcmd.add_argument('namespace', help='the namespace to delete limits for')

    propmenu = subparsers.add_parser('db', help='work with dbs')
    subparser = propmenu.add_subparsers(title='available commands', dest='subcmd')
    subparser.required = True

    subcmd = subparser.add_parser('get', help='get contents of database')
    subcmd.add_argument('database', help='the database name')
    subcmd.add_argument('-w', '--view', help='the view in the database to query')
    subcmd.add_argument('--docs', help='include document contents', action='store_true')

    propmenu = subparsers.add_parser('syslog', help='work with system logs')
    subparser = propmenu.add_subparsers(title='available commands', dest='subcmd')
    subparser.required = True

    subcmd = subparser.add_parser('get', help='get logs')
    subcmd.add_argument('components', help='components, one or more of [controllerN, schedulerN, invokerN] where N is the instance', nargs='*', default=['controller0', 'scheduler0', 'invoker0'])
    subcmd.add_argument('-t', '--tid', help='retrieve logs for the transaction id')
    subcmd.add_argument('-g', '--grep', help='retrieve logs that match grep expression')

    if argcomplete:
        argcomplete.autocomplete(parser)
    return parser.parse_args()

def userCmd(args, props):
    if args.subcmd == 'create':
        return createUserCmd(args, props)
    elif args.subcmd == 'delete':
        return deleteUserCmd(args, props)
    elif args.subcmd == 'get':
        return getUserCmd(args, props)
    elif args.subcmd == 'whois':
        return whoisUserCmd(args, props)
    elif args.subcmd == 'list':
        return listUserCmd(args, props)
    elif args.subcmd == 'block':
        return blockUserCmd(args, props)
    elif args.subcmd == 'unblock':
        return unblockUserCmd(args, props)
    else:
        print('unknown command')
        return 2

def dbCmd(args, props):
    if args.subcmd == 'get':
        return getDbCmd(args, props)
    else:
        print('unknown command')
        return 2

def syslogCmd(args, props):
    if args.subcmd == 'get':
        return getLogsCmd(args, props)
    else:
        print('unknown command')
        return 2

def limitsCmd(args, props):
    if args.subcmd == 'set':
        return setLimitsCmd(args, props)
    elif args.subcmd == 'get':
        return getLimitsCmd(args, props)
    elif args.subcmd == 'delete':
        return deleteLimitsCmd(args, props)
    else:
        print('unknown command')
        return 2

def createUserCmd(args, props):
    subject = args.subject.strip()
    if len(subject) < 5:
        print('Subject name must be at least 5 characters')
        return 2

    if args.namespace and args.namespace.strip() == '':
        print('Namespace must not be empty')
        return 2
    else:
        desiredNamespace = subject if not args.namespace else args.namespace.strip()

    if args.auth:
        try:
            parts = args.auth.split(':')
            try:
                uid = str(uuid.UUID(parts[0], version = 4))
            except ValueError:
                print('authorization id is not a valid UUID')
                return 2

            key = parts[1]
            if len(key) < 64:
                print('authorization key must be at least 64 characters long')
                return 2
        except Exception as e:
            print('failed to determine authorization id and key: %s' % e)
            return 2
    else:
        uid = str(uuid.uuid4())
        key = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(64))

    if args.genonly:
        print('%s:%s' % (uid, key))
        return 0

    (doc, res) = getDocumentFromDb(props, args.subject, args.verbose)
    if doc is None:
        doc = {
            '_id': subject,
            'subject': subject,
            'namespaces': [
                {
                    'name': desiredNamespace,
                    'uuid': uid,
                    'key': key
                }
            ]
        }
    else:
        if not doc.get('blocked'):
            namespaces = [ns for ns in doc['namespaces'] if ns['name'] == desiredNamespace]
            if len(namespaces) == 0:
                doc['namespaces'].append({
                    'name': desiredNamespace,
                    'uuid': uid,
                    'key': key
                })
            elif args.revoke:
                if len(namespaces) == 1:
                    namespaces[0]['uuid'] = uid
                    namespaces[0]['key'] = key
                else:
                    print('Namespace is not unique')
                    return 1
            else:
                print('Namespace already exists')
                return 1
        else:
            print('The subject you want to edit is blocked')
            return 1

    res = insertIntoDatabase(props, doc, args.verbose)
    if res.status in [201, 202]:
        if not args.silent:
            print('%s:%s' % (uid, key))
    else:
        print('Failed to create subject (%s)' % res.read().strip())
        return 1

def getUserCmd(args, props):
    (doc, res) = getDocumentFromDb(props, args.subject, args.verbose)

    if doc is not None:
        if args.all is True:
            # tabulate name of each space and its key
            for ns in doc['namespaces']:
                print('%s\t%s:%s' % (ns['name'], ns['uuid'], ns['key']))
            return 0
        else:
          # if requesting key for specific namespace, report only that key;
          # use default namespace if no namespace provided
          namespaceName = args.namespace if args.namespace is not None else args.subject
          namespaces = [ns for ns in doc['namespaces'] if ns['name'] == namespaceName]
          if len(namespaces) == 1:
              ns = namespaces[0]
              print('%s:%s' % (ns['uuid'], ns['key']))
              return 0
          else:
              print('namespace "%s" not found for "%s"' % (namespaceName, args.subject))
              return 1
    else:
        print('Failed to get subject (%s)' % res.read().strip())
        return 1

def listUserCmd(args, props):
    (nslist, res) = getIdentitiesFromNamespace(args, props)

    if args.pick < 1:
        print('pick at least 1 identity to show')
        return 2

    if nslist is not None:
        nslist = nslist if args.all is True else nslist[:args.pick]
        if len(nslist) > 0:
            for p in nslist:
                print('%s:%s%s' % (p['uuid'], p['key'], "\t%s" % p['subject'] if not args.key else ""))
            return 0
        else:
            print('no identities found for namespace "%s"' % args.namespace)
            return 0
    else:
        print('Failed to get namespace key (%s)' % res.read().strip())
        return 1

def getDocumentFromDb(props, doc, verbose):
    protocol = props[DB_PROTOCOL]
    host     = props[DB_HOST]
    port     = props[DB_PORT]
    username = props[DB_USERNAME]
    password = props[DB_PASSWORD]
    database = props[DB_WHISK_AUTHS]

    url = '%(protocol)s://%(host)s:%(port)s/%(database)s/%(subject)s' % {
        'protocol': protocol,
        'host'    : host,
        'port'    : port,
        'database': database,
        'subject' : doc
    }

    headers = {
        'Content-Type': 'application/json',
    }

    res = request('GET', url, headers=headers, auth='%s:%s' % (username, password), verbose=verbose)
    if res.status == 200:
        doc = json.loads(res.read())
        return (doc, res)
    else:
        return (None, res)

def getIdentitiesFromNamespace(args, props):
    protocol = props[DB_PROTOCOL]
    host     = props[DB_HOST]
    port     = props[DB_PORT]
    username = props[DB_USERNAME]
    password = props[DB_PASSWORD]
    database = props[DB_WHISK_AUTHS]

    url = '%(protocol)s://%(host)s:%(port)s/%(database)s/_design/%(view)s/_view/identities?key=["%(ns)s"]' % {
        'protocol': protocol,
        'host'    : host,
        'port'    : port,
        'username': username,
        'database': database,
        'view'    : args.view,
        'ns'      : args.namespace
    }

    headers = {
        'Content-Type': 'application/json',
    }

    res = request('GET', url, headers=headers, auth='%s:%s' % (username, password), verbose=args.verbose)
    nslist = None
    if res.status == 200:
        doc = json.loads(res.read())
        nslist = []
        if 'rows' in doc and len(doc['rows']) > 0:
            for row in doc['rows']:
                if 'id' in row:
                    nslist.append({"subject": row["id"], "uuid": row['value']['uuid'], "key": row['value']['key']})
    return (nslist, res)

def deleteUserCmd(args, props):
    protocol = props[DB_PROTOCOL]
    host     = props[DB_HOST]
    port     = props[DB_PORT]
    username = props[DB_USERNAME]
    password = props[DB_PASSWORD]
    database = props[DB_WHISK_AUTHS]

    if args.subject.strip() == '':
        print('Subject must not be empty')
        return 2

    if args.namespace and args.namespace.strip() == '':
        print('Namespace must not be empty')
        return 2

    (prev, res) = getDocumentFromDb(props, args.subject, args.verbose)
    if prev is None:
        print('Failed to delete subject (%s)' % res.read().strip())
        return 1

    if not args.namespace:
        url = '%(protocol)s://%(host)s:%(port)s/%(database)s/%(subject)s?rev=%(rev)s' % {
            'protocol': protocol,
            'host'    : host,
            'port'    : port,
            'database': database,
            'subject' : args.subject.strip(),
            'rev'     : prev['_rev']
        }

        headers = {
            'Content-Type': 'application/json',
        }

        res = request('DELETE', url, headers=headers, auth='%s:%s' % (username, password), verbose=args.verbose)
        if res.status in [200, 202]:
            print('Subject deleted')
        else:
            print('Failed to delete subject (%s)' % res.read().strip())
            return 1
    else:
        namespaceToDelete = args.namespace.strip()
        namespaces = [ns for ns in prev['namespaces'] if ns['name'] != namespaceToDelete]
        if len(prev['namespaces']) == len(namespaces):
            print('Namespace "%s" does not exist for "%s"' % (namespaceToDelete, prev['_id']))
            return 1
        else:
            prev['namespaces'] = namespaces
            res = insertIntoDatabase(props, prev, args.verbose)
            if res.status in [201, 202]:
                print('Namespace deleted')
            else:
                print('Failed to remove namespace (%s)' % res.read().strip())
                return 1

def whoisUserCmd(args, props):
    protocol = props[DB_PROTOCOL]
    host     = props[DB_HOST]
    port     = props[DB_PORT]
    username = props[DB_USERNAME]
    password = props[DB_PASSWORD]
    database = props[DB_WHISK_AUTHS]

    authParts = args.authkey.split(':')
    uuid      = authParts[0]
    key       = authParts[1]

    url = '%(protocol)s://%(host)s:%(port)s/%(database)s/_design/%(view)s/_view/identities?key=["%(uuid)s","%(key)s"]' % {
        'protocol': protocol,
        'host'    : host,
        'port'    : port,
        'username': username,
        'database': database,
        'view'    : args.view,
        'uuid'    : uuid,
        'key'     : key
    }

    headers = {
        'Content-Type': 'application/json',
    }

    res = request('GET', url, headers=headers, auth='%s:%s' % (username, password), verbose=args.verbose)
    if res.status == 200:
        doc = json.loads(res.read())
        if 'rows' in doc and len(doc['rows']) > 0:
            for row in doc['rows']:
                if 'id' in row:
                    print('subject: %s' % row['id'])
                    print('namespace: %s' % row['value']['namespace'])
        else:
            print('Subject id is not recognized')
        return 0
    print('Failed to get subject (%s)' % res.read().strip())
    return 1

def blockUserCmd(args, props):
    failed = 0
    for subject in args.subjects:
        subject = subject.strip()
        if len(subject) > 0:
            (doc, res) = getDocumentFromDb(props, subject, args.verbose)

            if doc is not None:
                doc['blocked'] = True
                insertRes = insertIntoDatabase(props, doc, args.verbose)
                if insertRes.status in [201, 202]:
                    print('"%s" blocked successfully' % subject)
                else:
                    print('Failed to block "%s" (%s)' % (subject, res.read().strip()))
                    failed += 1
            else:
                print('Failed to block "%s" (%s)' % (subject, res.read().strip()))
                failed += 1
    return failed

def unblockUserCmd(args, props):
    failed = 0
    for subject in args.subjects:
        subject = subject.strip()
        if len(subject) > 0:
            (doc, res) = getDocumentFromDb(props, subject, args.verbose)

            if doc is not None:
                doc['blocked'] = False
                insertRes = insertIntoDatabase(props, doc, args.verbose)
                if insertRes.status in [201, 202]:
                    print('"%s" unblocked successfully' % subject)
                else:
                    print('Failed to unblock "%s" (%s)' % (subject, res.read().strip()))
                    failed += 1
            else:
                print('Failed to unblock "%s" (%s)' % (subject, res.read().strip()))
                failed += 1
    return failed

def setLimitsCmd(args, props):
    argsDict = vars(args)
    docId = args.namespace + "/limits"
    (dbDoc, res) = getDocumentFromDb(props, quote_plus(docId), args.verbose)
    doc = dbDoc or {'_id': docId}

    limits = ['invocationsPerMinute', 'firesPerMinute', 'concurrentInvocations', 'allowedKinds', 'storeActivations']
    for limit in limits:
        givenLimit = argsDict.get(limit)
        toSet = givenLimit if givenLimit != None else doc.get(limit)
        if toSet != None:
            doc[limit] = toSet

    res = insertIntoDatabase(props, doc, args.verbose)
    if res.status in [201, 202]:
        print('Limits successfully set for "%s"' % args.namespace)
    else:
        print('Failed to set limits (%s)' % res.read().strip())
        return 1

def getLimitsCmd(args, props):
    docId = args.namespace + "/limits"
    (dbDoc, res) = getDocumentFromDb(props, quote_plus(docId), args.verbose)

    if dbDoc is not None:
        limits = ['invocationsPerMinute', 'firesPerMinute', 'concurrentInvocations', 'allowedKinds', 'storeActivations']
        for limit in limits:
            givenLimit = dbDoc.get(limit)
            if givenLimit != None:
                print('%s = %s' % (limit, givenLimit))
    else:
        error = json.loads(res.read())
        if error['reason'] == 'missing' or error['reason'] == 'deleted':
            print('No limits found, default system limits apply')
            return 0
        else:
            print('Failed to get limits (%s)' % res.read().strip())
        return 1

def deleteLimitsCmd(args, props):
    docId = quote_plus(args.namespace + "/limits")
    (dbDoc, res) = getDocumentFromDb(props, docId, args.verbose)

    if dbDoc is None:
        print('Failed to delete limits (%s)' % res.read().strip())
        return 1

    protocol = props[DB_PROTOCOL]
    host     = props[DB_HOST]
    port     = props[DB_PORT]
    username = props[DB_USERNAME]
    password = props[DB_PASSWORD]
    database = props[DB_WHISK_AUTHS]

    url = '%(protocol)s://%(host)s:%(port)s/%(database)s/%(docid)s?rev=%(rev)s' % {
        'protocol': protocol,
        'host'    : host,
        'port'    : port,
        'database': database,
        'docid'   : docId,
        'rev'     : dbDoc['_rev']
    }

    headers = {
        'Content-Type': 'application/json',
    }

    res = request('DELETE', url, headers=headers, auth='%s:%s' % (username, password), verbose=args.verbose)
    if res.status in [200, 202]:
        print('Limits deleted')
    else:
        print('Failed to delete limits (%s)' % res.read().strip())
        return 1

def getDbCmd(args, props):
    protocol = props[DB_PROTOCOL]
    host     = props[DB_HOST]
    port     = props[DB_PORT]
    username = props[DB_USERNAME]
    password = props[DB_PASSWORD]

    if args.database == 'subjects':
        database = props[DB_WHISK_AUTHS]
    elif args.database == 'whisks':
        database = props[DB_WHISK_ACTIONS]
    elif args.database == 'activations':
        database = props[DB_WHISK_ACTIVATIONS]
    else:
        database = args.database

    if args.view:
        try:
            parts = args.view.split('/')
            designdoc = parts[0]
            viewname  = parts[1]
        except:
            print('view name "%s" is not formatted correctly, should be design/view' % args.view)
            return 2

    url = '%(protocol)s://%(host)s:%(port)s/%(database)s%(design)s/%(index)s?reduce=false&include_docs=%(docs)s' % {
        'protocol': protocol,
        'host'    : host,
        'port'    : port,
        'database': database,
        'design'  : '/_design/' + designdoc +'/_view' if args.view else '',
        'index'   : viewname if args.view else '_all_docs',
        'docs'    : 'true' if args.docs else 'false'
    }

    headers = {
        'Content-Type': 'application/json',
    }

    print('getting contents for %s (%s)' % (database, args.view if args.view else 'primary index'))
    res = request('GET', url, headers=headers, auth='%s:%s' % (username, password), verbose=args.verbose)
    if res.status == 200:
        table = json.loads(res.read())
        print(json.dumps(table, sort_keys=True, indent=4, separators=(',', ': ')))
        return 0
    print('Failed to get database (%s)' % res.read().strip())
    return 1

def insertIntoDatabase(props, doc, verbose = False):
    protocol = props[DB_PROTOCOL]
    host     = props[DB_HOST]
    port     = props[DB_PORT]
    username = props[DB_USERNAME]
    password = props[DB_PASSWORD]
    database = props[DB_WHISK_AUTHS]

    url = '%(protocol)s://%(host)s:%(port)s/%(database)s' % {
        'protocol': protocol,
        'host'    : host,
        'port'    : port,
        'database': database
    }
    body = json.dumps(doc)
    headers = {
        'Content-Type': 'application/json',
    }

    res = request('POST', url, body, headers, auth='%s:%s' % (username, password), verbose=verbose)
    return res

def getLogsCmd(args, props):
    def getComponentLogs(component):
        path = '%s/%s/%s_logs.log' % (props[LOGS_DIR], component, component)
        if args.tid:
            cmd = r'grep "\[#tid_%s\]" %s' % (args.tid, path)
        elif args.grep:
            cmd = 'grep "%s" %s' % (args.grep, path)
        else:
            cmd = 'cat %s' % path
        (output, error) = shell(cmd, verbose = args.verbose)

        if output:
            return output.decode('utf-8')
        if error:
            sys.stderr.write(error)
        return ''

    logs = map(getComponentLogs, args.components)
    joined = ''.join(logs)

    if joined:
        output = joined.strip()
        parts = output.split('\n')
        filter = [p for p in parts if p != '']
        date = map(extractDate, filter)
        keyed = zip(date, parts)
        sort = sorted(keyed, key=lambda t: t[1])
        msgs = list(unzip(sort))[1]
        print('\n'.join(msgs))
    return 0

def shell(cmd, data=None, verbose=False):
    if verbose:
        print(cmd)
    if input:
        p = Popen(cmd, shell=True, stdout=PIPE, stderr=STDOUT, stdin=PIPE)
        out, err = p.communicate(input=data)
    else:
        out, err = Popen(cmd, shell=True, stdout=PIPE, stderr=STDOUT)
    p.wait()
    return (out, err)

def unzip(iterable):
    return zip(*iterable)

def extractDate(line):
    matches = re.search(r'\d{4}-[01]{1}\d{1}-[0-3]{1}\d{1}T[0-2]{1}\d{1}:[0-6]{1}\d{1}:[0-6]{1}\d{1}.\d{3}Z', line)
    if matches is not None:
        date = matches.group(0)
        return date
    else:
        return None

if __name__ == '__main__':
    main()
