#!/usr/bin/env python3

import argparse
import os
import sys
import time

from fluxburst.client import FluxBurst

# How we provide custom parameters to a flux-burst plugin
from fluxburst_compute_engine.plugin import BurstParameters

# Save data here
here = os.path.dirname(os.path.abspath(__file__))

# Note this runs an isolated burst, so we don't extend a local cluster.


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
    params = BurstParameters(project=args.project)

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
    # returned, maybe to do something with?
    unmatched = client.run_burst()
    assert not unmatched
    print("Sleeping for a few minutes so you can look around...")
    time.sleep(360)

    # Get a handle to the plugin so we can cleanup!
    plugin = client.plugins["compute_engine"]
    plugin.cleanup()


if __name__ == "__main__":
    main()
