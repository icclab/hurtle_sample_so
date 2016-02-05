from pymongo import MongoClient
import os
import sys
sys.stdout = sys.stderr


def get_mongo_connection():

    so_name = os.environ.get('DC_NAME', False)
    if not so_name:
        raise RuntimeError('DC_NAME not defined!')
    mongo_service_name = so_name.upper().replace('-', '_')
    db_host_key = mongo_service_name + '_M_SERVICE_HOST'
    db_port_key = mongo_service_name + '_M_SERVICE_PORT'
    print 'getting mongo connection details via env: %s & %s' % (db_host_key, db_port_key)

    db_host = os.environ.get(db_host_key, False)
    db_port = os.environ.get(db_port_key, False)
    print 'resolved mongo host to %s:%s' % (db_host, db_port)
    if not db_host:
        raise RuntimeError(db_host_key + ' not defined!')
    if not db_port:
        raise RuntimeError(db_port_key + 'not defined!')

    db_user = os.environ.get('DB_USER', 'admin')
    db_password = os.environ.get('DB_PASSWORD', 'hurtle')

    db_uri = 'mongodb://%s:%s@%s' % (db_user, db_password, db_host)
    connection = MongoClient(db_uri, int(db_port))
    resources_db = connection.resources_db
    return resources_db.stacks

