#!/usr/bin/env python

from boto.route53.record import ResourceRecordSets
from boto.route53.status import Status
import boto.route53 as r53

from collections import namedtuple
import argparse
import time
import yaml

# a DNS record for hesiod
# fqdn should include the trailing .
# value should contain the value without quotes
DNSRecord = namedtuple("DNSRecord", "fqdn value")

# A UNIX group
class Group(object):
    def __init__(self, name, gid):
        if not name:
            raise Exception("Group name must be provided.")
        if not gid:
            raise Exception("Group ID must be provided.")
        self.name = str(name)
        self.gid = int(gid)

        if len(self.passwd_line([]).split(":")) != 4:
            raise Exception("Invalid group, contains colons: %s" % self)

    def users(self, users):
        r = []
        for user in users:
            if self in user.groups:
                r.append(user)
        return r

    def dns_records(self, hesiod_domain, users):
        records = []

        passwd_line = self.passwd_line(users)

        # group record
        fqdn = "%s.group.%s" % (self.name, hesiod_domain)
        records.append(DNSRecord(fqdn.lower(), passwd_line))

        # gid record
        fqdn = "%s.gid.%s" % (self.gid, hesiod_domain)
        records.append(DNSRecord(fqdn.lower(), passwd_line))

        return records

    @classmethod
    # returns group, usernames list
    # usernames will be empty if only a partial line
    def parse_passwd_line(cls, line):
        parts = line.split(":")
        if len(parts) != 3 and len(parts) != 4:
            raise Exception("Invalid group passwd line: %s" % line)
        name = parts[0]
        gid = parts[2]
        usernames = []
        if len(parts) == 4:
            usernames = parts[3].split(",")

        return Group(name, gid), usernames

    def passwd_line(self, users):
        usernames = ",".join(sorted(map(lambda u: u.username, self.users(users))))
        return "%s:x:%d:%s" % (self.name, self.gid, usernames)

    def __eq__(self, other):
        return self.name == other.name and self.gid == other.gid

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return "Group(name=%s, gid=%s)" % (self.name, self.gid)

# A UNIX user
class User(object):
    def __init__(self, name, username, uid, groups, ssh_keys, homedir=None, shell="/bin/bash"):
        self.name = str(name)
        self.username = str(username)
        self.uid = int(uid)
        self.groups = groups
        self.ssh_keys = list(ssh_keys)
        if not homedir:
            homedir = "/home/%s" % self.username
        self.homedir = str(homedir)
        self.shell = str(shell)

        if len(self.passwd_line().split(":")) != 7:
            raise Exception("Invalid user, contains colons: %s" % self)

    @classmethod
    # returns user, primary group id
    def parse_passwd_line(cls, line):
        line = line.replace('"', '')
        parts = line.split(":")
        if len(parts) != 7:
            raise Exception("Invalid user passwd line: %s" % line)
        username, x, uid, group, gecos, homedir, shell = parts
        name = gecos.split(",")[0]
        group = int(group)
        return User(name, username, uid, [], [], homedir, shell), group

    def dns_records(self, hesiod_domain):
        records = []
        # user record
        fqdn = "%s.passwd.%s" % (self.username, hesiod_domain)
        records.append(DNSRecord(fqdn.lower(), self.passwd_line()))

        # uid record
        fqdn = "%s.uid.%s" % (self.uid, hesiod_domain)
        records.append(DNSRecord(fqdn.lower(), self.passwd_line()))

        # group list record
        gl = []
        for group in sorted(self.groups, key=lambda g: g.gid):
            gl.append("%s:%s" % (group.name, group.gid))
        fqdn = "%s.grplist.%s" % (self.username, hesiod_domain)
        records.append(DNSRecord(fqdn.lower(), ":".join(gl)))

        # ssh records
        if self.ssh_keys:
            ssh_keys_count_fqdn = "%s.count.ssh.%s" % (self.username, hesiod_domain)
            records.append(DNSRecord(ssh_keys_count_fqdn.lower(), str(len(self.ssh_keys))))

            # Need to keep this around for backwards compatibility when only one ssh key worked
            legacy_ssh_key_fqdn = "%s.ssh.%s" % (self.username, hesiod_domain)
            records.append(DNSRecord(legacy_ssh_key_fqdn.lower(), self.ssh_keys[0]))

            for _id, ssh_key in enumerate(self.ssh_keys):
                ssh_key_fqdn = "%s.%s.ssh.%s" % (self.username, _id, hesiod_domain)
                records.append(DNSRecord(ssh_key_fqdn.lower(), ssh_key))
        return records

    def passwd_line(self):
        gid = ""
        if self.groups:
            gid = str(self.groups[0].gid)
        return "%s:x:%d:%s:%s:%s:%s" % \
                (self.username, self.uid, gid, self.gecos(), self.homedir, self.shell)

    def gecos(self):
        return "%s,,,," % self.name

    def __eq__(self, other):
        return self.passwd_line() == other.passwd_line()

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return ("User(name=%s, username=%s, uid=%s, groups=%s, ssh_keys=%s, " +
            "homedir=%s, shell=%s)") % \
            (self.name, self.username, self.uid, self.groups,
                    self.ssh_keys, self.homedir, self.shell)

