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

from sdk.mcn import util
from sm.so import service_orchestrator
from sm.so.service_orchestrator import LOG
from sm.so.service_orchestrator import BUNDLE_DIR


class SOE(service_orchestrator.Execution):
    """
    Sample SO execution part.
    """

    def __init__(self, token, tenant):
        super(SOE, self).__init__(token, tenant)
        self.stack_id = None
        region_name = 'RegionOne'
        self.deployer = util.get_deployer(token,
                                          url_type='public',
                                          tenant_name=tenant,
                                          region=region_name)
        LOG.info('Bundle dir: ' + BUNDLE_DIR)

    def design(self):
        """
        Do initial design steps here.
        """
        LOG.info('Entered design() - nothing to do here')

    def deploy(self):
        """
        deploy SICs.
        """
        LOG.info('Calling deploy')
        if self.stack_id is None:
            f = open(os.path.join(BUNDLE_DIR, 'data', 'test.yaml'))
            template = f.read()
            f.close()
            self.stack_id = self.deployer.deploy(template, self.token)
            LOG.info('Stack ID: ' + self.stack_id.__repr__())

    def provision(self):
        """
        (Optional) if not done during deployment - provision.
        """
        LOG.info('Calling provision - nothing to do here yet!')
        # if self.stack_id is not None:
        #     f = open(os.path.join(BUNDLE_DIR, 'data', 'provision.yaml'))
        #     template = f.read()
        #     f.close()
        #     # TODO read parameters from extras, if no parameters at this stage
        #     #      assume that it will be supplied via an update.
        #     # TODO set defaults
        #     self.deployer.update(self.stack_id, template, self.token, parameters={'mme_pgwc_sgwc_input':'8.8.8.8'})
        #     LOG.info('Updated stack ID: ' + self.stack_id.__repr__())

    def dispose(self):
        """
        Dispose SICs.
        """
        LOG.info('Calling dispose')
        if self.stack_id is not None:
            self.deployer.dispose(self.stack_id, self.token)
            self.stack_id = None

    def state(self):
        """
        Report on state.
        """
        if self.stack_id is not None:
            tmp = self.deployer.details(self.stack_id, self.token)
            LOG.info('Returning Stack output state')
            output = ''
            try:
                output = tmp['output']
            except KeyError:
                pass
            return tmp['state'], self.stack_id, output
        else:
            LOG.info('Stack output: none - Unknown, N/A')
            return 'Unknown', 'N/A', None

    def update(self, old, new, extras):
        if self.stack_id is not None:
            f = open(os.path.join(BUNDLE_DIR, 'data', 'test.yaml'))
            template = f.read()
            f.close()

            # XXX the attribute mcn.endpoint.mme-pgwc-sgwc must be present, otherwise fail

            self.deployer.update(self.stack_id, template, self.token)
            LOG.info('Updated stack ID: ' + self.stack_id.__repr__())

class SOD(service_orchestrator.Decision):
    """
    Sample Decision part of SO.
    """

    def __init__(self, so_e, token, tenant):
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
        self.so_d = SOD(self.so_e, token, tenant)
        # so_d.start()
