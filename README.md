# Flux Burst Plugin for Compute Engine

This is an example implementation for an external bursting plugin for Flux.
For instructions, see the [main flux-burst repository](https://github.com/converged-computing/flux-burst).
Tutorials are available under the [flux operator](https://github.com/flux-framework/flux-operator/tree/main/examples/experimental/bursting)

![https://raw.githubusercontent.com/converged-computing/flux-burst/main/docs/assets/img/logo.png](https://raw.githubusercontent.com/converged-computing/flux-burst/main/docs/assets/img/logo.png)

## Usage

 - This plugin requires *terraform* to be installed.
 - For a bursted cluster (connecting one broker to another) you can use build [these images](https://github.com/converged-computing/flux-terraform-gcp/tree/main/build-images/bursted) with `make`.
 - See the [example alongside the Flux Operator](https://github.com/flux-framework/flux-operator/tree/main/examples/experimental/bursting/broker-compute-engine) for bursting from GKE to Compute Engine.
 - Isolated bursts are not fully supported yet - the image needs to be refactored for it!

If you are connecting clusters, they need to be compatible! See [the notes here](https://gist.github.com/vsoch/1801ffcba1eda5ca6ea65e03f9b5fa6c).

## TODO

 - We likely want to be able to handle different operating systems - right now the burst is setup for Rocky Linux.

## License

HPCIC DevTools is distributed under the terms of the MIT license.
All new contributions must be made under this license.

See [LICENSE](https://github.com/converged-computing/flux-burst/blob/main/LICENSE),
[COPYRIGHT](https://github.com/converged-computing/flux-burst/blob/main/COPYRIGHT), and
[NOTICE](https://github.com/converged-computing/flux-burst/blob/main/NOTICE) for details.

SPDX-License-Identifier: (MIT)

LLNL-CODE- 842614
