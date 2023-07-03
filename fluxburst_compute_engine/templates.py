# Copyright 2023 Lawrence Livermore National Security, LLC and other
# HPCIC DevTools Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (MIT)

# This is a vanilla (non-bursting) config
broker_config = """# Flux needs to know the path to the IMP executable
[exec]
imp = \"/usr/local/libexec/flux/flux-imp\"

# Allow users other than the instance owner (guests) to connect to Flux
# Optionally, root may be given \"owner privileges\" for convenience
[access]
allow-guest-user = true
allow-root-owner = true

# Point to shared network certificate generated flux-keygen(1).
# Define the network endpoints for Flux's tree based overlay network
# and inform Flux of the hostnames that will start flux-broker(1).
[bootstrap]
curve_cert = \"/usr/local/etc/flux/system/curve.cert\"

default_port = 8050
default_bind = \"tcp://eth0:%p\"
default_connect = \"tcp://%h:%p\"

hosts = [{ host = NODELIST },]

# Speed up detection of crashed network peers (system default is around 20m)
[tbon]
tcp_user_timeout = \"2m\"

# Point to resource definition generated with flux-R(1).
# Uncomment to exclude nodes (e.g. mgmt, login), from eligibility to run jobs.
[resource]
path = \"/usr/local/etc/flux/system/R\"
exclude = \"FLUXMANGER\"

# Remove inactive jobs from the KVS after one week.
[job-manager]
inactive-age-limit = \"7d\""""
