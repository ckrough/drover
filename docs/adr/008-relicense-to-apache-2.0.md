# ADR-008: Relicense Drover from AGPL-3.0 to Apache-2.0

## Status

Accepted (2026-06-09). Supersedes the AGPL-3.0 posture for this repository.

## Context

Drover shipped under AGPL-3.0-or-later, chosen under a now-retired policy that
assigned network copyleft to any code that could be operated as a service.
Drover is a locally-run CLI: it executes on the user's machine, classifies
local files, and (by default) talks only to a local Ollama instance. The
network-copyleft protection AGPL provides guards nothing the project depends on,
while the copyleft obligation discourages the enterprise and embedded adoption
that drives the project's actual return.

Backchain LLC and Chris Krough have committed to true, OSI-compliant open source
under a single permissive license across every repository. Attribution is the
return: wide adoption of a permissive tool produces the employer signal (Chris
Krough, personal brand) and business inbound (Backchain) that the project is
published to generate.

A unilateral relicense is only valid if the copyright holder owns all the code.
`git shortlog -sne --all` shows every commit authored by Chris Krough, the
AI-assist bot operating on his behalf, or the CI release bot. There are no
outside contributors, and Backchain LLC holds copyright on all code.

## Decision

Relicense Drover to the Apache License 2.0 (Apache-2.0). This applies to the
entire repository regardless of artifact class.

- Copyright holder (legal attribution): Backchain LLC, in `LICENSE`, `NOTICE`,
  and the recommended per-file source header.
- Author identity (employer signal): Chris Krough, in the package manifest
  `authors`/`maintainers` and `CITATION.cff`.
- No AGPL, no copyleft, no commercial license, no dual licensing, no CLA, and no
  DCO. The public license is the license.

New source files carry the standard Apache header
(`Copyright 2025 Backchain LLC` + `SPDX-License-Identifier: Apache-2.0`).
Existing files are not retrofitted.

## Consequences

- `LICENSE`, `pyproject.toml` SPDX, `README`, `CONTRIBUTING`, and `NOTICE` all
  name Apache-2.0 with no internal contradiction. GitHub re-detects the license
  as `apache-2.0` after the change lands.
- Downstream users may incorporate Drover into closed and commercial systems
  without the AGPL service-distribution obligation.
- The retired AGPL-for-services rule in the workspace's `repo-licensing.md` is
  updated separately to "Apache-2.0 for all repositories" (tracked outside this
  repo).
- The relicense is one-way in practice: code released under Apache-2.0 stays
  available under those terms.
