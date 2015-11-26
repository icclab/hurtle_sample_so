# Testing SO without deploying it using CC
## Installation Guide

The following instructions have been verified with the docker image centos:7.

	yum install epel-release -y 
	yum install gcc python-devel python-pip git python-virtualenv -y 
	cd /opt 
	virtualenv /opt/venv/hurtle/so 
	source /opt/venv/hurtle/so/bin/activate 
	git clone https://github.com/icclab/hurtle_cc_sdk.git
	git clone https://github.com/icclab/hurtle_sample_so.git
	git clone https://github.com/icclab/hurtle_sm.git
	cd hurtle_sm ; 	python setup.py install ; cd ..
	cd hurtle_cc_sdk ; python setup.py install ; cd ..


Start the SO locally with:

	cd hurtle_sample_so
	OPENSHIFT_PYTHON_DIR=/opt/venv/hurtle/so OPENSHIFT_REPO_DIR=$PWD python ./wsgi/application
	
Optionally you can also set the DESIGN_URI if your OpenStack install is not local.

In a new terminal do get a token from keystone (token must belong to a user which has the admin role for the tenant):

    $ keystone token-get
    $ export KID='...'
    $ export TENANT='...'

You can now visit the SO interface [here](http://localhost:8051/orchestrator/default).

## Sample requests

Initialize the SO:

    $ curl -v -X PUT http://localhost:8051/orchestrator/default \
          -H 'Content-Type: text/occi' \
          -H 'Category: orchestrator; scheme="http://schemas.mobile-cloud-networking.eu/occi/service#"' \
          -H 'X-Auth-Token: '$KID \
          -H 'X-Tenant-Name: '$TENANT

Get state of the SO + service instance:

    $ curl -v -X GET http://localhost:8051/orchestrator/default \
          -H 'X-Auth-Token: '$KID \
          -H 'X-Tenant-Name: '$TENANT

Trigger deployment of the service instance:

    $ curl -v -X POST http://localhost:8051/orchestrator/default?action=deploy \
          -H 'Content-Type: text/occi' \
          -H 'Category: deploy; scheme="http://schemas.mobile-cloud-networking.eu/occi/service#"' \
          -H 'X-Auth-Token: '$KID \
          -H 'X-Tenant-Name: '$TENANT

Trigger provisioning of the service instance:

    $ curl -v -X POST http://localhost:8051/orchestrator/default?action=provision \
          -H 'Content-Type: text/occi' \
          -H 'Category: provision; scheme="http://schemas.mobile-cloud-networking.eu/occi/service#"' \
          -H 'X-Auth-Token: '$KID \
          -H 'X-Tenant-Name: '$TENANT

Trigger update on SO + service instance:

    $ curl -v -X POST http://localhost:8051/orchestrator/default \
          -H 'Content-Type: text/occi' \
          -H 'X-Auth-Token: '$KID \
          -H 'X-Tenant-Name: '$TENANT \
          -H 'X-OCCI-Attribute: occi.epc.attr_1="foo"'

Trigger delete of SO + service instance:

    $ curl -v -X DELETE http://localhost:8051/orchestrator/default \
          -H 'X-Auth-Token: '$KID \
          -H 'X-Tenant-Name: '$TENANT

#@ Supported by

<div align="center" >
<a href='http://blog.zhaw.ch/icclab'>
<img src="https://raw.githubusercontent.com/icclab/hurtle/master/docs/figs/mcn_logo.png" title="mobile cloud networking" width=400px>
</a>
</div>
