# Target session results checklist

Use public/synthetic data only. Store detailed evidence within approved local storage. The following is a metadata-only template; no field represents a pass until observed. Stop dependent tests when prerequisites fail.

| Check | Initial status | Record |
|---|---|---|
| Kit archive/manifest | Not run | Trusted expected SHA-256, source revision, integrity result |
| Approved Python/PowerShell execution | Not run | Python architecture/version; script execution permitted/unavailable |
| Inventory | Not run | Windows build, GPU/VRAM, driver, RAM, optional-feature state; unknown stays unknown |
| Existing WSL workloads/configuration | Not run | Counts/config presence only; preserve unrelated workloads |
| Native folders | Not run | 14 tests, failures/errors/skips; any skip is not acceptance |
| Native ACL/staging | Not run | Six tests, failures/errors/skips; no real install |
| Optional document parsers | Not run | Nine parser tests; missing wheels/env or any failure is not acceptance |
| PowerShell wrapper | Not run | Plan and synthetic Stage/Status/Rollback only if approved; exact readiness false |
| Runtime/model assets | Not run | Approved acquisition, licenses, exact binaries/DLLs/model/template hashes |
| GPU fit and latency | Not run | Profile identity, peak memory, load time, latency, OOM/truncation behavior |
| Real LangGraph tools/citations | Not run | Granted sources only, injection denial, correct locators, reviewed copies |
| Full-stack isolation | Not run | N01–N09 and I01–I02 from isolation matrix; effective enforcement evidence |
| Retained host connectivity | Not run | H01 before/during/after; approved responder host control |
| Reboot/resume | Not run | Checkpoint and actual effective isolation/functional revalidation |
| Signed offline installation | Not run | Trust anchor, complete payload, fresh install/repair/rollback evidence |

Native tests alone leave deployment readiness false. Passing a fixture is evidence for that fixture/configuration, not a completed installation or authorization to process CUI.
