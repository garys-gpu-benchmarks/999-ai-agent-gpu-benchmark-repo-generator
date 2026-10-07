#!/usr/bin/env python3
# File: tests/test_amdgpu_reload.py
# Description: Stubbed tests for scripts/lib/amdgpu_reload.sh and the reload-or-reboot
#              branch of rocm_install_runtime (24.04 and 26.04). No real modprobe,
#              sysfs, or reboot is touched: commands are shell stubs on PATH and
#              sysfs is a temporary directory tree.
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "scripts" / "lib"
BASH = shutil.which("bash")

# Fake modprobe: unload removes /sys/module/amdgpu; load creates it plus one KFD GPU
# node per PCI GPU (or FAKE_KFD_NODES nodes). FAKE_UNLOAD=fail|hang, FAKE_LOAD=fail.
MODPROBE = r'''#!/usr/bin/env bash
echo "modprobe $*" >> "${FAKE_LOG}"
if [[ "$1" == "-r" ]]; then
  case "${FAKE_UNLOAD:-ok}" in
    fail) exit 1 ;;
    hang) sleep 8; exit 0 ;;
  esac
  rm -rf "${FAKE_SYS}/module/amdgpu" "${FAKE_SYS}/class/kfd/kfd/topology/nodes"
  exit 0
fi
[[ "${FAKE_LOAD:-ok}" == fail ]] && exit 1
mkdir -p "${FAKE_SYS}/module/amdgpu"
echo 0 > "${FAKE_SYS}/module/amdgpu/refcnt"
echo "${FAKE_LOADED_SRC:-AAA}" > "${FAKE_SYS}/module/amdgpu/srcversion"
mkdir -p "${FAKE_SYS}/class/kfd/kfd/topology/nodes/0"
echo "simd_count 0" > "${FAKE_SYS}/class/kfd/kfd/topology/nodes/0/properties"
for ((i = 1; i <= ${FAKE_KFD_NODES:-2}; i++)); do
  mkdir -p "${FAKE_SYS}/class/kfd/kfd/topology/nodes/${i}"
  printf 'cpu_cores_count 0\nsimd_count 1216\n' > "${FAKE_SYS}/class/kfd/kfd/topology/nodes/${i}/properties"
done
'''

MODINFO = r'''#!/usr/bin/env bash
if [[ "$1" == "-n" ]]; then echo "${FAKE_MODPATH:-/lib/modules/6.8.0-1-generic/updates/dkms/amdgpu.ko.zst}"; exit 0; fi
if [[ "$1" == "-F" && "$2" == "srcversion" ]]; then echo "${FAKE_DISK_SRC:-AAA}"; exit 0; fi
exit 0
'''

LOGGING_STUB = r'''#!/usr/bin/env bash
echo "$(basename "$0") $*" >> "${FAKE_LOG}"
'''


def _pci(sys_root: Path, count: int) -> None:
    for i in range(count):
        dev = sys_root / "bus" / "pci" / "devices" / f"0000:{i + 0x10:02x}:00.0"
        dev.mkdir(parents=True)
        (dev / "vendor").write_text("0x1002\n")
        (dev / "class").write_text("0x120000\n")
    audio = sys_root / "bus" / "pci" / "devices" / "0000:99:00.1"
    audio.mkdir(parents=True)
    (audio / "vendor").write_text("0x1002\n")
    (audio / "class").write_text("0x040300\n")


