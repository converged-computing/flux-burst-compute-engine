# Flux Burst Example

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

Run the faux burst, using the defaults

```bash
$ python run-burst.py --project $GOOGLE_PROJECT
```
