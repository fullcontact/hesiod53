#!/usr/bin/env python
import argparse
import dns.resolver
import time

# Meant for handling dns query failures
def retry(func, max_retries=3):
   def func_wrapper(*args, **kwargs):
        for attempt in range(0, max_retries):
            try:
                return func(*args, **kwargs)
            except:
                time.sleep(0.1)
        return
   return func_wrapper

def concatenate_txt_record(answers):
    results = []
    for rdata in answers:
        results.append("".join(rdata.strings))
    return results

@retry
def fetch_ssh_key_count(username, hesiod_domain):
    fqdn = "{username}.count.ssh.{domain}".format(username=username, domain=hesiod_domain)
    answers = dns.resolver.query(fqdn, "TXT", tcp=True)
    return int(concatenate_txt_record(answers)[0])

@retry
def fetch_ssh_key(username, hesiod_domain, _id):
    fqdn = "{username}.{id}.ssh.{domain}".format(username=username, id=_id, domain=hesiod_domain)
    answers = dns.resolver.query(fqdn, "TXT", tcp=True)
    return concatenate_txt_record(answers)

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

    for _id in range(0, fetch_ssh_key_count(username, hesiod_domain)):
        for key in fetch_ssh_key(username, hesiod_domain, _id):
            print key

if __name__ == "__main__":
    main()
