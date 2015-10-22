## Reactive Orchestration with Monasca

### Monasca Setup

The entire Monasca setup is beyond the scope of this documentation, refer to https://github.com/hpcloud-mon/monasca-installer for an automated way to install Monasca using Ansible. 

You will need to install a specific version of monasca-notification and of monasca-api. 

For monasca-notification, install via pip:

    pip install monasca-notification.tar.gz
    
For monasca-api, you need to replace the monasca-api jar file directly in /opt/monasca using the provided file. Do not forget to stop the service before.

    service stop|start monasca-api
    
### Monasca-notification configuration

A specific configuration for the occi_webhook notification type needs to be added to the configuration file of monasca-notification. In a typical installation, this file is /etc/monasca/notification.yml.

The occi_webhook notification type needs the configuration information of a user. In Hurtle, all requests need to provide a token for authentication, so to be able to provide the callback, the monasca-notification engine needs to generate a token too. It will send OCCI requests using a token from the user specified in the configuration file. This user will need to be in all tenants from which requests might come, as it will use the tenant of the user who deployed the SO.

Example configuration:

    notification_types:
        occi_webhook:
            timeout: 5
            user_name: monasca-agent # username
            password: mon4hurtle # password
            auth_url: "http://bart.cloudcomplab.ch:5000/v2.0" # design uri
            
### Heat templates for Reactive Orchestration

To be able to send metrics directly to Monasca, all VMs must run the monasca agent and send periodic updates to the monasca endpoint.

Installing the monasca-agent is easy on a new virtual machine using the following command.

    pip install monasca-agent
    
Note that this requires python-dev installed. For ease of use, an image with a pre-installed monasca-agent is available using the name *monasca-agent-ubu14.04*.

The agent needs to be configured to send data to monasca: like everything related to monasca, the agent needs to send a keystone token alongside its metrics. 

The SDK provides a method to easily create a user to be passed to Monasca (see the section on SO configuration), and provides the SO with a username, password and tenant name. These informations need to be passed down to the monasca-agent in each virtual machine of the new service. The utility *monasca-setup* is made for that purpose.

    monasca-setup --username {ks_username} --password {ks_password} --project_name {ks_tenant} --service {service_id} --keystone_url ks_url
    
