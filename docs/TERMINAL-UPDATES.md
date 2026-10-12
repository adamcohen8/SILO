# Terminal application updates

v0.1.0 is a manual-preparation evaluation release with no `update` metadata.
The updater therefore offers no v0.1.0 automatic migration from earlier active
installations. Protected managed enrollment and exact-release native startup
must be qualified separately. Use the release's `INSTALL.md` in a fresh approved
root. The channel design and earlier publication evidence below are historical;
publication alone does not enable a managed update route.

Earlier standalone evaluation terminals check the published stable SILO release
at startup and once per hour. When it finds a newer compatible release, the
status line shows **Update available — Ctrl+U to install**. Press **Ctrl+U**
with empty input and no active work to download, verify, install and restart.
The scrollback terminal has the same shortcut. `/update check` checks now;
`/update` installs the verified available update. Offline/failed checks say
**Unable to check for updates** and leave the application usable.

Launch an installed terminal with `Start-SILO-Terminal.cmd` at the installation
root. `--plain`, `--scrollback` and an explicitly supplied
`--required-policy-key-sha256` carry through an automatic restart. The desktop
continues to use its existing stable launcher; this feature adds no desktop
update notification.

Finish active requests and close the model menu first. Approve or discard
pending drafts, and review code artifacts before `/code-close`. Unsent input
is preserved and blocks the shortcut. A chat without an explicitly saved
project blocks installation until `/clear`; it is never silently retained.
Saved project state is persisted before shutdown and the active saved project
is reopened with the existing identity and source checks after restart.

## Installation and recovery

The existing host downloads a bounded source ZIP into private
`state/updates/u-ID` storage. It verifies GitHub's asset SHA-256, the complete
source manifest and every source file before accepting the handoff. The
terminal then closes owned workers, the GPU session and the project vault.
Its existing interpreter starts a separate updater window, which waits for
the original host process to exit and rechecks the published release and
staged bytes before executing the verified installer source.

The updater holds the same share-denied installation lock as the manual
installer. It prepares a separate application/runtime/interpreter payload,
reserving the session slot during preparation and activation. Native preflight
checks the currently selected model against current policy and verifies
synthetic text/PDF/DOCX behavior and process cleanup. With no selected model,
the parser/host checks run and inference/GPU checks are explicitly marked not
applicable. The updater does not reinstall a removed default model or alter
the model selection, retained projects, instructions, workflows or settings.
Application state is reserved from model folder grants.

Only successful native preflight permits activation. The previous payload and
`active.previous.json` are kept; ordinary preparation/preflight failures leave
the active version unchanged and attempt to reopen it. Activation or restart
launch failures restore the previous active record and launchers. A launch
success means process creation succeeded; the restarted terminal must still
reach Ready. Power loss/crashes require inspecting active/previous records and
the existing manual installer recovery procedure. The updater never deletes
old versions or incomplete transactions automatically.

Each claimed transaction is single-use. `result.json` records its outcome and
`native-preflight.json` preserves the successful preflight receipt. Failed
staging and preparation are retained for local inspection. Keep all private
state, raw receipts and machine paths out of GitHub. A changed active version
or published asset stops the update rather than guessing or replacing another
installation. Release-bound code acceptance is not carried to a new release.

## Release channel and trust

This evaluation updater trusts HTTPS to the fixed public
`adamcohen8/SILO` GitHub API. It requires GitHub's independently fetched asset
digests for `release.json` and the source ZIP, and exact matching pins inside
the metadata. Drafts, prereleases, missing digests, changed bytes, unsafe
archives, undeclared files and incompatible identities are denied. Requests
send no prompts, documents, project state, credentials or model-selected URLs.
Only the host checks/downloads updates; contained AI workers gain no network
access. GitHub's asset digest is documented in the
[release assets API](https://docs.github.com/en/rest/releases/assets).

This is the existing unsigned evaluation distribution, not independently
organization-signed software or CUI qualification. It does not change
PowerShell execution policy or invoke downloaded PowerShell scripts. The
existing GUI/manual installer script-policy requirements still apply.

A release owner must build from an exact reviewed commit containing this
updater and supply a positive, increasing integer sequence:

```shell
python scripts/build_evaluation_release.py \
  --revision EXACT_40_CHARACTER_COMMIT \
  --repository adamcohen8/SILO --tag evaluation-VERSION \
  --update-sequence INCREASING_INTEGER --output bundles/evaluation-VERSION
```

The builder injects `profiles/release-origin.json` into the source manifest
and sets matching `update` metadata in `release.json`. Sequence zero (the
default) creates a manual-bootstrap-only release. A current sequence must
increase and the source commit must differ; tags are not compared as version
strings. Existing legacy releases without this metadata are not automatic
update candidates. The historical 10 October 2026 installer lacks the updater;
the 11 October releases introduced that channel.
The first channel release, `evaluation-2026.10.11-silo.1`, binds commit
`f018f0d62f2baefaebf71c947b1bf8678ca9369f` and sequence 1. Release 2,
`evaluation-2026.10.11-silo.2`, binds merged commit
`f7995d48cdbfecc15145e2e91f2d1ddb6dd80e68` and sequence 2, including the Windows
redirected-input and legacy-output fixes. The historical release,
`evaluation-2026.10.11-silo.3`, binds merged commit
`e3da3c10b96120744c130236f9e62bba83d033d3` and sequence 3, adding bounded named-draft
and exact-citation completion checks plus neighboring text-search lines.
Before v0.1.0 became latest, sequence-1 and sequence-2 installations could discover sequence 3 with
`/update check` and install with Ctrl+U while idle with empty input. v0.1.0 has no channel metadata and is not offered as an update.

The published sequence-2-to-sequence-3 pair is available for native update testing.
Anonymous asset integrity and production updater discovery from both earlier
identities were verified; the complete native interactive handoff, restart and
rollback matrix remains pending. Follow the current repository `test_plan.md`
and record exact source/release identities. Actual Muse/GPT-OSS retests remain
pending for the newly published fixes.

Asset generation, merging source and opening a PR do not publish a release.
An explicitly authorized release must upload its exact source/metadata bytes
and become GitHub's latest stable release. Verify the API digests and anonymous
downloads before use. Do not mutate the pinned source/archive/metadata after
publication. Native end-to-end Windows update and rollback evidence remain
required; portable fixture tests do not establish those results.
