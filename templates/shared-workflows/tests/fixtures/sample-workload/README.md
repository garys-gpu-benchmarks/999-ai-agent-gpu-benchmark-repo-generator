# Sample workload (self-test fixture)

The smallest repository that passes the reusable `ci.yml`. The Self-test
workflow runs `ci.yml` against this folder on every push to
`__CI_SHARED_REPO__`, so a change that would break the workload repositories
fails here first. It is not a benchmark and never runs on a GPU.
