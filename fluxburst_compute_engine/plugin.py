# Copyright 2023 Lawrence Livermore National Security, LLC and other
# HPCIC DevTools Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (MIT)

import base64
import os
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional

import fluxburst.utils as utils
from fluxburst.logger import logger
from fluxburst.plugins import BurstPlugin
from python_terraform import IsFlagged

import fluxburst_compute_engine.templates as templates
import fluxburst_compute_engine.terraform as terraform


@dataclass
class BurstParameters:
    """
    Custom parameters for Flux Operator bursting.

    It should be possible to read this in from yaml, or the
    environment (or both).
    """

    # Google Cloud Project
    project: str

    network_name: Optional[str] = "foundation-net"
    region: Optional[str] = "us-central1"
    zone: Optional[str] = "us-central1-a"

    # An isolated burst brings up an independent cluster
    isolated_burst: Optional[bool] = False

    # Lead broker service hostname or ip address
    lead_host: Optional[str] = None

    # Lead broker service port (e.g, 30093)
    lead_port: Optional[str] = None

    # Host names on the main cluster excluding the lead_host
    # and additional login hosts. E.g.,
    # gffw-login-001,gffw-compute-a-[001-004]
    lead_hostnames: Optional[str] = None

    # Directory to init / install terraform modules
    # If not set, defaults to temporary directory
    terraform_dir: Optional[str] = None

    # Custom broker config / curve certs for bursted cluster
    curve_cert: Optional[str] = None
    munge_key: Optional[str] = None

    # Name of the terraform plan to use under tf.
    terraform_plan_name: Optional[str] = "burst"
    cluster_name: Optional[str] = "flux-bursted-cluster"

    # Compute node specs
    compute_scopes: List = field(default_factory=lambda: ["cloud-platform"])
    compute_name_prefix: Optional[str] = "gffw-compute-a"
    compute_machine_arch: Optional[str] = "x86-64"
    compute_machine_type: Optional[str] = "c2-standard-8"
    compute_family: Optional[str] = "flux-bursted-compute-x86-64"

    # Compact mode
    compute_compact: Optional[bool] = False

    # GPUS (not added yet)
    gpu_type: Optional[str] = None
    gpu_count: Optional[int] = 0

    # Flux log level
    log_level: Optional[int] = 7

    # Custom flux user
    flux_user: Optional[str] = None

    # arguments to flux wrap, e.g., "strace,-e,network,-tt
    wrap: Optional[str] = None


