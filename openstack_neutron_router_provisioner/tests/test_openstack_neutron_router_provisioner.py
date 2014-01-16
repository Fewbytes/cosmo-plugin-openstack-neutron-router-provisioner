#!/usr/bin/env python
# vim: ts=4 sw=4 et
import json
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
        # print(json.dumps(sorted(dir(self.neutron_client)), indent=4))
        self.name_prefix = 'cosmo_test_neutron_{0}_'.format(''.join(
            [random.choice(string.ascii_uppercase + string.digits) for i in range(RANDOM_LEN)]
        ))

    def _list_all_objs(self, obj_type_single):
        obj_type_plural = obj_type_single + 's'
        for obj in getattr(self.neutron_client, 'list_' + obj_type_plural)()[obj_type_plural]:
            yield obj

    def _list_objs(self, obj_type_single):
        for obj in self._list_all_objs(obj_type_single):
            if obj['name'].startswith(self.name_prefix):
                yield obj

    def tearDown(self):
        self.logger.info("tearDown called")
        # Disconnect ports from routers
        my_net_ids = [net['id'] for net in self._list_objs('network')]
        for port in self._list_all_objs('port'):
            if port.get('device_owner') == 'network:router_interface' and port.get('network_id') in my_net_ids:
                self.neutron_client.remove_interface_router(port['device_id'], {'port_id': port['id']})

        # Cleanup all neutron.list_XXX() objects with names starting with self.name_prefix
        for obj_type_single in 'router', 'network', 'subnet':
            for obj in self._list_objs(obj_type_single):
                self.logger.info("Deleting {0} {1}".format(obj_type_single, obj.get('name', obj['id'])))
                getattr(self.neutron_client, 'delete_' + obj_type_single)(obj['id'])

    def test_router_provision_and_terminate(self):
        name = self.name_prefix + 'rtr_prov_term'
        router = {
            'name': name,
        }

        tasks.provision(name, router)
        router = tasks._get_router_by_name(self.neutron_client, name)
        self.assertIsNotNone(router)
        self.assertIsNone(router['external_gateway_info'])  # must not have gateway

        tasks.terminate(router)
        router = tasks._get_router_by_name(self.neutron_client, name)
        self.assertIsNone(router)

    def find_external_net(self):
        nets = self.neutron_client.list_networks()['networks']
        for net in nets:
            if net.get('router:external'):
                return net
        return None

    def _test_router_with_gateway(self, enable_snat):

        ext_net = self.find_external_net()
        if not ext_net:
            raise RuntimeError("Failed to find external network for router gateway test")

        name = self.name_prefix + 'rtr_ext_gw_snat_'
        name += ['dis', 'ena'][enable_snat]
        router = {
            'name': name,
            'gateway': ext_net['name'],
        }

        tasks.provision(name, router, enable_snat)
        rtr = tasks._get_router_by_name(self.neutron_client, name)
        self.assertIsNotNone(rtr)
        rtr = tasks._get_router_by_name(self.neutron_client, router['name'])
        self.assertIsNotNone(rtr['external_gateway_info'])
        self.assertEquals(rtr['external_gateway_info']['network_id'], ext_net['id'])
        self.assertEquals(rtr['external_gateway_info']['enable_snat'], enable_snat)

    def test_router_with_gateway_snat_enabled(self):
        self._test_router_with_gateway(True)

    def test_router_with_gateway_snat_disabled(self):
        self._test_router_with_gateway(False)

    def _test_connect_gateway(self, enable_snat):
        ext_net = self.find_external_net()
        if not ext_net:
            raise RuntimeError("Failed to find external network for router gateway test")

        name = self.name_prefix + 'rtr_cn_egw_snat_'
        name += ['dis', 'ena'][enable_snat]

        router = {
            'name': name,
        }

        tasks.provision(name, router)
        rtr = tasks._get_router_by_name(self.neutron_client, name)
        self.assertIsNotNone(rtr)
        self.assertIsNone(rtr['external_gateway_info'])
        tasks.connect_gateway(router, ext_net, enable_snat=enable_snat)
        rtr = tasks._get_router_by_name(self.neutron_client, name)
        self.assertIsNotNone(rtr['external_gateway_info'])
        self.assertEquals(rtr['external_gateway_info']['network_id'], ext_net['id'])
        self.assertEquals(rtr['external_gateway_info']['enable_snat'], enable_snat)

    def test_connect_gateway_snat_enabled(self):
        self._test_connect_gateway(True)

    def test_connect_gateway_snat_disabled(self):
        self._test_connect_gateway(False)

    def _network_has_port_in_router(self, net, rtr):
        for port in self._list_all_objs('port'):
            if port.get('device_owner') == 'network:router_interface' and \
                    port.get('device_id') == rtr['id'] and \
                    port.get('network_id') == net['id']:
                return True
        return False

    def test_connect_disconnect_subnet(self):

        # Router
        name = self.name_prefix + 'rtr_subn'
        router = {
            'name': name,
        }

        tasks.provision(name, router)
        rtr = tasks._get_router_by_name(self.neutron_client, name)

        # Net
        net = self.neutron_client.create_network({
            'network': {
                'name': self.name_prefix + 'net_subn'
            }
        })['network']

        # Subnet
        name = self.name_prefix + 'subnet_subn'
        subnet = self.neutron_client.create_subnet({
            'subnet': {
                'network_id': net['id'],
                'name': name,
                'ip_version': 4,
                'cidr': '192.168.1.0/24',
            }
        })['subnet']

        # Connect router and subnet
        tasks.connect_subnet({'subnet': subnet}, {'router': rtr})
        self.assertTrue(self._network_has_port_in_router(net, rtr))

        # Disconnect
        tasks.disconnect_subnet(rtr, subnet)
        self.assertFalse(self._network_has_port_in_router(net, rtr))


if __name__ == '__main__':
    unittest.main()
