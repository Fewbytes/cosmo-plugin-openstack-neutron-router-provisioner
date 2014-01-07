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


# Untested and unused for now
@task
def connect_gateway(router, network, **kwargs):
    neutron_client = _init_client()
    rtr = _get_router_by_name(neutron_client, router['name'])
    net = _get_network_by_name(neutron_client, network['name'])
    neutron_client.add_gateway_router(rtr['id'], {'network_id': net['id']})
    
@task
def connect_subnet(router, subnet, **kwargs):
    neutron_client = _init_client()
    rtr = _get_router_by_name(neutron_client, router['name'])
    subnet = _get_subnet_by_name(neutron_client, subnet['name'])
    # print(dir(neutron_client))
    neutron_client.add_interface_router(rtr['id'], {'subnet_id': subnet['id']})

@task
def disconnect_subnet(router, subnet, **kwargs):
    neutron_client = _init_client()
    rtr = _get_router_by_name(neutron_client, router['name'])
    subnet = _get_subnet_by_name(neutron_client, subnet['name'])
    neutron_client.remove_interface_router(rtr['id'], {'subnet_id': subnet['id']})


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

def _make_get_obj_by_name(single):

    plural = single + 's'
    def f(neutron_client, name):
        matching_objs = getattr(neutron_client, 'list_'+ plural)(name=name)[plural]

        if len(matching_objs) == 0:
            return None
        if len(matching_objs) == 1:
            return matching_objs[0]
        raise RuntimeError("Lookup of {0} by name failed. There are {2} {1} named '{3}'"
                           .format(single, plural, len(matching_objs), name))

    f.func_name = '_get_' + single + '_by_name'
    return f


_get_router_by_name = _make_get_obj_by_name('router')
_get_network_by_name = _make_get_obj_by_name('network')
_get_subnet_by_name = _make_get_obj_by_name('subnet')

if __name__ == '__main__':
    neutron_client = _init_client()
    json.dumps(neutron_client.list_routers(), indent=4, sort_keys=True)
