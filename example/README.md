# Flux Burst Example

**WARNING this mock example is not supported yet**

It needs to be refactored to use a simpler setup, and it's not a priority
since we mostly use this module for connected bursting.

This is an example that will perform a burst, however without a local cluster
we will just be running the burst as an isolated cluster. In the context of
a real burst we would provide a broker config (system.toml) that points back
to the host it bursted from. I made this example primarily to test interacting
with terraform from Python.

## Usage

Before running, be sure to export your `GOOGLE_APPLICATION_CREDENTIALS`

```bash
$ export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

You will need to build the basic set of images provided at
[flux-terraform-gcp](https://github.com/converged-computing/flux-terraform-gcp/tree/main/build-images/basic).
(the repository that hosts the terraform modules).

```bash
git clone https://github.com/converged-computing/flux-terraform-gcp
cd build-images/basic
# This will build images in compute, login, and manager
make
```

Note that you can run them separately in different terminals for a faster build.

```bash
make compute
make login
make manager
```

When the images are finished, run the faux burst, using the defaults

```bash
$ python run-burst.py --project $GOOGLE_PROJECT
```

This will create a setup on Compute Engine, an isolated cluster you
can login to, interact with, etc.
