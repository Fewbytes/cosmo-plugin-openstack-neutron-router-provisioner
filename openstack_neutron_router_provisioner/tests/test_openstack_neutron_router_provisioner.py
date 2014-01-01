#!/usr/bin/env python
# vim: ts=4 sw=4 et
import logging
import mock
import random
import string
import unittest

import cosmo.events
cosmo.events.send_event = mock.Mock()
import openstack_neutron_router_provisioner.tasks as tasks

RANDOM_LEN = 3  # cosmo_test_neutron_XXX_something


class OpenstackNeutronRouterProvisionerTestCase(unittest.TestCase):

    def setUp(self):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.level = logging.DEBUG
        self.logger.info("setUp called")
        self.neutron_client = tasks._init_client()
        self.name_prefix = 'cosmo_test_neutron_{0}_'.format(''.join(
            [random.choice(string.ascii_uppercase + string.digits) for i in range(RANDOM_LEN)]
        ))

    def tearDown(self):
        for router in self.neutron_client.list_routers()['routers']:
            if router['name'].startswith(self.name_prefix):
                self.neutron_client.delete_router(router['id'])

    def test_router_provision_and_terminate(self):
        name = self.name_prefix + 'rtr1'
        router = {
            'name': name,
        }

        tasks.provision(name, router)
        router = tasks._get_router_by_name(self.neutron_client, name)
        self.assertIsNotNone(router)

        tasks.terminate(router)
        router = tasks._get_router_by_name(self.neutron_client, name)
        self.assertIsNone(router)

    def find_external_net(self):
        nets = self.neutron_client.list_networks()['networks']
        for net in nets:
            if net.get('router:external'):
                return net
        return None


    def test_add_gateway(self):

        ext_net = self.find_external_net()
        if not ext_net:
            raise RuntimeError("Failed to find external network for router gateway test")

        # Step 2: test gateway connection
        name = self.name_prefix + 'rtr2'
        router = {
            'name': name,
        }

        tasks.provision(name, router)
        router = tasks._get_router_by_name(self.neutron_client, name)
        self.assertIsNotNone(router)

        tasks.add_gateway(router, ext_net)
        rtr = tasks._get_router_by_name(self.neutron_client, router['name'])
        self.assertEquals(rtr['external_gateway_info']['network_id'], ext_net['id'])


if __name__ == '__main__':
    unittest.main()
