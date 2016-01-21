from flask import Flask
import requests
import json
import os

app = Flask('hurtle-so')

cc_admin_url = os.environ.get('CC_ADMIN_URL', False)

so_name = os.environ.get('DC_NAME', False)

# should this be set somewhere...
region = 'RegionOne'


def print_response(response):
    if response.content:
        print '> %i: %s' % (response.status_code, response.content)
    else:
        print '> %i' % response.status_code


def deep_equal(a, b):
    # if a and b are dicts and only contain lists and dicts, this should work
    return a == b


def save(data):
    pass


def get_current():
    return {
        'itg': {},
        'stg': {}
    }


def get_desired():

    # how do we know which STG to read?
    # i guess we hardcode... why not?

    # which region? do we know this here?
    # i guess that needs to be specified somewhere?

    # for now we just hardcode it

    with open('./data/service_manifest.json') as content:
        stg = json.loads(content)

    deployment_path = stg['resources'][region]['deployment']
    provision_path = stg['resources'][region]['deployment']

    deployment = ''
    provision = ''

    if deployment_path:
        with open(deployment_path) as content:
            deployment = content
    if provision_path:
        with open(provision_path) as content:
            provision = content

    return {
        'itg': {
            'deployment': deployment,
            'provision': provision
        },
        'stg': stg
    }


def check_for_updates():
    current = get_current()
    desired = get_desired()

    update_itg_if_required(current['itg'], desired['itg'])
    update_stg_if_required(current['stg'], desired['stg'])

    save(desired)


def update_itg_if_required(current, desired):
    if not deep_equal(current, desired):
        update_itg(current, desired)


def update_itg(current, desired):
    return True


def update_stg_if_required(current, desired):
    if not deep_equal(current, desired):
        update_stg(current, desired)


def update_stg(current, desired):
    return True


@app.route('/')
def home():
    return '', 200


@app.route('/self')
def self_info():
    return json.dumps({'so_name': so_name}), 200


# curl -X POST $URL/update/self -> update this SO
@app.route('/update/<name>', methods=['POST'])
def update(name):
    if name == 'self':
        print '### Redeploying myself...'
        url = cc_admin_url + '/update/%s' % so_name
        print 'curl -v -X POST %s' % url
        response = requests.post(url)
        print_response(response)

        return response.content, response.status_code
    else:
        return 'not implemented', 500


def server(host, port):
    print 'Admin API listening on %s:%i' % (host, port)
    #check_for_updates()

    all_ok = True
    if not cc_admin_url:
        print 'No CC_ADMIN_URL configured!'
        all_ok = False
    if not so_name:
        print 'No DC_NAME configured!'
        all_ok = False

    if all_ok:
        app.run(host=host, port=port, debug=False)
    else:
        print 'Admin API will not be started!'
