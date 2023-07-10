# Copyright 2023 Lawrence Livermore National Security, LLC and other
# HPCIC DevTools Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (MIT)

import os
import shutil

from python_terraform import Terraform

# For now write terraform setups to temporary location

here = os.path.dirname(os.path.abspath(__file__))
recipes = os.path.join(here, "tf")


def generate_variables(params, compute_nodes_needed):
    """
    Given params from the burst plugin, generate terraform variables.
    """
    if params.terraform_plan_name != "burst":
        raise ValueError(f"Plan name {params.terraform_plan_name} is not supported.")
    compute_node_specs = {
        "name_prefix": params.compute_name_prefix,
        "machine_arch": params.compute_machine_arch,
        "machine_type": params.compute_machine_type,
        "instances": compute_nodes_needed,
        "properties": [],
        "gpu_count": params.gpu_count,
        "gpu_type": params.gpu_type,
        "compact": params.compute_compact,
        "boot_script": params.compute_boot_script,
    }
    return {
        "project_id": params.project,
        "network_name": params.network_name,
        "region": params.region,
        "zone": params.zone,
        "compute_node_specs": [compute_node_specs],
        "compute_scopes": params.compute_scopes,
        "compute_family": params.compute_family,
    }


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
