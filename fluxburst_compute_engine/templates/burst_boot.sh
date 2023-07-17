#!/bin/sh

# Burst boot, requires:
# CURVECERT: base64 encoded curve certificate
# NODELIST: with complete list of nodes
# LOGLEVEL: desireed flux log level
# MUNGEKEY: bytes string for the munge key
# LEAD_BROKER_ADDRESS
# LEAD_BROKER_PORT

set -eEu -o pipefail

# This is already built into the image
fluxuser=flux
fluxuid=$(id -u ${fluxuser})

# IMPORTANT - this needs to match the local cluster
fluxroot=/usr

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
mkdir -p ${fluxroot}/etc/flux/system/conf.d

# --cores=IDS Assign cores with IDS to each rank in R, so we  assign 0-(N-1) to each host
echo "flux R encode --hosts=NODELIST"
flux R encode --hosts=NODELIST --local > ${fluxroot}/etc/flux/system/R
printf "\n📦 Resources\n"
cat ${fluxroot}/etc/flux/system/R

mkdir -p /etc/flux/imp/conf.d/
cat <<EOT >> /etc/flux/imp/conf.d/imp.toml
[exec]
allowed-users = [ "${fluxuser}", "root" ]
allowed-shells = [ "${fluxroot}/libexec/flux/flux-shell" ]
EOT

printf "\n🦊 Independent Minister of Privilege\n"
cat /etc/flux/imp/conf.d/imp.toml

cat <<EOT >> /tmp/system.toml
[exec]
imp = "${fluxroot}/libexec/flux/flux-imp"

# Allow users other than the instance owner (guests) to connect to Flux
# Optionally, root may be given "owner privileges" for convenience
[access]
allow-guest-user = true
allow-root-owner = true

# Point to shared network certificate generated flux-keygen(1).
# Define the network endpoints for Flux's tree based overlay network
# and inform Flux of the hostnames that will start flux-broker(1).
[bootstrap]
curve_cert = "${fluxroot}/etc/flux/system/curve.cert"

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
path = "${fluxroot}/etc/flux/system/R"

# Remove inactive jobs from the KVS after one week.
[job-manager]
inactive-age-limit = "7d"
EOT

mv /tmp/system.toml ${fluxroot}/etc/flux/system/conf.d/system.toml

printf "\n🐸 Broker Configuration\n"
cat ${fluxroot}/etc/flux/system/conf.d/system.toml

# If we are communicating via the flux uri this service needs to be started
chmod u+s ${fluxroot}/libexec/flux/flux-imp
chmod 4755 ${fluxroot}/libexec/flux/flux-imp
chmod 0644 /etc/flux/imp/conf.d/imp.toml
sudo chown -R ${fluxuser}:${fluxuser} ${fluxroot}/etc/flux/system/conf.d

cat << "PYTHON_DECODING_SCRIPT" > /tmp/convert_munge_key.py
#!/usr/bin/env python3

import sys
import base64

string = sys.argv[1]
dest = sys.argv[2]
encoded = string.encode('utf-8')
with open(dest, 'wb') as fd:
    fd.write(base64.b64decode(encoded))
PYTHON_DECODING_SCRIPT

cat << "PYTHON_DECODING_SCRIPT" > /tmp/convert_curve_cert.py
#!/usr/bin/env python3
import sys
import base64

string = sys.argv[1]
dest = sys.argv[2]
with open(dest, 'w') as fd:
    fd.write(base64.b64decode(string).decode('utf-8'))
PYTHON_DECODING_SCRIPT

mkdir -p /etc/munge
rm -rf /etc/munge/munge.key
python3 /tmp/convert_munge_key.py "MUNGEKEY" /etc/munge/munge.key
python3 /tmp/convert_curve_cert.py "CURVECERT" /tmp/curve.cert

chmod u=r,g=,o= /etc/munge/munge.key
chown munge:munge /etc/munge/munge.key

mv /tmp/curve.cert ${fluxroot}/etc/flux/system/curve.cert
chmod u=r,g=,o= ${fluxroot}/etc/flux/system/curve.cert
chown ${fluxuser}:${fluxuser} ${fluxroot}/etc/flux/system/curve.cert
service munge start > /dev/null 2>&1

# The rundir needs to be created first, and owned by user flux
# Along with the state directory and curve certificate
mkdir -p /run/flux
sudo chown -R ${fluxuser}:${fluxuser} /run/flux

# Remove group and other read
chmod o-r ${fluxroot}/etc/flux/system/curve.cert
chmod g-r ${fluxroot}/etc/flux/system/curve.cert
chown -R ${fluxuid} /run/flux ${STATE_DIR} ${fluxroot}/etc/flux/system/curve.cert

printf "\n✨ Curve certificate generated by helper pod\n"
cat ${fluxroot}/etc/flux/system/curve.cert

mkdir -p /etc/flux/manager

cat << "FIRST_BOOT_UNIT" > /etc/systemd/system/flux-start.service
[Unit]
Description=Flux message broker
Wants=munge.service

[Service]
Type=simple
NotifyAccess=main
TimeoutStopSec=90
KillMode=mixed
ExecStart=/bin/bash -c '/usr/bin/flux broker --config-path /usr/etc/flux/system/conf.d -Scron.directory=/usr/etc/flux/system/conf.d -Stbon.fanout=256  -Srundir=/run/flux -Sbroker.rc2_none -Sstatedir=/var/lib/flux -Slocal-uri=local:///run/flux/local -Stbon.connect_timeout=5s -Stbon.zmqdebug=1  -Slog-stderr-level=LOGLEVEL -Slog-stderr-mode=local'
SyslogIdentifier=flux
Restart=always
RestartSec=5s
RestartPreventExitStatus=42
SuccessExitStatus=42
User=flux
Group=flux
RuntimeDirectory=flux
RuntimeDirectoryMode=0755
StateDirectory=flux
StateDirectoryMode=0700
PermissionsStartOnly=true
Delegate=yes

[Install]
WantedBy=multi-user.target
FIRST_BOOT_UNIT

# This enables NFS
nfsmounts=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/nfs-mounts" -H "Metadata-Flavor: Google")

if [[ "X${nfsmounts}" != "X" ]]; then
    share=$(echo $nfsmounts | jq -r '.share')
    mountpoint=$(echo $nfsmounts | jq -r '.mountpoint')

    bash -c "sudo echo ${share} ${mountpoint} nfs defaults,hard,intr,_netdev 0 0 >> /etc/fstab"
    mount -a
fi

systemctl enable flux-start.service
systemctl start flux-start.service
