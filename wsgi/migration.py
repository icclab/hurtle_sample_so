
import yaml
import re

__author__ = 'merne'

versionRe = re.compile(r'^[vV]\d+_.+')
sharedRe = re.compile(r'^shared_.+')


class MigrationTemplateGenerator:

    def __init__(self, old_version_template=None, old_version_file=None, new_version_template=None, new_version_file=None):
        # provide either templates or paths to files

        if not old_version_template and not old_version_file:
            raise AttributeError('Provide either old_version_template or old_version_file')
        if not new_version_template and not new_version_file:
            raise AttributeError('Provide either new_version_template or new_version_file')

        if not old_version_template:
            with open(old_version_file, 'r') as stream:
                self.old_version = yaml.load(stream)
        else:
            self.old_version = old_version_template

        if not new_version_template:
            with open(new_version_file, 'r') as stream:
                self.new_version = yaml.load(stream)
        else:
            self.new_version = new_version_template

    def generate_all(self):

        return {1: self.generate_first(),
                2: self.generate_second(),
                3: self.new_version}

    def generate_first(self):
        # returns generated template (dict)
        # raises RuntimeError

        generated = dict()
        generated['description'] = self.old_version['description']
        generated['heat_template_version'] = self.old_version['heat_template_version']

        # this needs to be enhanced at some point
        generated['parameters'] = self.old_version['parameters']
        generated['outputs'] = self.old_version['outputs']

        generated['resources'] = self.old_version['resources'].copy()

        for name, resource in self.new_version['resources'].iteritems():
            resource_type = resource['type']
            category = self.get_category(resource_type, name)

            if category == 'Version':
                generated['resources'][name] = resource

            if category == 'Shared':
                if self.old_version['resources'][name] != self.new_version['resources'][name]:
                    raise RuntimeError('Shared resource %s differs!' % name)

            if category == 'Routing':
                pass

            if category == 'None':
                raise RuntimeError('Unsupported resource_type/name combination found! '
                                   'resource_type: %s name: %s' % (resource_type, name))

        return generated

    def generate_second(self):
        # returns generated template (dict)
        # raises RuntimeError
        generated = dict()
        generated['description'] = self.old_version['description']
        generated['heat_template_version'] = self.old_version['heat_template_version']

        # this needs to be enhanced at some point
        generated['parameters'] = self.old_version['parameters']
        generated['outputs'] = self.old_version['outputs']

        generated['resources'] = self.old_version['resources'].copy()

        for name, resource in self.new_version['resources'].iteritems():
            resource_type = resource['type']
            category = self.get_category(resource_type, name)

            if category == 'Version':
                generated['resources'][name] = resource

            if category == 'Shared':
                if self.old_version['resources'][name] != self.new_version['resources'][name]:
                    raise RuntimeError('Shared resource %s differs!' % name)

            if category == 'Routing':
                generated['resources'][name] = resource

            if category == 'None':
                raise RuntimeError('Unsupported resource_type/name combination found! '
                                   'resource_type: %s name: %s' % (resource_type, name))

        return generated

    @staticmethod
    def get_category(resource_type, name):
        # this will return one of the following:
        # 'Version', 'Shared', 'Routing' or 'None'

        versioned = [
            'OS::Nova::Server',
            'OS::Neutron::Port'
        ]
        shared = [
            'OS::Heat::RandomString',
            'OS::Neutron::Net',
            'OS::Neutron::Subnet',
            'OS::Neutron::SecurityGroup',
            'OS::Neutron::Router',
            'OS::Neutron::RouterInterface',
            'OS::Neutron::Port',
            'OS::Nova::Server'
        ]
        routing = [
            'OS::Neutron::FloatingIP'
        ]

        if resource_type in versioned:
            if bool(versionRe.search(name)):
                return 'Version'
        if resource_type in shared:
            if bool(sharedRe.search(name)):
                return 'Shared'
        if resource_type in routing:
            if not bool(versionRe.search(name)) and not bool(sharedRe.search(name)):
                return 'Routing'
        return 'None'
