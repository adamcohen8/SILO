# Install without downloading the repository first

The release builder now prepares a single command to paste into **native
64-bit Windows PowerShell, from any folder**. It uses Windows `curl.exe` to
download a versioned `install.ps1`, checks its exact SHA-256 through a held
read-only sharing handle, and keeps that handle through execution to deny
concurrent byte changes on Windows. The bootstrap downloads and verifies the source release
and calls `Install-Evaluation.ps1`, which supplies Python, dependencies and the
model and requires its existing native preflight before activation.

**There is no live anonymous installation URL yet.** The repository is private,
the installer PR is open, and these release assets have not been published.
The generated `INSTALL.md` contains the complete pasteable command once a
public release is approved and published. It requires no prior repository copy,
Git installation, GitHub account or existing Python on the target.

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
and the committed synthetic/metadata-only evaluation documents are included.
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
  --repository adamcohen8/local-ai-appliance \
  --tag evaluation-VERSION \
  --output bundles/evaluation-VERSION
```

Choose the actual public distribution repository through `--repository`; it
can differ from the private development repository. The output directory must
be new. Build does not make network requests, upload anything, create tags or
releases, change visibility, or run downloaded software.

Outputs are `install.ps1`, `local-ai-source-COMMIT.zip`, `release.json` with
their sizes/hashes and source revision, and `INSTALL.md` with the one-command
installation. They remain local and `published: false`. Publish the two actual
download assets and their metadata only after approval; publish the matching
command through the trusted distribution channel. Do not silently replace an
existing release/tag's assets. Regenerate pins after any signing or byte change.

Versioned asset URLs follow
[GitHub's documented release-download format](https://docs.github.com/en/repositories/releasing-projects-on-github/linking-to-releases).
Policy behavior follows
[Microsoft's execution-policy documentation](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies?view=powershell-5.1).

## Public repository decision

Anonymous GitHub release downloads require public distribution. Options are
to publish this existing repository or to create a clean public distribution
repository containing reviewed source/assets without the private development
history. Changing this repository's visibility would also expose its existing
commit metadata and GitHub discussions, including personal author email
metadata present in the history. Source ZIPs built here omit that Git metadata.
No repository visibility change or release publication is performed by these
tools. A clean public repository also needs an explicit project license decision;
this project currently has no top-level `LICENSE` file.

## Development evidence

Portable tests check the archive/manifest/command pins, repeatable generation,
no replacement of existing output, unsafe publication inputs, exact committed
snapshot behavior and exclusion of dirty/untracked files. A standalone bootstrap
test uses a synthetic inert installer and cached source ZIP, retaining the real
archive/hash/source-tree checks while mocking native path/ACL/Internet-zone
operations. Valid source reaches the inert installer, verified cache reuse
works, and a corrupted archive or changed cached script prevents invocation.
Native Windows curl, NTFS ACLs, Internet-zone behavior, signing and end-to-end
download/install acceptance remain untested by these portable checks.