class FluxBurstComputeEngine(BurstPlugin):
    # Set our custom dataclass, otherwise empty
    _param_dataclass = BurstParameters

    def generate_hostlist_range(self, size):
        """
        Generate the range for the hostlist (e.g., [0-2])
        """
        if size == 1:
            return "0"
        return f"0-{size-1}"

    def generate_bursted_boot_script(self, hosts):
        """
        Generate a bursted broked config.
        """
        template = templates.bursting_boot_script
        with open(self.params.munge_key, "rb") as fd:
            content = fd.read()
        bytes_string = base64.b64encode(content).decode("utf-8")

        # Also encode curve-cert in case there are illegal characters
        curve_cert = self.load_encoded_curve_cert()

        # We call this a poor man's jinja2!
        replace = {
            "NODELIST": hosts,
            "LOGLEVEL": str(self.params.log_level),
            "CURVECERT": curve_cert,
            "MUNGEKEY": bytes_string,
            "LEAD_BROKER_ADDRESS": self.params.lead_host,
            "LEAD_BROKER_PORT": str(self.params.lead_port),
        }
        for key, value in replace.items():
            template = template.replace(key, value)
        self.params.compute_boot_script = template

    def load_encoded_curve_cert(self):
        """
        Determine if we are given a path or string verbatim

        Return encoded for the start script to handle.
        """
        curve_cert = self.params.curve_cert
        if os.path.exists(curve_cert):
            curve_cert = utils.read_file(self.params.curve_cert)
        elif "public-key" not in curve_cert and "secret-key" not in curve_cert:
            raise ValueError(
                "Curve cert is either invalid (as string) or path does not exist."
            )
        return base64.b64encode(curve_cert.encode("utf-8")).decode("utf-8")

    def generate_default_boot_script(self, node_count):
        """
        Generate a bursted broked config.
        """
        template = templates.default_boot_script

        # Generate range of hosts, numbered 1-N
        hostrange = "001"
        if node_count > 1:
            # zfill 3 will produce 4 -> 004
            end = str(node_count).zfill(3)
            hostrange = f"[001-{end}]"

        # Default pattern of hostnames
        hosts = f"{self.params.compute_name_prefix}-{hostrange}"
        curve_cert = self.load_encoded_curve_cert()

        # We call this a poor man's jinja2!
        replace = {
            "LOGLEVEL": str(self.params.log_level),
            "NODELIST": hosts,
            "CURVECERT": curve_cert,
        }
        for key, value in replace.items():
            template = template.replace(key, value)
        self.params.compute_boot_script = template

    def generate_resource_hostlist(self):
        """
        Generate the hostlist for the resource spec and the broker.toml.

        The hostnames need to line up, index wise, for the bursting to work.
        Unlike the Flux Operator, here we expected the user of the plugin
        to define the full hostnames for the bursted clusters.
        """
        # hosts are the lead broker address plus the original node names.
        # TODO need to have NODELIST just be here
        # hosts = [{ host = "gffw-manager-001,gffw-login-001,gffw-compute-a-[001-004]" },]
        # Except gffw-manager-001 should be an ip address (typically)
        return f"{self.params.lead_host},{self.params.lead_hostnames}"

    def run(self, request_burst=False, nodes=None, tasks=None):
        """
        Given some set of scheduled jobs, run bursting.
        """
        # Don't support this yet - not enough time to develop / ensure working
        if self.params.isolated_burst:
            logger.warning(
                "Isolated burst is not fully tested yet, please open an issue if you want it."
            )
            return

        # Exit early if no jobs to burst
        if not self.jobs and not request_burst:
            logger.info(f"Plugin {self.name} has no jobs to burst.")
            return

        # If we have requested a burst, nodes are required
        if request_burst and not nodes:
            logger.warning("Burst requests require a number of nodes.")
            return

        # Request a burst with some number of nodes and tasks, vs. derive from jobs
        if request_burst:
            node_count = nodes
        else:
            # For now, assuming one burst will be done to run all jobs,
            # we just get the max size. This is obviously not ideal
            node_count = max([v["nnodes"] for _, v in self.jobs.items()])

        # If we don't have an isolated burst, generate a broker config
        hosts = None
        if not self.params.isolated_burst:
            hosts = self.generate_resource_hostlist()
            self.generate_bursted_boot_script(hosts)
        else:
            self.generate_default_boot_script(node_count)

        # Prepare variables for the plan
        # We assume for now they take the same variables. This could change.
        # The total node count should be == login +
        variables = terraform.generate_variables(self.params, node_count)

        # Get the desired terraform config (defaults to basic)
        # These commands assume terraform is installed, likely we need to check for this
        tf = terraform.get_compute_engine_plan(
            self.params.terraform_dir, self.params.terraform_plan_name, variables
        )

        # Save tf object at cluster name, and in future we would check for it (and include size)
        # Right now with the cluster_name parameter, we assume the creator is managing clusters
        self.clusters[self.params.cluster_name] = tf

        # run init
        print(f"Running terraform init for plan {self.params.terraform_plan_name}...")
        retval, _, _ = tf.init(capture_output=False)
        if retval != 0:
            logger.exit(
                f"Error running terraform init for plan {self.params.terraform_plan_name} in {self.params.terraform_dir}, see output above."
            )

        # We don't check output here because it seems to always return 2
        # Save the plan file in case
        outfile = os.path.join(tf.working_dir, "tfplan")
        retval, _, _ = tf.plan(
            no_color=IsFlagged, refresh=False, capture_output=False, out=outfile
        )

        # Approve and apply
        # TODO add capture_output=False so we can see
        retval, _, _ = tf.apply(skip_plan=True, capture_output=False)
        if retval != 0:
            logger.exit(
                f"Error running terraform apply for plan {self.params.terraform_plan_name} in {self.params.terraform_dir}, see output above."
            )

    def validate_params(self):
        """
        Validate parameters provided as BurstParameters.

        This includes checking to see if we have an isolated burst,
        and if a script is provided for any boot script, ensuring that
        it exists.
        """
        # This is the base directory, with subfolders as named plans
        if not self.params.terraform_dir:
            self.params.terraform_dir = tempfile.mkdtemp()

        # If it's an isolated burst, use the burst terraform configs
        if not self.params.isolated_burst:
            self.params.terraform_plan_name = "burst"

        if self.params.munge_key and not os.path.exists(self.params.munge_key):
            logger.error(f"Munge key {self.params.munge_key} does not exist.")
            return False

        # Isolated burst means not connecting two clusters
        # A non isolated burst requires metadata about local and remote cluster!
        if not self.params.isolated_burst:
            # This is the metadata we need about the local cluster
            if (
                not self.params.lead_host
                or not self.params.lead_port
                or not self.params.lead_hostnames
                or not self.params.curve_cert
                or not self.params.munge_key
            ):
                logger.error(
                    "A non-isolated burst should have lead host, port, hostnames, curve cert, and munge key defined."
                )
                return False

        # TODO we can add support for custom boot logic here
        return True

    def schedule(self, job):
        """
        Given a burstable job, determine if we can schedule it.

        This function should also consider logic for deciding if/when to
        assign clusters, but run should actually create/destroy.
        """
        # If it's not an isolated burst and we don't have host variables, no go
        if not self.validate_params():
            return False

        # We cannot run any jobs without Google Application Credentials
        if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
            logger.warning(
                "GOOGLE_APPLICATION_CREDENTIALS not found in environment, cannot schedule to Compute Engine."
            )
            return False

        # TODO determine if we can match some resource spec to another,
        # We likely want this class to be able to generate a lookup of
        # instances / spec about them.

        # For now, we just accept anything, and add to our jobs and return true
        if job["id"] in self.jobs:
            logger.debug(f"{job['id']} is already scheduled")
            return True

        # Add to self.jobs and return True!
        self.jobs[job["id"]] = job
        return True

    def cleanup(self, name=None):
        """
        Cleanup (delete) one or more clusters
        """
        if name and name not in self.clusters:
            raise ValueError(f"{name} is not a known cluster.")
        clusters = self.clusters if not name else {"name": self.clusters["name"]}
        for cluster_name, tf in clusters.items():
            logger.info(f"Cleaning up {cluster_name}")

            # Workaround that there is no force added here
            # https://github.com/beelit94/python-terraform/blob/99950cb03c37abadb0d7e136452e43f4f17dd4e1/python_terraform/__init__.py#L129
            options = tf._generate_default_options({"capture_output": False})
            args = tf._generate_default_args(None)
            args.append("-auto-approve")
            retval, _, _ = tf.cmd("destroy", *args, **options)
            if retval != 0:
                logger.warning(
                    f"Error destroying plan {self.params.terraform_plan_name} in {self.params.terraform_dir}, check Google Cloud console."
                )

        # Update known clusters
        self.refresh_clusters(clusters)
