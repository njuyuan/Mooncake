# AGENTS.md

## `docs/` Directory Changes

- Before modifying files under `docs/`, read `docs/AGENTS.md`.

## Pull Request Guidelines

- Follow `CONTRIBUTING.md` for PR title prefixes, RFC expectations, and
  contribution workflow.
- Before opening a PR for nontrivial work, check whether an existing issue or
  open PR already covers the same change. If the work overlaps, explain the
  difference instead of duplicating it.
- Do not open low-value busywork PRs for isolated typo, style, or mechanical
  changes unless they are part of a substantive requested change.
- Use `.github/pull_request_template.md` when preparing a PR, and fill in the
  relevant sections for description, module, type of change, testing,
  checklist, and AI assistance disclosure.
- For AI-assisted changes, make sure the human submitter has reviewed every
  changed line and can defend the change end-to-end.
- Before handoff, run pre-commit on the files touched by the change when the
  toolchain is available (see `CONTRIBUTING.md` for the PR-scoped
  `pre-commit run --files ...` command). Do not use
  `pre-commit run --all-files` for routine PRs; if it rewrites unrelated
  files, leave those edits out of the PR.
- Keep PRs lean: review `git diff` before staging, and include only changes
  required for the requested task.

## Cursor Cloud specific instructions

The Cloud VM is **CPU-only, no RDMA NIC, no etcd** (4 CPUs / ~15 GB RAM). System
deps are already installed via `dependencies.sh` (Go at `/usr/local/go`,
yalantinglibs installed system-wide). The project is prebuilt in `build/` and the
non-CUDA wheel is installed in `.venv` (CLIs `mooncake_master`,
`transfer_engine_bench`, `mooncake_http_metadata_server`).

- **C++ compiler gotcha:** the base image's `c++`/`cc` alternatives point to a
  clang that cannot link `libstdc++`, which breaks CMake's default compiler
  detection (`cannot find -lstdc++`). They have been repointed to GCC. If a fresh
  build hits that error, re-run
  `sudo update-alternatives --set c++ /usr/bin/g++ && sudo update-alternatives --set cc /usr/bin/gcc`.
- **Build with `-j2`, not `-j$(nproc)`** — heavy template files (yalantinglibs /
  async_simple) OOM-kill `cc1plus` at `-j4` on 15 GB RAM.
- Configure TCP-only: `-DUSE_CUDA=OFF -DUSE_ETCD=OFF -DSTORE_USE_ETCD=OFF -DWITH_EP=OFF`.
- Runtime needs `/usr/local/go/bin` on `PATH` and
  `build/mooncake-common:/usr/local/lib` on `LD_LIBRARY_PATH`; force TCP with
  `MC_FORCE_TCP=true` and use `metadata_server=P2PHANDSHAKE` (no etcd) — see
  `docs/source/getting_started/quick-start.md`.
- Store demo: start `mooncake_master`, then `MooncakeDistributedStore().setup(...,
  protocol="tcp", ...)` and `put`/`get`.
- Lint: `clang-format-20` (used by the C/C++ format hook) is not installed; the
  `ruff` hook rewrites files repo-wide, so revert unrelated edits before staging.
