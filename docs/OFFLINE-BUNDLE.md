# Offline bundle integrity prototype

`local-ai-bundle-check` validates an independently pinned manifest and its declared payloads. It never downloads missing files, executes content, installs software, or declares deployment readiness. The manifest schema is platform-neutral data; the payload reader is currently a POSIX development implementation and refuses Windows. Native Windows bundle verification is still pending.

This is a prerequisite for assembling an installer, not the one-command installer itself. No real model/runtime bundle is shipped, and no signing authority or trust anchor has been established.

## Manifest version 1

The bundle root contains `bundle-manifest.json` and exactly its declared payload files/directories. The JSON object has four fields:

| Field | Required value |
|---|---|
| `format_version` | Integer `1` |
| `bundle_id` | Bounded lowercase identifier using letters, digits, dots, underscores, and hyphens |
| `target` | `windows-amd64` |
| `artifacts` | 3–4096 artifact objects |

Each artifact has exactly `path`, `role`, `size`, `sha256`, `version`, `license`, and `source`. Paths use Windows-safe relative components; sizes are positive integers capped at 128 GiB per file; hashes are lowercase SHA-256 hex; version/license/source metadata is mandatory bounded text. Supported roles are `application`, `runtime`, `model`, `dependency`, `parser-model`, and `embedding-model`. At least one application, runtime, and model artifact must be present. These role/provenance fields are declarations, not evidence that software is compatible, licenses are approved, or the complete document workflow is included.

Unknown fields, duplicate JSON keys, unsafe device/stream/traversal paths, case aliases, duplicate payloads, and file/directory name conflicts are rejected. Future schema changes need a new explicit format version. There are no executable setup commands or remote-download directives in this format. Source metadata is never fetched.

## Development verification

After installing the source package in a POSIX development environment, run:

```sh
local-ai-bundle-check /absolute/path/to/bundle \
  --manifest-sha256 EXPECTED_SHA256_FROM_AN_INDEPENDENTLY_TRUSTED_CHANNEL
```

The placeholder must be replaced with an independently obtained 64-character lowercase manifest SHA-256. Computing that hash from the same untrusted bundle does not authenticate the bundle. A future production installer needs signature verification against an approved, independent trust anchor.

The verifier anchors directory/file opens to descriptors, refuses symbolic links/hard links/special files/cross-device content, rejects undeclared files and directories, and checks every payload's exact size and streaming digest. A corrupt or absent asset fails the whole check. No archive extraction or payload execution occurs.

Successful JSON includes the bundle ID, target, manifest hash, artifact/byte counts, and `payload_integrity_verified: true`. It always reports `signature_verified: false` and `deployment_ready: false`. Output does not include payload contents, prompts, operational documents, or host paths.

This check establishes bytes read during verification. It does not lock assets after return or authorize later execution. Production staging must copy and verify into protected installation storage and recheck identities before launch; a verified source bundle may change afterward. Missing dependencies, GPU fit, template/tool-call behavior, network isolation, rollback, reboot/resume, and signed trust are separate acceptance requirements.
