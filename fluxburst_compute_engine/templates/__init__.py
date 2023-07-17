# Copyright 2023 Lawrence Livermore National Security, LLC and other
# HPCIC DevTools Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (MIT)

import os

import fluxburst.utils as utils

here = os.path.dirname(os.path.abspath(__file__))


def get_script(name, replace):
    """
    Get a template file by name and replace a set of strings.
    """
    template_file = os.path.join(here, name)
    if not os.path.exists(template_file):
        raise ValueError(f"{template_file} does not exist")
    template = utils.read_file(template_file)
    for key, value in replace.items():
        template = template.replace(key, value)
    return template
