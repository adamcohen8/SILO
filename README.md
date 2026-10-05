# Local AI Appliance

A project to build a reproducible, one-command offline installation of a local AI document assistant for environments that handle Controlled Unclassified Information (CUI).

## Status

Planning stage. No installer or runtime has been implemented or validated. This repository does not establish authorization to process CUI.

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