*ks_username*, *ks_password* and *ks_tenant* are the login information of the user created by the SO through the SDK, *service_id* is a unique id which will be shared by all virtual machines belonging to the same service (generate this id at so initialization time), *ks_url* (example: http://bart.cloudcomplab.ch:35357/v3) is the keystone v3 url.

This is all that is required to create a VM which is able to send data to Monasca. Below an excerpt of a Heat template where these values are provided by Heat parameters:

    rcb_si:
        type: OS::Nova::Server
        properties:
          name: host1
          image: { get_param: image }
          flavor: { get_param: flavor }
          key_name: { get_param: sshkey }
          networks:
            - port : { get_resource: rcb_port_mgmt }
          user_data_format: RAW
          user_data:
            str_replace:
              template: |
                #!/bin/sh
                monasca-setup --username monasca_username --password monasca_password --project_name monasca_tenant --service service_id --keystone_url http://bart.cloudcomplab.ch:35357/v3
              params:
                monasca_username: { get_param: username }
                monasca_password: { get_param: password }
                monasca_tenant: { get_param: tenant }
                service_id: { get_param: service_id }

The template also needs to accept these specific parameters. A full example of a template can be found under *sample_notification_template.yml*.


### SO Configuration and Step by Step example

First the latest version of the SDK needs to be used at it provides the required functions to create notifications.

Adding the notification function to a SO is simple but requires modifications to a number of phases' configuration.

#### Init Phase

Below an example of the init phase of a SO.

    def __init__(self, token, tenant, ready_event):
        super(SOE, self).__init__(token, tenant)
        self.token = token
        self.tenant = tenant
        self.event = ready_event
        f = open(os.path.join(HERE, 'data', 'one-vm.yaml'))
        self.template = f.read()
        f.close()
        self.stack_id = None
        self.deployer = util.get_deployer(self.token,
                                            url_type='public',
                                            tenant_name=self.tenant)

        # BELOW SPECIFIC OBJECTS FOR NOTIFICATION
        self.template_obj = yaml.load(self.template)
        self.mon_user = self.mon_pass = self.mon_id = None
        self.mon_not = dict()
        self.mon_not_ids = []
        self.service = str(uuid.uuid4())
        self.mappings = dict()
        
Here are the explanations point by point of these objects.

* *self.template_obj = yaml.load(self.template)*: this creates a yaml object with the Heat template in memory, for easier modifications of the Heat template in later phases. The orchestrator can only rely on template modifications for application updates.
* *self.mon_user = self.mon_pass = self.mon_id = None*: this initializes the user objects (username, password, id) which will be used in the monasca agent setup. 
* *self.mon_not = dict()*: this creates a dictionary which will store the notifications and associate each notification type with a string used to identify a proper action to take to solve the issue that raised the alarm.
* *self.service = str(uuid.uuid4())*: this creates the random uuid of the service
* *self.mappings = dict()*: this will be used to record name changes in the resources of the template, only useful if specific actions are taken (details explained in the notification phase).

#### Deploy Phase

In this phase alarms are setup, and monasca agents on VMs are configured. Below an example with explanations afterwards.

    def deploy(self, attributes=None):
        if self.stack_id is None:
        
            # NOTIFICATION CONFIGURATION START
            
            # Create Monasca object
            rt = runtime.Monasca(self.token, self.tenant, auth_url=os.environ['DESIGN_URI'])
            
            # Create user
            if self.mon_user is None and self.mon_pass is None:
                self.mon_id, self.mon_user, self.mon_pass = rt.create_user()
                
            # Configure parameters dictionary
            params = dict()
            params['username'] = self.mon_user
            params['password'] = self.mon_pass
            params['tenant'] = self.tenant
            params['service_id'] = self.service
            # NOTIFICATION CONFIGURATION END
            
            self.stack_id = self.deployer.deploy(self.template, self.token, parameters=params)
            
            # NOTIFICATION CONFIGURATION START
            
            # Create alarm and notification
            n_name, n_id = rt.notify('(avg(cpu.user_perc{service=' + self.service + ',hostname=host1}) > 100)', os.getenv('APP_URL') + '/orchestrator/default', runtime.ACTION_UNDETERMINED)
            
            # Record notification and associated action
            self.mon_not[n_name] = "replace_host1"
            self.mon_not_ids.append(n_id)
            LOG.debug("created alarm: " + n_name + " with id: " + n_id + " and action: " + self.mon_not[n_name])
            
            # Fill the mapping
            self.mappings['rcb_si'] = 'rcb_si'  # initial mapping: resource name on heat template is same as expected
            # NOTIFICATION CONFIGURATION END
            
* *rt = runtime.Monasca(self.token, self.tenant, auth_url=os.environ['DESIGN_URI'])*: this initializes the runtime.Monasca object, which is essentially the Monasca controller which will be used throughout the SO's lifecycle to control the notifications and alarms.
* *self.mon_id, self.mon_user, self.mon_pass = rt.create_user()*: this creates a new keystone user (mandatory for monasca-agent setup as described in the previous section), and records its information in related class attributes defined in the init phase.
* *params['service_id'] = self.service* and the other parameters setup in the previous lines: this creates a parameters dictionary to send along the deploy command of the sdk. This will parameterize the Heat template provided that this template is configured to accept these specific parameters.

Note that the stack is deployed with these parameters (*self.deployer.deploy(self.template, self.token, parameters=params)*).

* *n_name, n_id = rt.notify('(avg(cpu.user_perc{service=' + self.service + ',hostname=host1}) > 100)', os.getenv('APP_URL') + '/orchestrator/default', runtime.ACTION_UNDETERMINED)*: this configures the alarm and notification on monasca.
    * *'(avg(cpu.user_perc{service=' + self.service + ',hostname=host1}) > 100)'*: an alarm definition according to the specification in the [monasca-api documentation](https://github.com/openstack/monasca-api/blob/master/docs/monasca-api-spec.md). Note the inclusion of the service id in the alarm definition as well as a specific hostname: this alarm is only triggered based on metrics sent by a monasca agent configured with this service id and running on a host with the *host1* hostname.
    * *os.getenv('APP_URL') + '/orchestrator/default'*: this is the url of the current SO, as reported in the 'APP_URL' environment variable APP_URL.
    * *runtime.ACTION_UNDETERMINED*, the type of alarm to create on Monasca, one from runtime.ACTION_OK, runtime.ACTION_UNDETERMINED, runtime.ACTION_ALARM.
* *self.mon_not[n_name] = "replace_host1"*: this records a mapping between the notification name which is sent by the monasca engine when a motification is triggered and the action to be taken in the notify method.
* *self.mon_not_ids.append(n_id)*: this records the id of the notification in the list of notification ids, and is used when deleting the SO to cleanly delete every created notification.
* *self.mappings['rcb_si'] = 'rcb_si'*: this saves the current name of a given resource in the mappings class attribute, useful if an action renames some resources.

In essence the four main steps are:

* Create a new user
* Parameterize a template with this new user's information and use them to configure the monasca agent
* Create one or more notification using *rt.notify*
* Record the action to be taken when this specific notification is received later in the runtime phase

##### Example Alarms

* *avg(cpu.user_perc{service=' + self.service + ',hostname=host1}) > 100)*, with action type *UNDETERMINED*: this alarm gives an OK when the CPU usage is less than 100%, which should be all the time. The usefulness of this alarm is to trigger a notification when it goes from OK to UNDETERMINED: this happens when no metrics are received by Monasca for a specific alarm during a minimum period of 180 seconds.
* *avg(cpu.user_perc{service=' + self.service + ',hostname=host1}) > 50)*, with action type *ALARM*: this is a more classic alarm, triggering a notification when the cpu usage percentage reaches 50%.

