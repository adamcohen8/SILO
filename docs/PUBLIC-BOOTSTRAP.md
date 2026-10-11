# Install without downloading the repository first

The release builder now prepares a single command to paste into **native
64-bit Windows PowerShell, from any folder**. It uses Windows `curl.exe` to
download a versioned `install.ps1`, checks its exact SHA-256 through a held
read-only sharing handle, and keeps that handle through execution to deny
concurrent byte changes on Windows. The bootstrap downloads and verifies the source release
and calls `Install-Evaluation.ps1`, which supplies Python, dependencies and the
model and requires its existing native preflight before activation.

The [SILO evaluation release](https://github.com/adamcohen8/SILO/releases/tag/evaluation-2026.10.11-silo.3) is published, and all four download assets are available without a GitHub login. Copy the complete command from the repository README, release notes or downloadable [INSTALL.md](https://github.com/adamcohen8/SILO/releases/download/evaluation-2026.10.11-silo.3/INSTALL.md). It requires no prior repository copy, Git installation, GitHub account or existing Python on the target.

The release binds source commit `e3da3c10b96120744c130236f9e62bba83d033d3` and update sequence 3. It includes the Windows fixes, six-model catalog, model menu, saved-project features and terminal updater, plus PR #19's bounded checks for named draft proposals and exact citations and neighboring text-search lines. Sequence-1 and sequence-2 installations can discover this release through `/update check` and install with Ctrl+U. It remains an unsigned public/synthetic evaluation; actual model retests, native acceptance of this exact release including terminal update/restart, and CUI authorization remain pending.

The command is release-specific. It does not execute a moving branch or pipe
downloaded text into `Invoke-Expression`. Its bootstrap hash is embedded in the
command, and the bootstrap embeds the source archive's size/hash and the exact
source manifest hash. Repository access over HTTPS and the trusted channel
providing that command are the initial trust assumptions. These hashes are
integrity checks; this unsigned evaluation does not provide publisher signing.

## Source preparation and verification

`scripts/build_evaluation_release.py` reads an exact 40-character Git commit,
not the current filesystem contents. Dirty/untracked files, Git history,
author metadata, local settings, models, wheels and credentials are omitted.
Unexpected tracked file categories, Git links/submodules, Windows path aliases
and oversized source snapshots are rejected. Ordinary reviewed source files
and the committed synthetic/metadata-only evaluation documents are included,
along with the two explicitly reviewed SILO branding assets (`silo.png` and `silo.ico`).
Allowed extensions are not a sensitive-content classifier; publication still
requires review of the actual source and repository material.

The generated source ZIP contains a complete payload inventory. The bootstrap
creates private user-owned NTFS storage under the installation root, holds an
exclusive source-operation lock, and verifies the cached ZIP on every run.
It hashes through the same read handle used for extraction, verifies every
extracted file and rejects undeclared/missing/changed files before invoking
the installer. Cached source is rechecked before reuse. Partial downloads and
incomplete source transactions are retained for inspection; existing source
copies are not overwritten. Model/asset caches keep their existing resume and
offline behavior. The initial source bootstrap itself requires connectivity.

The bootstrap follows only HTTPS redirects. After source verification it marks
downloaded PowerShell files as Internet-zone files, preserving unsigned-script
restrictions. The curl command also marks the downloaded bootstrap this way.
It does not alter execution policy, remove those markers, or use bypass flags.
If the approved organizational process requires signed scripts, this unsigned
evaluation release will be blocked until that requirement is satisfied. The
same native Windows/CUI acceptance limits apply as in
[EVALUATION-INSTALLER.md](EVALUATION-INSTALLER.md).

## Build reviewable assets

On the maintainer's build computer, after committing/reviewing source:

```shell
python scripts/build_evaluation_release.py \
  --revision EXACT_40_CHARACTER_COMMIT \
  --repository adamcohen8/SILO \
  --tag evaluation-VERSION \
  --output bundles/evaluation-VERSION
```

Choose the actual public distribution repository through `--repository`; it
can differ from the private development repository. The output directory must
be new. Build does not make network requests, upload anything, create tags or
releases, change visibility, or run downloaded software.

Outputs are `install.ps1`, `local-ai-source-COMMIT.zip`, `release.json` with
their sizes/hashes and source revision, and `INSTALL.md` with the one-command
installation. The builder outputs remain local with `published: false`. During an authorized
publication, update the distribution metadata and instructions to reflect the
published release without changing the pinned bootstrap or source bytes. Publish
the two actual download assets and their metadata, then verify anonymous download
bytes and the tagged source revision. Publish the matching command through the
trusted distribution channel. Do not silently replace an
existing release/tag's assets. Regenerate pins after any signing or byte change.

For the terminal update channel, add `--update-sequence` with a positive,
increasing integer when building SILO source that contains the updater. This
binds generated release identity into the source manifest. The default zero
is manual-bootstrap-only; publication and native validation remain separate.
See [terminal update distribution and recovery](TERMINAL-UPDATES.md).

Versioned asset URLs follow
[GitHub's documented release-download format](https://docs.github.com/en/repositories/releasing-projects-on-github/linking-to-releases).
Policy behavior follows
[Microsoft's execution-policy documentation](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies?view=powershell-5.1).

## Public repository

The existing repository was renamed to **SILO** and made public with the owner's
approval. Its source and existing Git history are public; generated source ZIPs
omit Git history and author metadata. Existing repository links redirect to SILO.
The versioned evaluation assets are now published separately; repository
visibility and publication do not establish native Windows or CUI qualification.
No repository visibility change or release publication is performed by these
tools. A clean public repository also needs an explicit project license decision;
this project currently has no top-level `LICENSE` file.

## Development evidence

### 11 October 2026 release 3 publication verification

The current release, `evaluation-2026.10.11-silo.3`, binds merged source
`e3da3c10b96120744c130236f9e62bba83d033d3` and update sequence 3. All four assets were
downloaded anonymously and matched local prepared bytes and GitHub API sizes
and SHA-256 digests. The tag resolved to that exact commit; all 230 source
inventory files matched committed bytes plus the generated release identity.
The bootstrap parsed without PowerShell syntax errors. The merged code passed
389 checks with 169 skips and zero failures/errors (558 executions).

The production updater discovered sequence 3 from both published earlier
identities and a source installation without release identity, and offered no
update from sequence 3. Distribution and discovery are verified; actual
Muse/GPT-OSS retests and the native interactive update/rollback matrix remain
pending. Use current main's `test_plan.md`; immutable source ZIPs preserve their
original documentation snapshot.

| Asset | SHA-256 |
| --- | --- |
| `INSTALL.md` | `b7a6e168372dbffb01fe9231a680e034acaaaafe12f13fd8d509d67db825f05c` |
| `install.ps1` | `4e43dab5186bbfe3a39336093358397aa1298163a6b18c4768a93d13c977b75e` |
| `local-ai-source-e3da3c10b96120744c130236f9e62bba83d033d3.zip` | `36c90656f3407f71c0461184420cd97ce55c4f3001879da642305edafa624c27` |
| `release.json` | `ef255b9969299e034d601c675c0822699617200a07ba24dcf1f50971998fb883` |

Source manifest SHA-256:
`d85f1ee22f06addfef91c58edd781490478bb4eb5386cb9f831bb0bc0e2b92a3`.

### 11 October 2026 release 2 publication verification (historical)

The earlier release, `evaluation-2026.10.11-silo.2`, binds merged source
`f7995d48cdbfecc15145e2e91f2d1ddb6dd80e68` and update sequence 2. All four
published assets were downloaded anonymously. Their sizes and SHA-256 hashes
matched both local prepared assets and GitHub's API digests. The tag resolved
to that exact commit; all 228 source inventory files matched committed bytes
plus the generated release identity. The bootstrap parsed without PowerShell
syntax errors.

The production updater discovered sequence 2 from the published sequence-1
identity and from a source installation without release identity. It offered
no update from sequence 2. These checks establish distribution and discovery;
the complete native interactive published-pair update/rollback matrix remains
pending. The merged Windows report records its separately bound native tests
and preserved failures.

| Asset | SHA-256 |
| --- | --- |
| `install.ps1` | `bc810719bf82abf701e3c9cf4470f0530d9b3d2e3ef91fd1058870824ba40356` |
| `local-ai-source-f7995d48cdbfecc15145e2e91f2d1ddb6dd80e68.zip` | `4fbac7bcfe8dfb0f450c6d09b4778760d8fcb37bc55a760b4a165f86c8892e1d` |
| `release.json` | `2f7b8817652f2ddef77b044c4ea9249794863b83ecdfce4cabdb84a321bd6888` |
| `INSTALL.md` | `5e3f5f33134963a3c538924b142f662a8ad5ed23f6c0fe892f18751f7a93665c` |

Source manifest SHA-256:
`afc68c34e5c5a4c7e453c43b0714e61f25737f09e866fede0eefa514994306b3`.

### 11 October 2026 release 1 publication verification (historical)

The new release's four assets were downloaded anonymously after publication.
Each size and SHA-256 matched both the prepared local asset and GitHub's API
digest. The tag resolved to `f018f0d62f2baefaebf71c947b1bf8678ca9369f`;
the extracted source inventory and manifest were reverified. The real updater
discovered sequence 1 from a source installation without release identity and
offered no update when supplied this release's current identity.

| Asset | SHA-256 |
| --- | --- |
| `install.ps1` | `7d631a5ed917a7f4c5a8915c6d9dd22330697d212f9f42cb33b44b9f4a8a3b1d` |
| `local-ai-source-f018f0d62f2baefaebf71c947b1bf8678ca9369f.zip` | `a7f63174d0e5c61070a1b1f2b93a4b9a9db3c4c9bc68edcbf8ce8e58fffcd0c1` |
| `release.json` | `f664c2a7b25231d67d0c16e6e485763f8bf205550f2b75aa2a42ef33a253545b` |
| `INSTALL.md` | `3de053aa5436c6987be7bdbd580a22b7534cec76a14590fcf407d217adcd8704` |

Source manifest SHA-256:
`49bd1b24fb0fde9eb1bef7177835db23ce6f5fad8a31cb36d611300527768356`.
The generated bootstrap parsed without PowerShell syntax errors. Publication,
download integrity and portable checks do not establish native Windows update,
restart/rollback or CUI acceptance for this release.

### Portable development checks

Portable tests check the archive/manifest/command pins, repeatable generation,
no replacement of existing output, unsafe publication inputs, exact committed
snapshot behavior and exclusion of dirty/untracked files. A standalone bootstrap
test uses a synthetic inert installer and cached source ZIP, retaining the real
archive/hash/source-tree checks while mocking native path/ACL/Internet-zone
operations. Valid source reaches the inert installer, verified cache reuse
works, and a corrupted archive or changed cached script prevents invocation.
Native Windows curl, NTFS ACLs, Internet-zone behavior, signing and end-to-end
download/install acceptance remain untested by these portable checks.
