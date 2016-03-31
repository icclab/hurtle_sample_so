#   Copyright (c) 2013-2015, Intel Performance Learning Solutions Ltd, Intel Corporation.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""
Sample SO.
"""

import os
import time

from sdk.mcn import util
from sm.so import service_orchestrator
from sm.so.service_orchestrator import LOG

import json
import urllib2
from wsgi.mongo import get_mongo_connection


class SOEExtn(service_orchestrator.Execution):

    def __init__(self, token, tenant, **kwargs):
        """
        This will setup heat clients and associated resource manifests per region
        """
        super(SOEExtn, self).__init__(token, tenant, **kwargs)
        self.token = token
        self.tenant = tenant
        extras = kwargs.get('extras', {})
        # FIXME(edmo): remove or document hardcoding

        self.service_manifest = self.__service_manifest(extras)
        # self.deployer = {}
        # self.deployer = self.__deployer(self.service_manifest)
        # TODO make call for check to update here
        # TODO SOs update only on boot
        # XXX SO receives update call and then asks CC to update itself
        self.db = get_mongo_connection()

    def __service_manifest(self, extras):
        s_mani = {}
        path = '/opt/app-root/src/data/service_manifest.json'
        #path = './data/service_manifest.json'
        with open(path) as file:
            s_mani = json.loads(file.read())

        # s_mani = s_mani.read()
        # sm_hash = hashlib.md5(str(s_mani)).hexdigest()

        # s_mani = json.loads(s_mani)
        # s_mani['hash'] = sm_hash
        # TODO this is ugly - should be an attribute of depends_on however depends_on is only an array
        # s_mani['depends_on_hash'] = hashlib.md5(str(s_mani['depends_on'])).hexdigest()

        s_mani = self.__deployer(s_mani)

        return s_mani

    def __deployer(self, s_mani):
        """
        this modifies the in-memory copy of the service manifest
        """
        deployer = {}
        # deployer['hash'] = hashlib.md5(str(s_mani['resources'])).hexdigest()
        for region in s_mani['resources'].keys():
            # create a hash per deployment and provisioning template to use later in detecting updates
            dep = urllib2.urlopen(s_mani['resources'][region]['deployment']).read()
            # dep['hash'] = hashlib.md5(str(dep)).hexdigest()
            prov = urllib2.urlopen(s_mani['resources'][region]['provision']).read()
            # prov['hash'] = hashlib.md5(str(prov)).hexdigest()

            deployer[region] = {
                'client': util.get_deployer(self.token, url_type='public', tenant_name=self.tenant, region=region),
                'deployment': dep,
                'provision': prov,
                'stack_id': ''
            }

        s_mani['resources'] = deployer
        return s_mani

    def design(self):
        # super(SOEExtn, self).design()
        LOG.info('Entered design() - nothing to do here')

    def deploy(self):
        # super(SOEExtn, self).deploy()
        # TODO check that the deployment descriptor is present

        # TODO: refactor this to: for region_name, region in self.service_manifest['resources'].iteritems()
        for region in self.service_manifest['resources'].keys():
            if len(self.service_manifest['resources'][region]['stack_id']) < 1:
                self.service_manifest['resources'][region]['stack_id'] = \
                    self.service_manifest['resources'][region]['client'].deploy(self.service_manifest['resources'][region]['deployment'], self.token)
                LOG.info('Stack ID: ' + self.service_manifest['resources'][region]['stack_id'])

                LOG.info('waiting for stack to get ready...')
                done = False
                while not done:
                    details = self.service_manifest['resources'][region]['client'].details(self.service_manifest['resources'][region]['stack_id'], self.token)
                    LOG.info('current state: %s' % details['state'])
                    if details['state'] == 'CREATE_COMPLETE' or details['state'] == 'UPDATE_COMPLETE':
                        done = True
                    else:
                        time.sleep(3)

                if self.db:

                    # persist data
                    document_filter = {
                        "_id": self.service_manifest['resources'][region]['stack_id'],
                        "region": region
                    }
                    data = {
                        "_id": self.service_manifest['resources'][region]['stack_id'],
                        "token": self.token,
                        "tenant_name": self.tenant,
                        "region": region,
                        "deploy": self.service_manifest['resources'][region]['deployment']
                    }
                    current = self.db.find_one(document_filter)
                    if not current:
                        self.db.insert(data)
                    else:
                        # does this case ever happen?
                        self.db.update_one(document_filter, {
                            "$set": {
                                'deploy': data['deploy']
                            }
                        })

    def provision(self):
        # super(SOEExtn, self).provision()
        # TODO check that the provision descriptor is present

        # TODO: refactor this to: for region_name, region in self.service_manifest['resources'].iteritems()
        for region in self.service_manifest['resources'].keys():
            if len(self.service_manifest['resources'][region]['stack_id']) > 0:
                self.service_manifest['resources'][region]['client'].update(self.service_manifest['resources'][region]['stack_id'],
                                                       self.service_manifest['resources'][region]['provision'], self.token)
                LOG.info('Stack ID: ' + self.service_manifest['resources'][region]['stack_id'])

                if self.db:
                    # persist data
                    document_filter = {
                        "_id": self.service_manifest['resources'][region]['stack_id'],
                        "region": region
                    }
                    data = {
                        "_id": self.service_manifest['resources'][region]['stack_id'],
                        "token": self.token,
                        "region": region,
                        "provision": self.service_manifest['resources'][region]['provision']
                    }

                    current = self.db.find_one(document_filter)
                    if not current:
                        self.db.insert(data)
                    else:

                        self.db.update_one(document_filter, {
                            "$set": {
                                'provision': data['provision'],
                                'token': data['token']
                            }
                        })


    # XXX admin interface triggers update of SO implementation
    def update(self, old, new, extras):
        # super(SOEExtn, self).update(old, new, extras)
        new_service_manifest = self.__service_manifest(extras)
        self.compare(self.service_manifest, new_service_manifest)

    def compare(self, old, new):
        if not old['hash'] == new['hash']:
            if not old['depends_on_hash'] == new['depends_on_hash']:
                print 'service dependencies have changed'
                print 'signal resolver to update'
                if len(old['depends_on']) > len(new['depends_on']):
                    print 'remove:\n' + str(old['depends_on']) + '\n'
                elif len(new['depends_on']) > len(old['depends_on']):
                    print 'add:\n' + str(new['depends_on']) + '\n'
                else:
                    print 'should have done something...'

            if not old['resources']['hash'] == new['resources']['hash']:
                print 'resources have changed'
                print 'signal blue/green update\n'
        else:
            print 'nothing has changed\n'

    def state(self):
        # super(SOEExtn, self).state()
        stack_state = ''
        stack_ids = ''
        outputs = []
        for region in self.service_manifest['resources'].keys():
            tmp = self.service_manifest['resources'][region]['client'].details(self.service_manifest['resources'][region]['stack_id'], self.token)
            LOG.info('Returning Stack output state')


            # for stack state, we return the least successful one
            # e.g. one stack "CREATE_COMPLETED', one "CREATE_FAILED" -> we return CREATE_FAILED
            #      one stack with "CREATE_IN_PROGRESS", one "CREATE_COMPLETED" -> we return CREATE_IN_PROGRESS
            #

            successful_states = ['CREATE_COMPLETE', 'UPDATE_COMPLETE']
            ongoing_states = ['CREATE_IN_PROGRESS', 'UPDATE_IN_PROGRESS']
            failed_states = ['CREATE_FAILED', 'UPDATE_FAILED']
            no_state = ['']

            current_state = tmp['state']
            if stack_state == '':
                stack_state = current_state
            else:
                # we already have a state present...
                if current_state in successful_states:
                    # no need to write a successful state back
                    pass
                if current_state in ongoing_states:
                    # if the saved state is 'better', overwrite
                    if stack_state in successful_states:
                        stack_state = current_state
                if current_state in failed_states:
                    # if the saved state is 'better', overwrite
                    if stack_state in successful_states or stack_state in ongoing_states:
                        stack_state = current_state



            # for stack_id, we concat them together with their region-names:
            # region1:stack-id1,region2:stack-id2
            if len(stack_ids) == 0:
                stack_ids = '%s:%s' % (region, self.service_manifest['resources'][region]['stack_id'])
            else:
                stack_ids = '%s,%s:%s' %(stack_ids, region, self.service_manifest['resources'][region]['stack_id'])

            # for stack_output, we add the region name at the end of every key
            # a.b.c in region 1 becomes a.b.c.region1
            try:
                current_outputs = tmp['output']
                for output in current_outputs:
                    outputs.append({
                        'output_key': '%s.%s' % (output['output_key'], region.replace(' ', '')),
                        'output_value': output['output_value']
                    })
            except KeyError:
                pass

        return stack_state, stack_ids, outputs


    def notify(self, entity, attributes, extras):
        super(SOEExtn, self).notify(entity, attributes, extras)

    def dispose(self):
        """
        Dispose SICs.
        """
        # super(SOEExtn, self).dispose()
        LOG.info('Calling dispose')
        for region in self.service_manifest['resources'].keys():
            if len(self.service_manifest['resources'][region]['stack_id']) > 0:
                self.service_manifest['resources'][region]['client'].dispose(self.service_manifest['resources'][region]['stack_id'], self.token)
                self.service_manifest['resources'][region]['stack_id'] = ''


class SOE(SOEExtn):
    """
    Sample SO execution part.
    """

    def __init__(self, token, tenant, **kwargs):
        super(SOE, self).__init__(token, tenant)

    def design(self):
        """
        Do initial design steps here.
        """
        super(SOE, self).design()

    def deploy(self):
        """
        deploy SICs.
        """
        LOG.info('Calling deploy')
        super(SOE, self).deploy()

    def provision(self):
        """
        (Optional) if not done during deployment - provision.
        """

        LOG.info('Calling provision')
        super(SOE, self).provision()

    def dispose(self):
        """
        Dispose SICs.
        """
        LOG.info('Calling dispose')
        super(SOE, self).dispose()

    def state(self):
        """
        Report on state.
        """
        LOG.info('Calling state')
        return super(SOE, self).state()

    def update(self, old, new, extras):
        # TODO implement your own update logic - this could be a heat template update call
        super(SOE, self).update(old, new, extras)
        LOG.info('Calling update - nothing to do!')
        if len(self.service_manifest) > 0:
            LOG.info('The service manifest is updated!')


class SOD(service_orchestrator.Decision):
    """
    Sample Decision part of SO.
    """

    def __init__(self, so_e, token, tenant, service_manifest):
        super(SOD, self).__init__(so_e, token, tenant)

    def run(self):
        """
        Decision part implementation goes here.
        """
        pass


class ServiceOrchestrator(object):
    """
    Sample SO.
    """

    def __init__(self, token, tenant):
        self.so_e = SOE(token, tenant)
        self.so_d = SOD(self.so_e, token, tenant, {})
        # so_d.start()
#
# if __name__ == '__main__':
#     extras = {
#         'it.hurtle.service_manifest': 'file:///Users/andy/Source/MCN/Source/demo-sm1/bundle/data/service_manifest.json'
#     }
#     test = SOEExtn(tenant='edmo', token='7c66db7430164abc94e1ad94c77cb311', extras=extras)
#
#     # test that no changes are made if the same manifest is presented
#     old = new = {}
#     extras['it.hurtle.service_manifest'] = 'file:///Users/andy/Source/MCN/Source/demo-sm1/bundle/data/service_manifest.json'
#     test.update(old, new, extras)
#
#     # test that changes will be made if an updated manifest is presented
#     old = new = {}
#     extras['it.hurtle.service_manifest'] = 'file:///Users/andy/Source/MCN/Source/demo-sm1/bundle/data/service_manifest-uptd.json'
#     test.update(old, new, extras)
