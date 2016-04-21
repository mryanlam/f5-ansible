#!/usr/bin/python

# Ansible module to manage BIG-IP devices
#
# This module covers the ResourceRecord interfaces described in the iControl
# Management documentation.
#
# More information can be found here
#
#    https://devcentral.f5.com/wiki/iControl.Management.ashx
#

DOCUMENTATION = '''
---
module: bigip_zone
short_description: Manage resource records on a BIG-IP
description:
   - Manage resource records on a BIG-IP
version_added: "1.8"
options:
  username:
    description:
      - The username used to authenticate with
    required: true
    default: admin
  password:
    description:
      - The password used to authenticate with
    required: true
    default: admin
  hostname:
    description:
      - BIG-IP host to connect to
    required: true
    default: localhost
  view_name:
    description:
      - The name of the view
    required: true
  view_order:
    description:
      - The order of the view within the named.conf file. 0 = first in zone.
      0xffffffff means to move the view to last. Any other number will move the
      view to that position, and bump up any view(s) by one (if necessary).
    default: 0
  options:
    description:
      - A sequence of options for the view
  zone_names:
    description:
      - A sequence of zones in this view
    required: true
  state:
    description:
      - Whether the record should exist.  When C(absent), removes
        the record.
    required: false
    default: present
    choices: [ "present", "absent" ]
notes:
   - Requires the bigsuds Python package on the remote host. This is as easy as
     pip install bigsuds

requirements: [ "bigsuds", "distutils" ]
author: Tim Rupp <t.rupp@f5.com>
'''

EXAMPLES = """

- name: Add a view, named "internal", to organization.com zone
  local_action:
      module: bigip_view
      username: 'admin'
      password: 'admin'
      hostname: 'bigip.organization.com'
      zone_names:
          - 'organization.com'
      state: 'present'
      options:
          - domain_name: elliot.organization.com
          ip_address: 10.1.1.1
"""

import sys
import re
from distutils.version import StrictVersion

try:
    import bigsuds
except ImportError:
	bigsuds_found = False
else:
	bigsuds_found = True

VERSION_PATTERN='BIG-IP_v(?P<version>\d+\.\d+\.\d+)'

class ViewZoneException(Exception):
	  pass

class ViewZone(object):
    REQUIRED_BIGIP_VERSION='9.0.3'

    def __init__(self, module):
        new_zones = []

        self.module = module

        self.username = module.params['username']
        self.password = module.params['password']
        self.hostname = module.params['hostname']
        self.view_name = module.params['view_name']
        self.zone_name = module.params['zone_name']
        self.zone_type = module.params['zone_type'].lower()
        self.zone_file = module.params['zone_file']
        self.options = module.params['options']
        self.text = module.params['text']

        if not self.zone_name.endswith('.'):
            self.zone_name += '.'

        self.client = bigsuds.BIGIP(
            hostname=self.hostname,
            username=self.username,
            password=self.password,
            debug=True
        )

        # Do some checking of things
        self.check_version()
       
    def get_zone_type(self):
        zone_type_maps = {
            'unset': 'UNSET',    # Not yet initialized
            'master': 'MASTER',   # A master zone
            'slave': 'SLAVE',    # A slave zone
            'stub': 'STUB',     # A stub zone
            'forward': 'FORWARD',  # A forward zone
            'hint': 'HINT'      # A hint zone, "."
        }

        if self.zone_type in zone_type_maps:
            return zone_type_maps[self.zone_type]
        else:
            raise ViewZoneException('Specified zone_type does not exist')

    def check_version(self):
        response = self.client.System.SystemInfo.get_version()
        match = re.search(VERSION_PATTERN, response)
        version = match.group('version')

        v1 = StrictVersion(version)
        v2 = StrictVersion(self.REQUIRED_BIGIP_VERSION)

        if v1 < v2:
            raise ViewException('The BIG-IP version %s does not support this feature' % version)

    def zone_exists(self):
        view_zone = [{
            'view_name': self.view_name,
            'zone_name': self.zone_name,
        }]

        response = self.client.Management.Zone.zone_exist(
            view_zones=view_zone
        )

        return response

    def create_zone(self):
        view_zone = [{
            'view_name': self.view_name,
            'zone_name': self.zone_name,
            'zone_type': self.get_zone_type(),
            'zone_file': self.zone_file,
            'option_seq': self.options
        }]

        text = [[
           self.text
        ]]

        #try:
        response = self.client.Management.Zone.add_zone_text(
            zone_records=view_zone,
            text=text,
            sync_ptrs=[1]
        )
        #except Exception, e:
        #    raise ViewException(str(e))

    def delete_zone(self):
        view_zone = [{
            'view_name': self.view_name,
            'zone_name': self.zone_name
        }]

        #try:
        response = self.client.Management.Zone.delete_zone(
            view_zones=view_zone
        )
        #except Exception, e:
        #    raise ViewException(str(e))

def main():
    module = AnsibleModule(
        argument_spec = dict(
            username=dict(default='admin'),
            password=dict(default='admin'),
            hostname=dict(default='localhost'),
            view_name=dict(default='external'),
            zone_name=dict(required=True),
            zone_type=dict(default='master'),
            options=dict(required=False, type='list'),
            zone_file=dict(default=None),
            text=dict(default=None),
            state=dict(default="present", choices=["absent", "present"]),
        )
    )

    state = module.params["state"]
    zone_file = module.params['zone_file']

    if not bigsuds_found:
        module.fail_json(msg="The python bigsuds module is required")

    #try:
    view_zone = ViewZone(module)

    if state == "present":
        if not zone_file:
            raise ViewZoneException('A zone_file must be specified')

        if view_zone.zone_exists():
            changed = False
        else:
            view_zone.create_zone()
            changed = True
    elif state == "absent":
        view_zone.delete_zone()
        changed = True
    #except Exception, e:
    #    module.fail_json(msg=str(e))

    module.exit_json(changed=changed)

from ansible.module_utils.basic import *
main()