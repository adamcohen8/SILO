# Local AI Appliance

A project to build a reproducible, one-command offline installation of a local AI document assistant for environments that handle Controlled Unclassified Information (CUI).

## Status

Development prototype. A POSIX folder-permission broker, native folder workspace, reviewed draft-copy workflow, and read-only Windows target inspection script are implemented. The Windows filesystem adapter, model integration, PDF/Word ingestion, network isolation, signed bundle, and one-command installer are not implemented or qualified. This repository does not establish authorization to process CUI.

The [desktop preview](docs/DESKTOP-PREVIEW.md) supports explicit folder selection/drop, text preview, draft differences, and user-approved saves as new files. It currently runs on macOS with public/synthetic text and has no AI generation.

## Accepted first-version requirements

- One local user on the unit's Windows workstation.
- No document access by default. The user selects or drops folders into **read-only** or **editable** categories through a trusted local interface.
- Read-only grants permit document access but no modification. Editable grants permit reading and creating documents; existing-file changes require a user-reviewed edit workflow.
- The model cannot grant itself access or write documents outside editable folders.
- No shell or generated-code execution in this iteration. Coding assistance can be added later.
- Administrator installation and required Windows feature changes/reboots are allowed.
- Development takes place on macOS. No Windows test computer is currently available; on-target Windows/GPU/isolation evidence is required before deployment claims.

See [architecture and decisions](docs/ARCHITECTURE.md) and [target validation](docs/TARGET-VALIDATION.md).

## Goals

- Install from a signed, versioned offline bundle with pinned dependencies and model hashes.
- Prevent external communications by the AI stack while preserving the host computer's permitted connectivity.
- Search, compare, and draft from local documents with verifiable document and page citations.
- Support replaceable models and inference runtimes through a common local interface and tested model profiles.
- Produce installation, configuration, isolation, and functional test evidence.

The long-term aspiration is to contribute to or integrate with GenAI.mil. This is an independent project with no current affiliation, endorsement, or integration.

## First hardware target

- Windows 11 Pro 25H2
- Intel Core i9-14900KF
- NVIDIA GeForce RTX 4090, 24 GB VRAM
- 64 GB system RAM
- Approximately 1 TB storage

Nemotron 3 Nano 30B-A3B and LangGraph are initial candidates. Quantization, inference runtime, and the isolation architecture remain subject to testing. WSL2 is a potential GPU runtime, not a security sandbox.

## Storage and development boundaries

This repository contains source code, configuration templates, manifests, documentation, and public or synthetic test fixtures only.

Do not commit CUI, operational documents, extracted text, embeddings or indexes derived from CUI, user conversations, sensitive logs, credentials, or private signing keys. Do not include those materials in GitHub issues, pull requests, attachments, or build outputs.

Model weights, dependencies, and full installation bundles belong in separate artifact storage. The repository should record their versions, licenses, provenance, and hashes. Deployed data and backups belong within the organization's authorized storage boundary.

The installed AI must not require GitHub connectivity or GitHub credentials.

## First milestone

Use public or synthetic data on the target workstation to demonstrate GPU inference, blocked external communications across the complete application, retained host connectivity, and document answers with valid citations. Package the verified configuration only after those results are established.

## Development checks

The current folder adapter is POSIX-only and deliberately refuses Windows access until a native Windows implementation is available.

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

This verifies folder-tool behavior only. It does not test inference, a Windows installation, or network isolation.
