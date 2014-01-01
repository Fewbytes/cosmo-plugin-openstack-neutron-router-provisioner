# vim: ts=4 sw=4 et
import setuptools

COSMO_CELERY_VERSION = "0.3"
COSMO_CELERY_BRANCH = "develop"
COSMO_CELERY = "https://github.com/CloudifySource/cosmo-celery-common/tarball/{0}".format(COSMO_CELERY_BRANCH)


setuptools.setup(
    zip_safe=True,
    name='cosmo-plugin-openstack-neutron-router-provisioner',
    version='0.1',
    author='Ilya Sher',
    author_email='ilya@fewbytes.com',
    packages=['openstack_neutron_router_provisioner'],
    license='LICENSE',
    description='Plugin for provisioning OpensTack Neutron security group',
    install_requires=[
        "celery",
        "cosmo-celery-common",
        "mock",
        "python-keystoneclient",
        "python-neutronclient",
    ],
    dependency_links=["{0}#egg=cosmo-celery-common-{1}".format(COSMO_CELERY, COSMO_CELERY_VERSION),]
)
