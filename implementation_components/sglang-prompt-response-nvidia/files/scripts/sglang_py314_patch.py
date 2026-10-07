"""Python 3.14 compatibility for SGLang 0.5.10 + torch 2.9.1.

torch.compile is unsupported on 3.14. Piecewise CUDA graphs import
torch._inductor, which then fails on typing.Union.__module__.
"""
from __future__ import annotations

import ast
import importlib.abc
import sys

# Triton 3.5 still walks the pre-3.14 AST node names.
if not hasattr(ast, "Num"):
    ast.Num = ast.Constant
if not hasattr(ast, "Str"):
    ast.Str = ast.Constant
if not hasattr(ast, "Bytes"):
    ast.Bytes = ast.Constant
if not hasattr(ast, "NameConstant"):
    ast.NameConstant = ast.Constant
if not hasattr(ast, "Ellipsis"):
    ast.Ellipsis = ast.Constant

try:
    import torch

    def _noop_compile(fn=None, *args, **kwargs):
        if callable(fn):
            return fn

        def decorator(func):
            return func

        return decorator

    torch.compile = _noop_compile

    # sglang 0.5.10 registers a fake for sgl_kernel::moe_fused_gate at import.
    # Kernel 0.4.6.post1 loads on torch 2.13 and does not define that op.
    # Mistral bf16 does not call it; the name only has to exist so launch_server imports.
    try:
        torch.ops.sgl_kernel.moe_fused_gate
    except Exception:
        torch.library.define(
            "sgl_kernel::moe_fused_gate",
            "(Tensor input_tensor, Tensor bias, int num_expert_group, int topk_group, "
            "int topk, int num_fused_shared_experts=0, float routed_scaling_factor=0.0, "
            "bool apply_routed_scaling_factor_on_output=False) -> (Tensor, Tensor)",
        )
except Exception:
    pass

try:
    import sgl_kernel

    # sglang 0.5.10 imports kernel 0.4.1 names. Kernel 0.4.6.post1 matches
    # torch 2.13 and loads, but renamed fp8_blockwise_scaled_mm.
    if not hasattr(sgl_kernel, "fp8_blockwise_scaled_mm") and hasattr(
        sgl_kernel, "fp8_blockwise_scaled_grouped_mm"
    ):
        sgl_kernel.fp8_blockwise_scaled_mm = sgl_kernel.fp8_blockwise_scaled_grouped_mm

    def _sgl_kernel_missing(name):
        if name.startswith("_"):
            raise AttributeError(name)

        def _stub(*_args, **_kwargs):
            raise RuntimeError(f"sgl_kernel has no {name} in this build")

        setattr(sgl_kernel, name, _stub)
        return _stub

    sgl_kernel.__getattr__ = _sgl_kernel_missing
except Exception:
    pass


def _patch_server_args(module) -> None:
    cls = getattr(module, "ServerArgs", None)
    if cls is None:
        return
    orig = getattr(cls, "_handle_piecewise_cuda_graph", None)
    if orig is None or getattr(orig, "_sglang_py314", False):
        return

    def wrapped(self):
        orig(self)
        if not getattr(self, "enforce_piecewise_cuda_graph", False):
            self.disable_piecewise_cuda_graph = True

    wrapped._sglang_py314 = True
    cls._handle_piecewise_cuda_graph = wrapped


class _Loader(importlib.abc.Loader):
    def __init__(self, real):
        self.real = real

    def create_module(self, spec):
        if hasattr(self.real, "create_module"):
            return self.real.create_module(spec)
        return None

    def exec_module(self, module):
        self.real.exec_module(module)
        _patch_server_args(module)


class _Finder:
    def find_spec(self, fullname, path=None, target=None):
        if fullname != "sglang.srt.server_args":
            return None
        for finder in sys.meta_path:
            if finder is self:
                continue
            find_spec = getattr(finder, "find_spec", None)
            if find_spec is None:
                continue
            spec = find_spec(fullname, path, target)
            if spec is not None and spec.loader is not None:
                spec.loader = _Loader(spec.loader)
                return spec
        return None


sys.meta_path.insert(0, _Finder())
if "sglang.srt.server_args" in sys.modules:
    _patch_server_args(sys.modules["sglang.srt.server_args"])
