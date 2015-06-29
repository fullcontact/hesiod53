#!/usr/bin/env python

import argparse
import dns.resolver
import time

def fetch_ssh_keys(username, hesiod_domain, tries=3):
    fqdn = username + ".ssh." + hesiod_domain
    results = []

    try:
        # use TCP because ssh keys are too big for UDP anyways, so we'll back
        # off and try TCP eventually anyways
        answers = dns.resolver.query(fqdn, "TXT", tcp=True)
        for rdata in answers:
            results.append("".join(rdata.strings))
    except:
        # retry, in case of dns failure
        if tries > 1:
            time.sleep(0.3)
            return fetch_ssh_keys(username, hesiod_domain, tries - 1)

    return results

def find_hesiod_domain(hesiod_conf_file):
    lhs = None
    rhs = None
    with open(hesiod_conf_file) as f:
        for line in f:
            line = line.strip()
            if line.startswith("lhs="):
                lhs = line[4:]
            elif line.startswith("rhs="):
                rhs = line[4:]
    if not lhs:
        lhs = ".ns"
    if not rhs:
        raise Exception("Hesiod domain could not be found. " +
            "Set rhs in /etc/hesiod.conf")

    hesiod_domain = lhs + rhs
    if hesiod_domain[0] == ".":
        hesiod_domain = hesiod_domain[1:]
    return hesiod_domain

def main():
    parser = argparse.ArgumentParser(
            description="Fetch SSH credentials for the ssh server using hesiod")
    parser.add_argument("username", metavar="USERNAME",
            help="The username for which ssh credentials should be fetched.")
    parser.add_argument("--hesiod-conf", metavar="HESIOD_CONF_FILE",
            dest="hesiod_conf_file",
            help="Hesiod configuration file location.",
            default="/etc/hesiod.conf")

    args = parser.parse_args()

    username = args.username
    hesiod_domain = find_hesiod_domain(args.hesiod_conf_file)

    for key in fetch_ssh_keys(username, hesiod_domain):
        print key

if __name__ == "__main__":
    main()
