#!/usr/bin/env python3

import argparse
import os
import sys

from fluxburst.client import FluxBurst

# How we provide custom parameters to a flux-burst plugin
from fluxburst_compute_engine.plugin import BurstParameters

# Save data here
here = os.path.dirname(os.path.abspath(__file__))

# Note this runs an isolated burst, so we don't extend a local cluster.
# We currently require a curve.certificate to be generated,
# you can do this in fluxrm/flux-sched:focal with `flux keygen curve.cert`

curve_cert = """#   ****  Generated on 2023-07-10 00:58:16 by CZMQ  ****
#   ZeroMQ CURVE **Secret** Certificate
#   DO NOT PROVIDE THIS FILE TO OTHER USERS nor change its permissions.

metadata
    name = "1c6ff0f9feb3"
    keygen.czmq-version = "4.2.0"
    keygen.sodium-version = "1.0.18"
    keygen.flux-core-version = "0.51.0-135-gb20460a6e"
    keygen.hostname = "1c6ff0f9feb3"
    keygen.time = "2023-07-10T00:58:16"
    keygen.userid = "1002"
    keygen.zmq-version = "4.3.2"
curve
    public-key = "Kmzvmw!9^i!fu*[Dg]qJR1TcuFr-%o:U4Ya.<qV]"
    secret-key = "Vj12s!j.HAifDz5cN)uC?D3kSY60]bkOS51Z!hah"
"""


def get_parser():
    parser = argparse.ArgumentParser(
        description="Experimental Bursting",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--project", help="Google Cloud project")
    return parser


def main():
    """
    Create an external cluster we can burst to, and optionally resize.
    """
    parser = get_parser()

    # If an error occurs while parsing the arguments, the interpreter will exit with value 2
    args, _ = parser.parse_known_args()
    if not args.project:
        sys.exit("Please define your Google Cloud Project with --project")

    # Create the dataclass for the plugin config
    # We use a dataclass because it does implicit validation of required params, etc.
    params = BurstParameters(
        project=args.project,
        isolated_burst=True,
        curve_cert=curve_cert,
        compute_machine_type="n2-standard-4",
    )

    # Create a mock flux burst client. This will return a fake burstable job
    client = FluxBurst(mock=True)

    # For debugging, here is a way to see plugins available
    # import fluxburst.plugins as plugins
    # print(plugins.burstable_plugins)
    # {'gke': <module 'fluxburst_gke' from '/home/flux/.local/lib/python3.8/site-packages/fluxburst_gke/__init__.py'>}

    # Load our plugin and provide the dataclass to it!
    client.load("compute_engine", params)

    # Sanity check loaded
    print(f"flux-burst client is loaded with plugins for: {client.choices}")

    # We are using the default algorithms to filter the job queue and select jobs.
    # If we weren't, we would add them via:
    # client.set_ordering()
    # client.set_selector()

    # Here is how we can see the jobs that are contenders to burst!
    # client.select_jobs()

    # Now let's run the burst! The active plugins will determine if they
    # are able to schedule a job, and if so, will do the work needed to
    # burst. unmatched jobs (those we weren't able to schedule) are
    # returned, maybe to do something with? Note that the default mock
    # generates a N=4 job. For compute engine that will be 3 compute
    # nodes and 1 login node.
    unmatched = client.run_burst()
    assert not unmatched
    plugin = client.plugins["compute_engine"]
    print(
        f"Terraform configs and working directory are found at {plugin.params.terraform_dir}"
    )
    input("Press Enter to when you are ready to destroy...")

    # Get a handle to the plugin so we can cleanup!
    plugin.cleanup()


if __name__ == "__main__":
    main()
