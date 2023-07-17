# Flux Burst Example

This is an example that will perform an isolated burst, meaning we create an entirely
separate cluster. In the context of a real burst we would provide a broker config (system.toml) that points back
to the host it bursted from. You can see a connected burst example [alongside the flux operator](https://github.com/flux-framework/flux-operator/tree/main/examples/experimental/bursting/broker-compute-engine).
I made this example primarily to test interacting with terraform from Python.

## Usage

Before running, be sure to export your `GOOGLE_APPLICATION_CREDENTIALS`

```bash
$ export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

You will need to build the base image "burst" provided at
[flux-terraform-gcp](https://github.com/converged-computing/flux-terraform-gcp/tree/main/build-images/bursted).
(the repository that hosts the terraform modules).

```bash
git clone https://github.com/converged-computing/flux-terraform-gcp
cd build-images/bursted
make
```

When the images are finished, run the faux burst, using the defaults

```bash
$ python run-burst.py --project $GOOGLE_PROJECT
```

This will create a setup on Compute Engine, an isolated cluster you
can login to, interact with, etc. You can typically get the ssh command from
the google cloud console:

```bash
gcloud compute ssh gffw-compute-a-001 --zone us-central1-a
```

If you need to debug, you can check the startup scripts to make sure that everything finished.

```bash
sudo journalctl -u google-startup-scripts.service
```

That's also helpful to ensure the startup scripts finish! You sometimes cannot connect to the broker right away.
And then you should be able to interact with Flux!

```bash
$ flux resource list
     STATE NNODES   NCORES NODELIST
      free      3       12 gffw-compute-a-[001-004]
 allocated      0        0
      down      0        0
```

Try running a job across workers:

```bash
$ flux run --cwd /tmp -N 4 hostname
```
```
gffw-compute-a-001
gffw-compute-a-004
gffw-compute-a-002
gffw-compute-a-003
```

And that's it! You can press enter in the other terminal to bring everything down.