@unittest.skipIf(BASH is None or os.name == "nt", "needs Linux bash")
class AmdgpuReloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.sys = self.tmp / "sys"
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.log = self.tmp / "calls.log"
        self.log.write_text("")
        for name, body in {
            "modprobe": MODPROBE,
            "modinfo": MODINFO,
            "update-initramfs": LOGGING_STUB,
            "udevadm": LOGGING_STUB,
            "journalctl": "#!/usr/bin/env bash\nexit 0\n",
        }.items():
            path = self.bin / name
            path.write_text(body)
            path.chmod(0o755)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _loaded(self, refcnt: int = 0) -> None:
        mod = self.sys / "module" / "amdgpu"
        mod.mkdir(parents=True)
        (mod / "refcnt").write_text(f"{refcnt}\n")

    def _run(self, script: str, **env) -> subprocess.CompletedProcess:
        full_env = {
            **os.environ,
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "FAKE_SYS": str(self.sys),
            "FAKE_LOG": str(self.log),
            "_AMDGPU_RELOAD_SYS": str(self.sys),
            "AMDGPU_INIT_WAIT": "0",
            **env,
        }
        prelude = textwrap.dedent(f'''
            set -euo pipefail
            run_noninteractive_root() {{ while [[ "${{1:-}}" == *=* ]]; do shift; done; "$@"; }}
            source "{LIB / "amdgpu_reload.sh"}"
        ''')
        return subprocess.run([BASH, "-c", prelude + script], env=full_env,
                              capture_output=True, text=True, timeout=60)

    def _reload(self, mode: str, **env) -> int:
        result = self._run(f'if amdgpu_reload_instead_of_reboot {mode}; then echo RC=0; else echo RC=1; fi', **env)
        self.assertIn("RC=", result.stdout, result.stderr)
        return 0 if "RC=0" in result.stdout else 1

    def calls(self) -> str:
        return self.log.read_text()

    # ---- success paths -------------------------------------------------
    def test_firmware_reload_succeeds_when_all_gpus_return(self):
        _pci(self.sys, 2)
        self._loaded()
        self.assertEqual(self._reload("firmware"), 0)
        self.assertIn("modprobe -r amdgpu", self.calls())
        self.assertIn("modprobe amdgpu", self.calls())
        self.assertIn("update-initramfs -u", self.calls())

    def test_module_not_loaded_is_just_loaded(self):
        _pci(self.sys, 2)
        self.assertEqual(self._reload("firmware"), 0)
        self.assertNotIn("modprobe -r", self.calls())

    def test_dkms_reload_succeeds_when_dkms_module_is_running(self):
        _pci(self.sys, 2)
        self._loaded()
        self.assertEqual(self._reload("dkms"), 0)

    def test_partitioned_gpu_more_kfd_nodes_than_pci_is_ok(self):
        _pci(self.sys, 2)
        self._loaded()
        self.assertEqual(self._reload("firmware", FAKE_KFD_NODES="8"), 0)

    # ---- fall back to reboot -------------------------------------------
    def test_disabled_by_env(self):
        _pci(self.sys, 2)
        self._loaded()
        self.assertEqual(self._reload("firmware", ROCM_RELOAD_INSTEAD_OF_REBOOT="0"), 1)
        self.assertEqual(self.calls(), "")

    def test_no_amd_gpu_on_pci(self):
        _pci(self.sys, 0)
        self.assertEqual(self._reload("firmware"), 1)
        self.assertNotIn("modprobe", self.calls())

    def test_module_in_use(self):
        _pci(self.sys, 2)
        self._loaded(refcnt=3)
        self.assertEqual(self._reload("firmware"), 1)
        self.assertNotIn("modprobe", self.calls())

    def test_unload_fails(self):
        _pci(self.sys, 2)
        self._loaded()
        self.assertEqual(self._reload("firmware", FAKE_UNLOAD="fail"), 1)
        self.assertNotIn("modprobe amdgpu", self.calls())

    def test_unload_hangs_gives_up_at_deadline(self):
        _pci(self.sys, 2)
        self._loaded()
        self.assertEqual(self._reload("firmware", FAKE_UNLOAD="hang", AMDGPU_UNLOAD_TIMEOUT="2"), 1)

    def test_load_fails(self):
        _pci(self.sys, 2)
        self._loaded()
        self.assertEqual(self._reload("firmware", FAKE_LOAD="fail"), 1)

    def test_missing_gpu_after_reload(self):
        _pci(self.sys, 8)
        self._loaded()
        self.assertEqual(self._reload("firmware", FAKE_KFD_NODES="7"), 1)

    def test_dkms_not_built_skips_unload(self):
        _pci(self.sys, 2)
        self._loaded()
        self.assertEqual(self._reload("dkms", FAKE_MODPATH="/lib/modules/6.8.0-1-generic/kernel/drivers/gpu/drm/amd/amdgpu/amdgpu.ko.zst"), 1)
        self.assertNotIn("modprobe", self.calls())

    def test_dkms_loaded_module_is_not_the_dkms_build(self):
        _pci(self.sys, 2)
        self._loaded()
        self.assertEqual(self._reload("dkms", FAKE_LOADED_SRC="INBOX", FAKE_DISK_SRC="DKMS"), 1)


@unittest.skipIf(BASH is None or os.name == "nt", "needs Linux bash")
class RuntimeInstallBranchTests(unittest.TestCase):
    """rocm_install_runtime: reload success returns with no reboot; failure reboots at stage3."""

    def _run(self, lib: str, reload_rc: int) -> tuple[str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / "stage.env"
            script = textwrap.dedent(f'''
                set -euo pipefail
                cd "{tmp}"
                export ROCM_RUNTIME_STAGE_FILE="{stage}" REPO_ROOT="{tmp}"
                run_noninteractive_root() {{ while [[ "${{1:-}}" == *=* ]]; do shift; done; echo "ROOT $*" >> calls; }}
                wget() {{ touch "${{2}}"; }}
                apt-cache() {{ return 0; }}
                source <(tr -d '\\r' < "{LIB / lib}")
                amdgpu_reload_instead_of_reboot() {{ echo "RELOAD $1" >> calls; return {reload_rc}; }}
                rocm_install_runtime
                echo "STAGE=$( [[ -f "{stage}" ]] && cat "{stage}" | head -1 || echo none)"
                cat calls
            ''')
            result = subprocess.run([BASH, "-c", script], capture_output=True, text=True, timeout=60)
            return result.stdout, result.stderr

    def _check(self, lib: str, mode: str):
        out, err = self._run(lib, 0)
        self.assertIn(f"RELOAD {mode}", out, err)
        self.assertIn("STAGE=none", out)
        self.assertNotIn("ROOT reboot", out)
        self.assertIn("ROOT apt-get upgrade -y", out)
        self.assertNotIn("ROOT apt upgrade", out)

        out, err = self._run(lib, 1)
        self.assertIn(f"RELOAD {mode}", out, err)
        self.assertIn("STAGE=ROCM_RUNTIME_STAGE=stage3", out)
        self.assertIn("ROOT reboot", out)

    def test_24_04(self):
        self._check("rocm_install_24_04.sh", "dkms")

    def test_26_04(self):
        self._check("rocm_install_26_04.sh", "firmware")


if __name__ == "__main__":
    unittest.main()
