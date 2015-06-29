# Hesiod + Route53

This is a system to manage UNIX users, groups, and ssh keys across an entire
EC2 fleet using only DNS. This replaces more traditional services such as LDAP
and Kerberos with Route53, which is much easier to manage.

User and group management is done with
[Hesiod](https://en.wikipedia.org/wiki/Hesiod_(name_service)). This repository
includes a synchronization tool that configrues a Route53 domain with the
necssary DNS entries based on a YAML file.

For ssh keys, an `AuthorizedKeysCommand` helper is included so that ssh public
keys can also be stored in DNS. When an ssh client tries to connect using
public key authentication, the helper will query DNS for the proper ssh keys,
which it then provides to the OpenSSH daemon. This replaces individual
`authorized_keys` files for each user.

## Route53 Sync

### Installation

```
virtualenv env
. env/bin/activate
pip install /path/to/hesiod53
```

### Usage

    hesiod53 USER_FILE

Run `hesiod53 -h` for full usage instructions.

An example user configuration file is in
[`example_users.yml`](example_users.yml). Ensure you configure your Route53
zone and domain correctly.

## Hesiod Setup

1. Install Hesiod. On Debian-like systems, this is the `hesiod` package.
2. Configure `/etc/hesiod.conf`. An example hesiod configuration file is in
   [`example_hesiod.conf`](example_hesiod.conf). Set lhs and rhs (left-hand
   side and right-hand side) so that the concatenation of the two strings is
   the domain you used in your user configuration file. Ensure that both lhs
   and rhs start with a dot.
3. Configure `/etc/nsswitch.conf`. For the `passwd` and `group` lines, add
   hesiod, so that your configuration looks similar to the following:

        passwd:         compat hesiod
        group:          compat hesiod
        shadow:         compat

At this point, if you setup everything properly, then you should be able to see
user information for users in DNS. `getent passwd USER` will return a
passwd-like line showing the user information if everything is configured
correctly.

### Sudo Setup (Optional)

If you want your users to be able to use sudo, then it is recommended to add
users to groups and then grant sudo access to a group. Note that you have to
allow sudo access without a password since users do not have passwords.

Example sudo line to give group `wheel` sudo access:

    %wheel ALL=(ALL) NOPASSWD:ALL

## SSH Key Helper

### Installation

The path of the ssh helper is critical for security. ssh will reject the use of
any binary where the ownership is writable by anyone but root or any parent
directory is writable by anyone but root. Thus, it is suggested to install to a
path such as `/etc/ssh/authkeys.py`.

In addition, the ssh helper depends on
[dnspython](pypi.python.org/pypi/dnspython). You can use the installation
method for the sync utility with a virtualenv, or you can install the
`python-dnspython` package on Debian-like systems.

### Configuration

Ensure that `/etc/hesiod.conf` is populated with your hesiod information. See
the Hesiod setup section, above.

Then, in `sshd_config`, put the following options

    AuthorizedKeysCommand /path/to/ssh/command.py
    AuthorizedKeysCommandUser nobody

This will tell the ssh daemon to run the command to look up keys for a given
user *after* checking for any local keys by running the command as the user
`nobody`.

### PAM Configuration

With most default PAM setups, user authentication will not work if there is not
a shadow entry, which is not present if you are only using ssh key authentication.

To make user authentication work, ensure that the `broken_shadow` option is
passed to `pam_unix.so` in your PAM account configuration. In Debian-like
systems, this can be found in `/etc/pam.d/common-account`.

Example:

    account [success=1 new_authtok_reqd=done default=ignore] pam_unix.so broken_shadow