# syncs users and groups to route53
# users is a list of users
# groups is a list of groups
# route53_zone - the hosted zone in Route53 to modify, e.g. example.com
# hesiod_domain - the zone with hesiod information, e.g. hesiod.example.com
def sync(users, groups, route53_zone, hesiod_domain, dry_run):
    conn = r53.connect_to_region('us-east-1')

    record_type = "TXT"
    ttl = "60"

    # suffix of . on zone if not supplied
    if route53_zone[-1:] != '.':
        route53_zone += "."
    if hesiod_domain[-1:] != '.':
        hesiod_domain += "."

    # get existing hosted zones
    zones = {}
    results = conn.get_all_hosted_zones()
    for r53zone in results['ListHostedZonesResponse']['HostedZones']:
        zone_id = r53zone['Id'].replace('/hostedzone/', '')
        zones[r53zone['Name']] = zone_id

    # ensure requested zone is hosted by route53
    if not route53_zone in zones:
        raise Exception("Zone %s does not exist in Route53" % route53_zone)

    sets = conn.get_all_rrsets(zones[route53_zone])

    # existing records
    existing_records = set()
    for rset in sets:
        if rset.type == record_type:
            if rset.name.endswith("group." + hesiod_domain) or \
                    rset.name.endswith("gid." + hesiod_domain) or \
                    rset.name.endswith("passwd." + hesiod_domain) or \
                    rset.name.endswith("uid." + hesiod_domain) or \
                    rset.name.endswith("grplist." + hesiod_domain) or \
                    rset.name.endswith("ssh." + hesiod_domain):
                value = "".join(rset.resource_records).replace('"', '')
                existing_records.add(DNSRecord(str(rset.name), str(value)))

    # new records
    new_records = set()
    for group in groups:
        for record in group.dns_records(hesiod_domain, users):
            new_records.add(record)
    for user in users:
        for record in user.dns_records(hesiod_domain):
            new_records.add(record)

    to_remove = existing_records - new_records
    to_add = new_records - existing_records

    if to_remove:
        print "Deleting:"
        for r in sorted(to_remove):
            print r
        print
    else:
        print "Nothing to delete."

    if to_add:
        print "Adding:"
        for r in sorted(to_add):
            print r
        print
    else:
        print "Nothing to add."

    if dry_run:
        print "Dry run mode. Stopping."
        return

    # stop if nothing to do
    if not to_remove and not to_add:
        return
    for record_chunk in list(chunks(to_remove, 50)):
        changes = ResourceRecordSets(conn, zones[route53_zone])
        for record in record_chunk:
            removal = changes.add_change("DELETE", record.fqdn, record_type, ttl)
            removal.add_value(txt_value(record.value))
        commit_changes(changes, conn)

    for record_chunk in list(chunks(to_add, 50)):
        changes = ResourceRecordSets(conn, zones[route53_zone])
        for record in record_chunk:
            addition = changes.add_change("CREATE", record.fqdn, record_type, ttl)
            addition.add_value(txt_value(record.value))
        commit_changes(changes, conn)

# Commit Changes
def commit_changes(changes, conn):
    print "Commiting changes", changes
    try:
        result = changes.commit()
        status = Status(conn, result["ChangeResourceRecordSetsResponse"]["ChangeInfo"])
    except r53.exception.DNSServerError, e:
        raise Exception("Could not update DNS records.", e)

    while status.status == "PENDING":
        print "Waiting for Route53 to propagate changes."
        time.sleep(10)
        print status.update()

# Make chunks
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    #print lst
    lst=list(lst)
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

# DNS text values are limited to chunks of 255, but multiple chunks are concatenated
# Amazon handles this by requiring you to add quotation marks around each chunk
def txt_value(value):
    first = value[:255]
    rest = value[255:]
    if rest:
        rest_value = txt_value(rest)
    else:
        rest_value = ""

    return '"%s"%s' % (first, rest_value)

def load_data(filename):
    with open(filename, "r") as f:
        contents = yaml.load(f, Loader=yaml.FullLoader)

        route53_zone = contents["route53_zone"]
        hesiod_domain = contents["hesiod_domain"]

        # all groups and users
        groups_idx = {}
        users_idx = {}

        groups = []
        users = []

        for g in contents["groups"]:
            group = Group(**g)
            if group.name in groups_idx:
                raise Exception("Group name is not unique: %s" % group.name)
            if group.gid in groups_idx:
                raise Exception("Group ID is not unique: %s" % group.gid)
            groups_idx[group.name] = group
            groups_idx[group.gid] = group
            groups.append(group)

        for u in contents["users"]:
            groups_this = []
            if u["groups"]:
                for g in u["groups"]:
                    group = groups_idx[g]
                    if not group:
                        raise Exception("No such group: %s" % g)
                    groups_this.append(group)
            u["groups"] = groups_this
            user = User(**u)

            if len(user.groups) == 0:
                raise Exception("At least one group required for user %s" % \
                        user.username)

            if user.username in users_idx:
                raise Exception("Username is not unique: %s" % user.username)
            if user.uid in users_idx:
                raise Exception("User ID is not unique: %s" % user.uid)
            users_idx[user.username] = user
            users_idx[user.uid] = user
            users.append(user)

        return users, groups, route53_zone, hesiod_domain

def main():
    parser = argparse.ArgumentParser(
            description="Synchronize a user database with Route53 for Hesiod.",
            epilog = "AWS credentials follow the Boto standard. See " +
                "http://docs.pythonboto.org/en/latest/boto_config_tut.html. " +
                "For example, you can populate AWS_ACCESS_KEY_ID and " +
                "AWS_SECRET_ACCESS_KEY with your credentials, or use IAM " +
                "role-based authentication (in which case you need not do " +
                "anything).")
    parser.add_argument("user_file", metavar="USER_FILE",
            help="The user yaml file. See example_users.yml for an example.")
    parser.add_argument("--dry-run",
            action='store_true',
            dest="dry_run",
            help="Dry run mode. Do not commit any changes.",
            default=False)

    args = parser.parse_args()

    users, groups, route53_zone, hesiod_domain = load_data(args.user_file)
    sync(users, groups, route53_zone, hesiod_domain, args.dry_run)
    print "Done!"

if __name__ == "__main__":
    main()