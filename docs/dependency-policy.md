# Dependency policy

The benchmark matrix is authoritative for intentional direct dependencies. Generated repositories must install the union of:

1. Direct imports and executable requirements discovered from the implementation.
2. Framework and accelerator dependencies explicitly declared by the matrix or contributed by automatically discovered implementation components.

Transitive packages may be installed by a framework, but they must not be promoted to direct requirements without evidence that the workload imports or needs them. Unexpected packages should be reported as warnings rather than causing setup to fail.

For ROCm workloads, PyTorch, torchvision, ROCm, Python, GPU architecture, and framework versions form one tested compatibility tuple. Install torchvision only when the matrix/profile or implementation requires it. Set `BENCHMARK_INSTALL_TORCHVISION=1` and provide `TORCHVISION_INSTALL_SPEC` for vision workloads; leave it disabled for non-vision workloads.

Setup must verify the actual imports and native extensions used by the benchmark, record installed versions and indexes under `results/`, and refuse to write its completion marker when the tested tuple is not usable.
