# Copyright 2023 Lawrence Livermore National Security, LLC and other
# HPCIC DevTools Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (MIT)

import os
import shutil

from fluxburst.logger import logger
from python_terraform import Terraform

# For now write terraform setups to temporary location

here = os.path.dirname(os.path.abspath(__file__))
recipes = os.path.join(here, "tf")


def generate_variables(params, node_count):
    """
    Given params from the burst plugin, generate terraform variables.
    """
    # Template directory
    path = os.path.join(recipes, params.terraform_plan_name)

    # Always set the default boot script. We could eventually
    # expose a variable to prevent this from being set
    default_boot_script = os.path.join(path, "boot_script.sh")

    # If we have a boot script, use it, otherwise default
    if not params.login_boot_script and os.path.exists(default_boot_script):
        logger.debug(
            "Using default boot script {default_boot_script} for login node spec."
        )
        params.login_boot_script = default_boot_script

    if not params.compute_boot_script and os.path.exists(default_boot_script):
        logger.debug(
            "Using default boot script {default_boot_script} for compute node spec."
        )
        params.compute_boot_script = default_boot_script

    login_node_specs = {
        "name_prefix": params.login_name_prefix,
        "machine_arch": params.login_machine_arch,
        "machine_type": params.login_machine_type,
        "instances": params.login_count,
        "properties": [],
        "boot_script": params.login_boot_script,
    }

    compute_node_specs = {
        "name_prefix": params.compute_name_prefix,
        "machine_arch": params.compute_machine_arch,
        "machine_type": params.compute_machine_type,
        "instances": node_count,
        "properties": [],
        "gpu_count": params.gpu_count,
        "gpu_type": params.gpu_type,
        "compact": params.compute_compact,
        "boot_script": params.login_boot_script,
    }
    variables = {
        "project_id": params.project,
        "network_name": params.network_name,
        "region": params.region,
        "zone": params.zone,
        "manager_machine_type": params.manager_machine_type,
        "manager_name_prefix": params.manager_name_prefix,
        "manager_scopes": params.manager_scopes,
        "login_node_specs": [login_node_specs],
        "login_scopes": params.login_scopes,
        "compute_node_specs": [compute_node_specs],
        "compute_scopes": params.compute_scopes,
        "broker_config": "",
        "manager_family": params.manager_family,
        "compute_family": params.compute_family,
        "login_family": params.login_family,
    }
    # If we have a custom broker config, use it.
    if params.broker_config:
        variables["broker_config"] = params.broker_config
    return variables


def get_compute_engine_plan(dest, name="basic", variables=None):
    """
    Get a named subdirectory of terraform recipes
    """
    variables = variables or {}
    path = os.path.join(recipes, name)
    if not os.path.exists(path):
        raise ValueError(f"Recipe {name} does not exist at {path}")

    # Prepare the directory for the plan, if doesn't exist yet
    dest = os.path.join(dest, name)
    if not os.path.exists(dest):
        shutil.copytree(path, dest)
    return Terraform(working_dir=dest, variables=variables)
