# Copyright 2023 Lawrence Livermore National Security, LLC and other
# HPCIC DevTools Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (MIT)

import os
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional

from fluxburst.logger import logger
from fluxburst.plugins import BurstPlugin
from python_terraform import IsFlagged

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

    # Lead broker size
    lead_size: Optional[str] = None

    # Directory to init / install terraform modules
    # If not set, defaults to temporary directory
    terraform_dir: Optional[str] = "/tmp/tmplwvbme2s"

    # Custom broker config toml template for bursted cluster
    broker_config: Optional[str] = None

    # Name of the terraform plan to use under tf
    terraform_plan_name: Optional[str] = "basic"
    cluster_name: Optional[str] = "flux-bursted-cluster"

    # This is used for the manager node
    manager_machine_type: Optional[str] = "e2-standard-8"

    # API scopes for the manager (all of google cloud)
    manager_scopes: List = field(default_factory=lambda: ["cloud-platform"])
    manager_name_prefix: Optional[str] = "gffw"
    manager_family: Optional[str] = "flux-fw-manager-x86-64"

    # Login node specs
    login_scopes: List = field(default_factory=lambda: ["cloud-platform"])
    login_name_prefix: Optional[str] = "gffw-login"
    login_family: Optional[str] = "flux-fw-login-x86-64"
    login_machine_arch: Optional[str] = "x86-64"
    login_machine_type: Optional[str] = "e2-standard-4"
    login_count: Optional[int] = 1
    login_boot_script: Optional[str] = None

    # If this isn't set, each template can define a custom one
    login_boot_script: Optional[str] = None

    # Compute node specs
    compute_scopes: List = field(default_factory=lambda: ["cloud-platform"])
    compute_name_prefix: Optional[str] = "gffw-compute-a"
    compute_machine_arch: Optional[str] = "x86-64"
    compute_machine_type: Optional[str] = "c2-standard-8"
    compute_count: Optional[int] = 1
    compute_boot_script: Optional[str] = None
    compute_family: Optional[str] = "flux-fw-compute-x86-64"

    # Compact mode
    compute_compact: Optional[bool] = False

    # GPUS (not tested)
    gpu_type: Optional[str] = None
    gpu_count: Optional[int] = 0

    # NOT USED OR TESTED/IMPLEMENTED YET
    # Flux log level
    log_level: Optional[int] = 7

    # Custom flux user
    flux_user: Optional[str] = None

    # arguments to flux wrap, e.g., "strace,-e,network,-tt
    wrap: Optional[str] = None

    # Name of a secret to be made in the same namespace
    munge_secret_name: Optional[str] = "munge-key"

    # Path to munge.key file (local) to use to create config map
    # If this is owned by root, likely won't be readable
    munge_key: Optional[str] = "/etc/munge/munge.key"

    # curve secret name to do the same for
    curve_cert_secret_name: Optional[str] = "curve-cert"

    # Path to curve.cert
    curve_cert: Optional[str] = "/mnt/curve/curve.cert"


class FluxBurstComputeEngine(BurstPlugin):
    # Set our custom dataclass, otherwise empty
    _param_dataclass = BurstParameters

    def run(self):
        """
        Given some set of scheduled jobs, run bursting.
        """
        # Exit early if no jobs to burst
        if not self.jobs:
            logger.info(f"Plugin {self.name} has no jobs to burst.")
            return

        # For now, assuming one burst will be done to run all jobs,
        # we just get the max size. This is obviously not ideal
        node_count = max([v["nnodes"] for _, v in self.jobs.items()])

        # Prepare variables for the plan
        # We assume for now they take the same variables. This could change.
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

        # run plan (this will return 2 since we don't set -out, which is fine for now)
        retval, _, _ = tf.plan(no_color=IsFlagged, refresh=False, capture_output=False)

        # Approve and apply
        # TODO add capture_output=False so we can see
        retval, _, _ = tf.apply(skip_plan=True, capture_output=False)
        if retval != 0:
            logger.exit(
                f"Error running terraform apply for plan {self.params.terraform_plan_name} in {self.params.terraform_dir}, see output above."
            )

        # TODO we need to store this as a named cluster under self.clusters
        # TODO if this is an external burst (and the broker does not connect) we need a way to submit jobs
        # TODO This assumes submitting all jobs to the cluster we just created
        for _, job in self.jobs.items():
            print("TODO: if external/isolated, need way to submit")

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

        if self.params.isolated_burst and (
            not self.params.lead_host
            or not self.params.lead_port
            or not self.params.lead_size
        ):
            logger.error(
                "A non-isolated burst should have lead host, port, and size defined."
            )
            return False

        # Boot scripts, if provided, must exist
        for script in [self.params.login_boot_script, self.params.compute_boot_script]:
            if script and not os.path.exists(script):
                logger.error("Boot script {script} does not exist.")
                return False

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