#### Notification action

The notify method is called when a POST using the action type 'notify' is received by a SO. The notification below has only one possible action, and uses Heat to replace the host1 VM which has disappeared when this alarm is triggered. 

This needs to be done by creating a new resource following the same configuration as Heat does not understand that a resource has disappeared as it does not perform health management by itself. Here is an example of a notify method.

    def notify(self, entity, attributes, extras):
        super(SOE, self).notify(entity, attributes, extras)
        
        # Retrieve the alarm_name from the OCCI attributes of the request
        try:
            alarm_name = attributes['notification.alarm_name']
        except KeyError:
            raise ValueError("Notify action missing notification.alarm_name OCCI attribute")

        # Check if the alarm name is within the keys of the mon_not dictionary setup in the deploy phase
        if alarm_name in self.mon_not:
            
            # If the name is 'replace_host1', then realize the action below
            if self.mon_not[alarm_name] == 'replace_host1':
                
                # Action: Create a new VM with hostname host1 as this alarm is triggered when the host died
                
                # Find the name of the resource in the current version of the template
                old_res_name = self.mappings['rcb_si']
                # This switches the resource names
                if old_res_name != 'rcb_si':
                    new_res_name = 'rcb_si'
                    self.mappings['rcb_si'] = 'rcb_si'
                else:
                    new_res_name = 'rcb_si_1'
                    self.mappings['rcb_si'] = 'rcb_si_1'
                
                # Extract the resource from the template object
                old_res = self.template_obj.get('resources').pop(old_res_name)
                # Reinsert it with different key
                self.template_obj.get('resources')[new_res_name] = old_res

                # Dump the template as a string ready for heat
                template_updated = yaml.dump(self.template_obj)

                if self.stack_id is not None:
                    # Note tack needs to be parameterized same as in deploy
                    params = {}
                    params['username'] = self.mon_user
                    params['password'] = self.mon_pass
                    params['tenant'] = self.tenant
                    params['service_id'] = self.service
                    self.deployer.update(self.stack_id, template_updated, self.token, parameters=params)

The main steps common for any notifications are:

* *alarm_name = attributes['notification.alarm_name']*: retrieves the notification name from the attributes of the request
* *if alarm_name in self.mon_not:*: checks that an action has been configured for this alarm

After that step, the action to take is specific to each SO implementation for each specific alarm. The action described in the example takes place if the name *replace_host1* is sent in the attributes of the notify call. 

The goal of the action is to create a new VM of type rcb_si, as the triggered alarm is related to the termination of that specific VM. Using Heat, a workaround is required: remove resource rcb_si from the template, replacing it with an identical resource rcb_si_1, linked to the same Neutron port. If rcb_si_1 crashes afterwards, the notification deletes it from the template and replace it with a rcb_si resource again.

#### Dispose Phase

During this phase, besides removing the heat template, the SO also needs to delete the user created previously, as well as any alarms.

    rt = runtime.Monasca(self.token, self.tenant_name, auth_url=os.environ['DESIGN_URI'])
    # Delete the user
    rt.delete_user(self.mon_id)
    # Delete each created alarm and notification
    for n_id in self.mon_not_ids:
        rt.dispose_monasca(n_id)

This excerpt is generic and can be used in any SO.