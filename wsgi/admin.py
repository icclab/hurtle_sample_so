from flask import Flask
import requests
import json
import yaml
import os
import copy
import urllib2
from wsgi.mongo import get_mongo_connection
from wsgi.migration import MigrationTemplateGenerator
from sdk.mcn import util
import sys
sys.stdout = sys.stderr

app = Flask('hurtle-so')

cc_admin_url = os.environ.get('CC_ADMIN_URL', False)

so_name = os.environ.get('DC_NAME', False)


def print_response(response):
    if response.content:
        print '> %i: %s' % (response.status_code, response.content)
    else:
        print '> %i' % response.status_code


def deep_equal(a, b):
    # if a and b are dicts and only contain lists and dicts, this should work
    # we need to do a deepcopy as the default .copy() on the dict is shallow.
    a_copy = copy.deepcopy(a)
    for region in a_copy:
        del a_copy[region]['id']
        del a_copy[region]['token']
        del a_copy[region]['tenant_name']

    return a_copy == b


def save_itg(desired):

    db = get_mongo_connection()

    for region_name, region in desired.iteritems():
        document_filter = {
            "_id": region['id'],
            "region": region_name
        }

        db.update_one(document_filter, {
            "$set": {
                "deploy": desired['deploy'],
                "provision": desired['provision']
            }
        })


def save_stg(desired):
    pass


def save(desired):
    save_itg(desired['itg'])
    save_stg(desired['stg'])


def get_current():

    # TODO: handle multiple stacks as well (multiple regions)

    db = get_mongo_connection()
    stacks = db.find()
    current = {
        'stg': {},
        'itg': dict()
    }
    for stack in stacks:

        current['itg'][stack['region']] = {
            'deploy': yaml.load(stack['deploy']),
            'provision': yaml.load(stack['provision']),
            'id': stack['_id'],
            'token': stack['token'],
            'tenant_name': stack['tenant_name']
        }
    return current


def get_desired():

    # how do we know which STG to read?
    # i guess we hardcode... why not?

    # which region? do we know this here?
    # i guess that needs to be specified somewhere?

    # for now we just hardcode it

    with open('./data/service_manifest.json') as content:
        stg = json.loads(content.read())

    desired = {
        'stg': stg,
        'itg': dict()
    }

    for region_name, region in stg['resources'].iteritems():

        deployment_path = region['deployment']
        provision_path = region['provision']

        deploy = ''
        provision = ''

        # this should have some error handling
        if deployment_path:
            deploy = yaml.load(urllib2.urlopen(deployment_path).read())
        if provision_path:
            provision = yaml.load(urllib2.urlopen(provision_path).read())

        desired['itg'][region_name] = {
                'deploy': deploy,
                'provision': provision
        }

    return desired


def check_for_updates():
    current = get_current()
    if len(current['itg'].keys()) != 0:
        desired = get_desired()

        update_itg_if_required(current['itg'], desired['itg'])
        update_stg_if_required(current['stg'], desired['stg'])

        # we pass both as current may contain some old data not yet copied to desired
        save(desired)
    else:
        # first time we run, we have no current stack...
        print 'First run, not updating anything...'

def update_itg_if_required(current, desired):
    if not deep_equal(current, desired):
        print 'ITG does require migration!'

        update_itg(current, desired)
    else:
        print 'ITG does not require migration!'


def update_itg(current, desired):
    # we migrate from current.provision to desired.deploy, then update to desired.provision

    # XXX: integration point for state migration work
    # might need another separation below, depending on if state is migrated or not

    migration_templates = {}

    for region_name, region in current.iteritems():
        if not desired[region_name]:
            raise RuntimeError('Region not found in target template!')

        migration_templates[region_name] = {}

        template_generator = MigrationTemplateGenerator(old_version_template=current[region_name]['provision'],
                                                        new_version_template=desired[region_name]['deploy'])

        migration_templates[region_name] = template_generator.generate_all()
        migration_templates[region_name][4] = desired[region_name]['provision']

    for region_name, region in migration_templates.iteritems():
        for step, template in region.iteritems():
            token = current[region_name]['token']
            tenant = current[region_name]['tenant_name']
            stack_id = current[region_name]['id']
            template_raw = yaml.dump(template)

            deployer = util.get_deployer(token, url_type='public', tenant_name=tenant, region=region_name)

            #TODO: here add some error handling
            deployer.update(identifier=stack_id, template=template_raw, token=token)

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
    check_for_updates()

    all_ok = True
    if not cc_admin_url:
        print 'No CC_ADMIN_URL configured!'
        all_ok = False
    if not so_name:
        print 'No DC_NAME configured!'
        all_ok = False

    if all_ok:
        print 'Admin API listening on %s:%i' % (host, port)
        app.run(host=host, port=port, debug=False)
    else:
        print 'Admin API will not be started!'
