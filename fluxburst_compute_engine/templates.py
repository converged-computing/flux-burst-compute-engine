# Copyright 2023 Lawrence Livermore National Security, LLC and other
# HPCIC DevTools Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (MIT)

# This is a vanilla (non-bursting) config, mostly for reference
default_broker_config = """# Flux needs to know the path to the IMP executable
[exec]
imp = "/usr/local/libexec/flux/flux-imp"

# Allow users other than the instance owner (guests) to connect to Flux
# Optionally, root may be given "owner privileges" for convenience
[access]
allow-guest-user = true
allow-root-owner = true

# Point to shared network certificate generated flux-keygen(1).
# Define the network endpoints for Flux's tree based overlay network
# and inform Flux of the hostnames that will start flux-broker(1).
[bootstrap]
curve_cert = "/usr/local/etc/flux/system/curve.cert"

default_port = 8050
default_bind = "tcp://eth0:%p"
default_connect = "tcp://%h:%p"

hosts = [{ host = "NODELIST"},]

# Speed up detection of crashed network peers (system default is around 20m)
[tbon]
tcp_user_timeout = "2m"

# Point to resource definition generated with flux-R(1).
# Uncomment to exclude nodes (e.g. mgmt, login), from eligibility to run jobs.
[resource]
path = "/usr/local/etc/flux/system/R"
exclude = "FLUXMANAGER"

# Remove inactive jobs from the KVS after one week.
[job-manager]
inactive-age-limit = "7d"
"""

# This expects a local and remote cluster
bursting_broker_config = """# Flux needs to know the path to the IMP executable
[exec]
imp = "/usr/local/libexec/flux/flux-imp"

# Allow users other than the instance owner (guests) to connect to Flux
# Optionally, root may be given "owner privileges" for convenience
[access]
allow-guest-user = true
allow-root-owner = true

# Point to shared network certificate generated flux-keygen(1).
# Define the network endpoints for Flux's tree based overlay network
# and inform Flux of the hostnames that will start flux-broker(1).
[bootstrap]
curve_cert = "/usr/local/etc/flux/system/curve.cert"

default_port = 8050
default_bind = "tcp://eth0:%p"
default_connect = "tcp://%h:%p"

hosts = [{host="LEAD_BROKER_ADDRESS", bind="tcp://eth0:LEAD_BROKER_PORT", connect="tcp://LEAD_BROKER_ADDRESS:LEAD_BROKER_PORT"},
         {host="NODELIST"}]

# Speed up detection of crashed network peers (system default is around 20m)
[tbon]
tcp_user_timeout = "2m"

# Point to resource definition generated with flux-R(1).
# Uncomment to exclude nodes (e.g. mgmt, login), from eligibility to run jobs.
[resource]
path = "/usr/local/etc/flux/system/R"
# exclude this for now, doesn't seem to work
# exclude = "FLUXMANAGER"

# Remove inactive jobs from the KVS after one week.
[job-manager]
inactive-age-limit = "7d"
"""

