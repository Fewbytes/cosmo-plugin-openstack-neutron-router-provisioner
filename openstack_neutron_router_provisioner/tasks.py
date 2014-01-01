# vim: ts=4 sw=4 et

# Standard
import json
import os

# Celery
from celery import task

# OpenStack
import keystoneclient.v2_0.client as ksclient
from neutronclient.neutron import client

# Cosmo
from cosmo.events import send_event

@task
def provision(__cloudify_id, router, **kwargs):
    neutron_client = _init_client()
    if _get_router_by_name(neutron_client, router['name']):
        raise RuntimeError("Can not provision router with name '{0}' because router with such name already exists"
                           .format(router['name']))

    rtr_dict = {
        'name': router['name'],
    }

    if 'gateway' in router:
        rtr_dict['external_gateway_info'] = {
            'network_id': _get_network_by_name(neutron_client, router['gateway'])['id']
        }

    rtr = neutron_client.create_router({'router': rtr_dict})['router']

    send_event(__cloudify_id, "rtr-" + router['name'], "router status", "state", "running")


@task
def add_gateway(router, network, **kwargs):
    neutron_client = _init_client()
    rtr = _get_router_by_name(neutron_client, router['name'])
    net = _get_network_by_name(neutron_client, network['name'])
    neutron_client.add_gateway_router(rtr['id'], {'network_id': net['id']})
    

@task
def terminate(router, **kwargs):
    neutron_client = _init_client()
    rtr = _get_router_by_name(neutron_client, router['name'])
    neutron_client.delete_router(rtr['id'])


# TODO: cache the token, cache client
def _init_client():
    config_path = os.getenv('NEUTRON_CONFIG_PATH', os.path.expanduser('~/neutron_config.json'))
    with open(config_path) as f:
        neutron_config = json.loads(f.read())

    keystone_client = _init_keystone_client()

    neutron_client = client.Client('2.0', endpoint_url=neutron_config['url'], token=keystone_client.auth_token)
    neutron_client.format = 'json'
    return neutron_client


def _init_keystone_client():
    config_path = os.getenv('KEYSTONE_CONFIG_PATH', os.path.expanduser('~/keystone_config.json'))
    with open(config_path) as f:
        cfg = json.loads(f.read())
    # Not the same config as nova client. Same parameters, different names.
    args = {field: cfg[field] for field in ('username', 'password', 'tenant_name', 'auth_url')}
    return ksclient.Client(**args)


def _get_router_by_name(neutron_client, name):
    # TODO: check whether neutron_client can get routers only named `name`
    matching_routers = neutron_client.list_routers(name=name)['routers']

    if len(matching_routers) == 0:
        return None
    if len(matching_routers) == 1:
        return matching_routers[0]
    raise RuntimeError("Lookup of router by name failed. There are {0} routers named '{1}'"
                       .format(len(matching_routers), name))


def _get_router_by_name_or_fail(neutron_client, name):
    router = _get_router_by_name(neutron_client, name)
    if router:
        return router
    raise ValueError("Lookup of router by name failed. Could not find a router with name {0}".format(name))

def _get_network_by_name(neutron_client, name):
    # TODO: check whether neutron_client can get networks only named `name`
    matching_networks = neutron_client.list_networks(name=name)['networks']

    if len(matching_networks) == 0:
        return None
    if len(matching_networks) == 1:
        return matching_networks[0]
    raise RuntimeError("Lookup of network by name failed. There are {0} networks named '{1}'"
                       .format(len(matching_networks), name))


if __name__ == '__main__':
    neutron_client = _init_client()
    json.dumps(neutron_client.list_routers(), indent=4, sort_keys=True)
