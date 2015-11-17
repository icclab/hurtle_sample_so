#   Copyright (c) 2013-2015, Intel Performance Learning Solutions Ltd, Intel Corporation.
#   Copyright 2015 Zuercher Hochschule fuer Angewandte Wissenschaften
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
import threading
import yaml

from sdk.mcn import util
from sdk.mcn import runtime
from sm.so import service_orchestrator
from sm.so.service_orchestrator import LOG
from sm.so.service_orchestrator import BUNDLE_DIR

HERE = BUNDLE_DIR


class SOE(service_orchestrator.Execution):

    def __init__(self, token, tenant, ready_event, **kwargs):
        super(SOE, self).__init__(token, tenant)
        self.token = token
        self.tenant = tenant
        self.event = ready_event
        self.app_url = kwargs.get('app_url', 'http://localhost:8080/orchestrator/default')
        f = open(os.path.join(HERE, 'data', 'one-vm.yaml'))
        self.template = f.read()
        f.close()
        self.stack_id = None
        self.deployer = util.get_deployer(self.token,
                                          url_type='public',
                                          tenant_name=self.tenant)

        self.template_obj = yaml.load(self.template)
        self.mon_user = self.mon_pass = self.mon_id = None
        self.mon_not = dict()
        self.mon_not_ids = []
        self.hostname = 'host1'  # the name of the host we'll monitor
        self.service = 'IAMSERVICE4'
        # as resource are renamed when template is updated to recreate a resource,
        #    one needs to keep track of mappings between original name
        #    and updated name if the renamed resource fails again
        self.mappings = dict()

    def design(self):
        """
        Do initial design steps here.
        """
        LOG.debug('Executing design logic')
        # self.resolver.design()

    def deploy(self, attributes=None):
        """
        deploy SICs.
        """
        # LOG.debug('Deploy service dependencies')
        # self.resolver.deploy()
        LOG.debug('Executing deployment logic')
        if self.stack_id is None:

            # let's add monasca service

            rt = runtime.Monasca(self.token, self.tenant, auth_url=os.environ['DESIGN_URI'])

            # user creation specific to SO instance to pass to monasca-agent within VMs
            if self.mon_user is None and self.mon_pass is None:
                self.mon_id, self.mon_user, self.mon_pass = rt.create_user()

            params = dict()
            params['username'] = self.mon_user
            params['password'] = self.mon_pass
            params['tenant'] = self.tenant
            params['service_id'] = self.service
            params['hostname'] = self.hostname

            self.stack_id = self.deployer.deploy(self.template, self.token, parameters=params)
            # need a way to get local SO url from opsv3 to setup a notification url
            notification_url = self.app_url
            n_name, n_id = rt.notify('(avg(cpu.user_perc{service=' + self.service +
                                     ',hostname='+self.hostname+'}) > 100)',
                                     notification_url, runtime.ACTION_UNDETERMINED)
            self.mon_not[n_name] = "replace_host1"
            self.mon_not_ids.append(n_id)
            LOG.debug("created alarm: " + n_name + " with id: " + n_id + " and action: " + self.mon_not[n_name])

            # fill the mapping
            self.mappings['rcb_si'] = 'rcb_si'  # initial mapping: resource name on heat template is same as expected

            LOG.info('Resource dependencies - stack id: ' + self.stack_id)

    def provision(self, attributes=None):
        """
        (Optional) if not done during deployment - provision.
        """

        # self.resolver.provision()
        # LOG.info('Now I can provision my resources once my resources are created. Service info:')
        # LOG.info(self.resolver.service_inst_endpoints)
        #
        # # TODO add you provision phase logic here
        # # XXX note that provisioning of external services must happen before resource provisioning

        LOG.debug('Executing resource provisioning logic')
        # once logic executes, deploy phase is done
        # self.event.set()

    def dispose(self):
        """
        Dispose SICs.
        """
        # LOG.info('Disposing of 3rd party service instances...')
        # self.resolver.dispose()

        if self.stack_id is not None:
            LOG.info('Disposing of resource instances...')
            self.deployer.dispose(self.stack_id, self.token)
            self.stack_id = None
            # TODO on disposal, the SOE should notify the SOD to shutdown its thread

            # Removing users, alarm-def
            rt = runtime.Monasca(self.token, self.tenant, auth_url=os.environ['DESIGN_URI'])
            rt.delete_user(self.mon_id)
            for n_id in self.mon_not_ids:
                rt.dispose_monasca(n_id)

    def state(self):
        """
        Report on state.
        """

        # TODO ideally here you compose what attributes should be returned to the SM
        # In this case only the state attributes are returned.
        # resolver_state = self.resolver.state()
        # LOG.info('Resolver state:')
        # LOG.info(resolver_state.__repr__())

        if self.stack_id is not None:
            tmp = self.deployer.details(self.stack_id, self.token)

            return tmp.get('state', 'Unknown'), self.stack_id, tmp.get('output', [])
        else:
            return 'Unknown', 'N/A', []

    def update(self, old, new, extras):
        # TODO implement your own update logic - this could be a heat template update call - not to be confused
        # with provisioning
        pass

    def notify(self, entity, attributes, extras):
        super(SOE, self).notify(entity, attributes, extras)
        # TODO here you can add logic to handle a notification event sent by the CC
        # XXX this is optional
        LOG.debug('my token is: ' + self.token)
        # self.token remains the one used to initialize the SO! so any token in the request works as long as there's one
        try:
            alarm_name = attributes['notification.alarm_name']
        except KeyError:
            raise ValueError("Notify action missing notification.alarm_name OCCI attribute")
        LOG.debug("Alarm name is: " + alarm_name)

        LOG.debug('updating template!')
        if alarm_name in self.mon_not:
            if self.mon_not[alarm_name] == 'replace_host1':
                # suppose we have to delete rcb_si and replace it
                # pop the resource

                # find the name in the current version of the template
                old_res_name = self.mappings['rcb_si']
                if old_res_name != 'rcb_si':
                    new_res_name = 'rcb_si'
                    self.mappings['rcb_si'] = 'rcb_si'
                else:
                    new_res_name = 'rcb_si_1'
                    self.mappings['rcb_si'] = 'rcb_si_1'

                old_res = self.template_obj.get('resources').pop(old_res_name)
                # reinsert it with different key
                self.template_obj.get('resources')[new_res_name] = old_res

                # dump the template as a string ready for heat
                template_updated = yaml.dump(self.template_obj)
                LOG.debug("update the stack")

                if self.stack_id is not None:
                    # stack needs to be parameterized same as in deploy
                    params = {}
                    params['username'] = self.mon_user
                    params['password'] = self.mon_pass
                    params['tenant'] = self.tenant
                    params['service_id'] = self.service
                    self.deployer.update(self.stack_id, template_updated, self.token, parameters=params)
                    LOG.debug("TEMPLATE UPDATED!")


class ServiceOrchestrator(object):
    """
    Sample SO.
    """

    def __init__(self, token, tenant, **kwargs):
        # this python thread event is used to notify the SOD that the runtime phase can execute its logic
        self.event = threading.Event()
        app_url = kwargs.get('app_url', '')
        LOG.debug('app_url callback: ' + app_url)
        if len(app_url) > 0:
            self.so_e = SOE(token=token, tenant=tenant, ready_event=self.event, app_url=app_url)
        else:
            self.so_e = SOE(token=token, tenant=tenant, ready_event=self.event)

        # XXX there is no SOD for this SO as that functionality is delegated to the CC's RT component


# basic test
if __name__ == '__main__':

    token = ''
    tenant = ''

    soe = SOE(token, tenant, threading.Event())
    soe.design()
    soe.deploy()
    soe.provision()
    soe.dispose()