bursting_boot_script = """#!/bin/sh

set -eEu -o pipefail

# This is already built into the image
fluxuser=flux
fluxuid=$(id -u ${fluxuser})
fluxroot=/usr/local

echo "Flux username: ${fluxuser}"
echo "Flux install root: ${fluxroot}"
export fluxroot

# Prepare NFS
dnf install nfs-utils -y

mkdir -p /var/nfs/home
chown nobody:nobody /var/nfs/home

ip_addr=$(hostname -I)

echo "/var/nfs/home *(rw,no_subtree_check,no_root_squash)" >> /etc/exports

firewall-cmd --add-service={nfs,nfs3,mountd,rpc-bind} --permanent
firewall-cmd --reload

systemctl enable --now nfs-server rpcbind

# commands to be run as root
asFlux="sudo -u ${fluxuser} -E HOME=/home/${fluxuser} -E PATH=$PATH"

# TODO we can allow custom logic here if needed

echo "${fluxuser} ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers
printf "${fluxuser} user identifiers:\n$(id ${fluxuser})\n"
printf "\nAs Flux prefix for flux commands: ${asFlux}\n"

export STATE_DIR=/var/lib/flux
mkdir -p ${STATE_DIR}
mkdir -p /usr/local/etc/flux/system/conf.d

# Broker Options: important!
# TODO newer flux will not have quorum=ranks, but rather -Sbroker.quorum=2 (size)
brokerOptions="-Scron.directory=/usr/local/etc/flux/system/conf.d \
  -Stbon.fanout=256 \
  -Srundir=/run/flux -Sbroker.rc2_none  \
  -Sstatedir=${STATE_DIR} \
  -Slocal-uri=local:///run/flux/local \
  -Stbon.connect_timeout=5s \
  -Sbroker.quorum=0-1 \
  -Stbon.zmqdebug=1 \
  -Slog-stderr-level=7  \
  -Slog-stderr-mode=local"

# --cores=IDS Assign cores with IDS to each rank in R, so we  assign 0-(N-1) to each host
echo "flux R encode --hosts=NODELIST"
flux R encode --hosts=NODELIST --local > /usr/local/etc/flux/system/R
printf "\n📦 Resources\n"
cat /usr/local/etc/flux/system/R

mkdir -p /usr/local/etc/flux/imp/conf.d/
cat <<EOT >> /usr/local/etc/flux/imp/conf.d/imp.toml
[exec]
allowed-users = [ "${fluxuser}", "root" ]
allowed-shells = [ "${fluxroot}/libexec/flux/flux-shell" ]
EOT

printf "\n🦊 Independent Minister of Privilege\n"
cat /usr/local/etc/flux/imp/conf.d/imp.toml

cat <<EOT >> /tmp/system.toml
[exec]
imp = "/usr/local/libexec/flux/flux-imp"

# Allow users other than the instance owner (guests) to connect to Flux
# Optionally, root may be given "owner privileges" for convenience
[access]
allow-guest-user = true
allow-root-owner = true

# Point to shared network certificate generated flux-keygen(1).
# Define the network endpoints for Flux's tree based overlay network
# and inform Flux of the hostnames that will start flux-broker(1).
[bootstrap]
curve_cert = "/usr/local/etc/flux/system/curve.cert"

default_port = 8050
default_bind = "tcp://eth0:%p"
default_connect = "tcp://%h:%p"

hosts = [{host="LEAD_BROKER_ADDRESS", bind="tcp://eth0:LEAD_BROKER_PORT", connect="tcp://LEAD_BROKER_ADDRESS:LEAD_BROKER_PORT"},
         {host="NODELIST"}]

# Speed up detection of crashed network peers (system default is around 20m)
[tbon]
tcp_user_timeout = "2m"

# Point to resource definition generated with flux-R(1).
# Uncomment to exclude nodes (e.g. mgmt, login), from eligibility to run jobs.
[resource]
path = "/usr/local/etc/flux/system/R"

# Remove inactive jobs from the KVS after one week.
[job-manager]
inactive-age-limit = "7d"
EOT

mv /tmp/system.toml /usr/local/etc/flux/system/conf.d/system.toml

printf "\n🐸 Broker Configuration\n"
cat /usr/local/etc/flux/conf.d/system.toml

# If we are communicating via the flux uri this service needs to be started
chmod u+s ${fluxroot}/libexec/flux/flux-imp
chmod 4755 ${fluxroot}/libexec/flux/flux-imp
chmod 0644 /usr/local/etc/flux/imp/conf.d/imp.toml
sudo chown -R ${fluxuser}:${fluxuser} /usr/local/etc/flux/system/conf.d

mkdir -p /etc/munge
rm -rf /etc/munge/munge.key
python3 /etc/flux/manager/convert_munge_key.py "MUNGEKEY" /etc/munge/munge.key
chmod u=r,g=,o= /etc/munge/munge.key
chown munge:munge /etc/munge/munge.key

cat <<EOT >> /tmp/curve.cert
CURVECERT
EOT

mv /tmp/curve.cert /usr/local/etc/flux/system/curve.cert
chmod u=r,g=,o= /usr/local/etc/flux/system/curve.cert
chown ${fluxuser}:${fluxuser} /usr/local/etc/flux/system/curve.cert
service munge start > /dev/null 2>&1

# The rundir needs to be created first, and owned by user flux
# Along with the state directory and curve certificate
mkdir -p /run/flux

# Remove group and other read
chmod o-r /usr/local/etc/flux/system/curve.cert
chmod g-r /usr/local/etc/flux/system/curve.cert
chown -R ${fluxuid} /run/flux ${STATE_DIR} /usr/local/etc/flux/system/curve.cert

printf "\n✨ Curve certificate generated by helper pod\n"
cat /usr/local/etc/flux/system/curve.cert

# Sleep until the broker is ready
printf "\n🌀 flux start -o --config /usr/local/etc/flux/system/conf.d ${brokerOptions}\n"
while true
    do
    ${asFlux} flux start -o --config /usr/local/etc/flux/system/conf.d ${brokerOptions}
    retval=$?
    echo "Return value for follower worker is ${retval}"
    if [[ "${retval}" -eq 0 ]]; then
        echo "The follower worker exited cleanly. Goodbye!"
        break
    fi
    echo "😪 Sleeping 15s until broker is ready..."
    sleep 15
done
"""
