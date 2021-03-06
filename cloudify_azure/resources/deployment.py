# #######
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json

from cloudify import exceptions as cfy_exc
from cloudify.decorators import operation

from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resource.resources.models import DeploymentMode


class Deployment(object):

    def __init__(self, logger, credentials, name, timeout=None):
        self.resource_group = name
        self.logger = logger
        self.timeout = timeout
        self.credentials = ServicePrincipalCredentials(
            client_id=str(credentials['client_id']),
            secret=str(credentials['client_secret']),
            tenant=str(credentials['tenant_id'])
        )
        self.client = ResourceManagementClient(
            self.credentials, str(credentials['subscription_id']))

        self.logger.info("Use subscription: {}"
                         .format(credentials['subscription_id']))

    def create(self, template, params, location):
        """Deploy the template to a resource group."""
        self.logger.info("Client resource...")
        self.client.resource_groups.create_or_update(
            self.resource_group,
            {
                'location': location
            }
        )

        self.logger.info("Create deployment...")

        parameters = {str(k): {'value': str(v)} for k, v in params.items()}

        if isinstance(template, basestring):
            template = json.loads(template)

        deployment_properties = {
            'mode': DeploymentMode.incremental,
            'template': template,
            'parameters': parameters
        }

        deployment_async_operation = self.client.deployments.create_or_update(
            self.resource_group,  # resource group name
            self.resource_group,  # deployment name
            deployment_properties
        )
        self.logger.info("Wait deployment...Timeout: {}"
                         .format(repr(self.timeout)))
        deployment_async_operation.wait(timeout=self.timeout)

    def delete(self):
        """Destroy the given resource group"""
        self.logger.info("Delete resource groups...")
        deployment_async_operation = self.client.resource_groups.delete(
            self.resource_group
        )
        self.logger.info("Wait delete deployment...Timeout: {}"
                         .format(repr(self.timeout)))
        deployment_async_operation.wait(timeout=self.timeout)


@operation
def create(ctx, **kwargs):
    properties = {}
    properties.update(ctx.node.properties)
    properties.update(kwargs)
    ctx.logger.info("Create: {}".format(repr(properties['name'])))
    deployment = Deployment(ctx.logger, properties['azure_config'],
                            properties['name'],
                            timeout=properties.get('timeout'))

    # load template
    template = properties.get('template')
    if not template and properties.get('template_file'):
        ctx.logger.info("Will be used {} as template"
                        .format(repr(properties['template_file'])))
        template = ctx.get_resource(properties['template_file'])

    if not template:
        raise cfy_exc.NonRecoverableError(
            "Template does not defined."
        )

    # create deployment
    deployment.create(template=template,
                      params=properties.get('params', {}),
                      location=properties['location'])
    ctx.instance.runtime_properties['resource_id'] = properties['name']


@operation
def delete(ctx, **kwargs):
    properties = {}
    properties.update(ctx.node.properties)
    properties.update(kwargs)
    ctx.logger.info("Delete: {}".format(
        repr(ctx.instance.runtime_properties['resource_id'])
    ))
    deployment = Deployment(ctx.logger, properties['azure_config'],
                            ctx.instance.runtime_properties['resource_id'],
                            timeout=properties.get('timeout'))
    deployment.delete()
