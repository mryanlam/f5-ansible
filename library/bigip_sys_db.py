#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: bigip_sys_db
short_description: Manage BIG-IP system database variables
description:
   - Manage BIG-IP system database variables
version_added: "2.2"
options:
  server:
    description:
      - BIG-IP host
    required: true
  server_port:
    description:
      - BIG-IP host port
    required: false
    default: 443
  key:
    description:
      - The database variable to manipulate
    required: true
  password:
    description:
      - BIG-IP password
    required: true
  state:
    description:
      - The state of the variable on the system. When C(present), guarantees
        that an existing variable is set to C(value). When C(reset) sets the
        variable back to the default value. At least one of value and state
        C(reset) are required.
    required: false
    default: present
    choices:
      - present
      - reset
  user:
    description:
      - BIG-IP username
    required: true
    aliases:
      - username
  value:
    description:
      - The value to set the key to. At least one of value and state C(reset)
        are required.
    required: false
  validate_certs:
    description:
      - If C(no), SSL certificates will not be validated. This should only be
        used on personally controlled sites using self-signed certificates.
    required: false
    default: true
notes:
  - Requires the bigsuds Python package on the host if using the iControl
    interface. This is as easy as pip install bigsuds
requirements:
  - f5-sdk
author:
    - Tim Rupp (@caphrim007)
'''

EXAMPLES = '''
- name: Set the boot.quiet DB variable on the BIG-IP
  bigip_sys_db:
      user: "admin"
      password: "secret"
      server: "lb.mydomain.com"
      key: "boot.quiet"
      value: "disable"
  delegate_to: localhost

- name: Disable the initial setup screen
  bigip_sys_db:
      user: "admin"
      password: "secret"
      server: "lb.mydomain.com"
      key: "setup.run"
      value: "false"
  delegate_to: localhost

- name: Reset the initial setup screen
  bigip_sys_db:
      user: "admin"
      password: "secret"
      server: "lb.mydomain.com"
      key: "setup.run"
      state: "reset"
  delegate_to: localhost
'''

RETURN = '''
'''

try:
    from f5.bigip import ManagementRoot
    from f5.sdk_exception import F5SDKError
    HAS_F5SDK = True
except:
    HAS_F5SDK = False


class BigIpSysDb():
    def __init__(self, *args, **kwargs):
        if not HAS_F5SDK:
            raise F5SDKError("The python f5-sdk module is required")

        self.params = kwargs
        self.api = ManagementRoot(kwargs['server'],
                                  kwargs['user'],
                                  kwargs['password'],
                                  port=kwargs['server_port'])

    def flush(self):
        result = dict()
        state = self.params['state']
        value = self.params['value']

        if not state == 'reset' and not value:
            raise F5SDKError(
                "When resetting a key, a value is not supported"
            )

        current = self.read()

        if self.params['check_mode']:
            if value == current:
                changed = False
            else:
                changed = True
        else:
            if state == "present":
                changed = self.present()
            elif state == "reset":
                changed = self.reset()
            current = self.read()
            result.update(current)

        result.update(dict(changed=changed))
        return result

    def read(self):
        dbs = self.api.tm.sys.dbs.db.load(
            name=self.params['key']
        )
        return dbs

    def present(self):
        current = self.read()

        if current['value'] == self.params['value']:
            return False

        current.update(self.params['value'])
        current.refresh()

        if current['value'] == self.params['value']:
            raise F5SDKError(
                "Failed to set the DB variable"
            )
        return True

    def reset(self):
        current = self.read()

        default = current['defaultValue']
        if current['value'] == default:
            return False

        current['value'] = default
        current.update()
        return True


def main():
    argument_spec = f5_argument_spec()

    meta_args = dict(
        key=dict(required=True),
        state=dict(default='present', choices=['present', 'reset']),
        value=dict(required=False, default=None)
    )
    argument_spec.update(meta_args)

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True
    )

    try:
        obj = BigIpSysDb(**module.params)
        result = obj.flush()

        module.exit_json(**result)
    except F5SDKError, e:
        module.fail_json(msg=str(e))

from ansible.module_utils.basic import *
from ansible.module_utils.f5 import *

if __name__ == '__main__':
    main()