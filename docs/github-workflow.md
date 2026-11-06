# GitHub milestone workflow

The repository is `newsurvey0098-blip/LossFit`; use the local Git remote `origin` for commits and pushes. The active implementation branch is `codex/lossfit-verification`, which tracks the matching GitHub branch. The hosted `main` branch remains at the earlier baseline while the implementation branch carries the verified work. Keep coherent implementation phases in descriptive commits and update `docs/verification.md` and `docs/acceptance-matrix.md` with evidence before publishing each milestone.

## Publishing a milestone

1. Check the working tree and current branch. Keep unrelated changes out of the milestone.
2. Run the phase's targeted checks, plus the relevant local acceptance checks. Do not state that a live integration or deployment was verified unless it was exercised.
3. Update the acceptance evidence, run `git diff --check`, and commit the complete change.
4. Push the implementation branch with `git push origin codex/lossfit-verification`. GitHub Actions runs CI for this branch. Verify the run result before reporting the milestone as hosted-verified.
5. Check Vercel deployment history. Git integration automatically attempted previews for non-production branch pushes; toggling `previewDeploymentsDisabled` alone did not stop one. Both projects now use the Ignored Build Step command `exit 0`, which skips Git builds/deployments until local acceptance is complete. Keep this setting in place during implementation pushes. When deployment is explicitly resumed, replace it with the intended build gate (a command exiting `1` proceeds) and verify which projects and environments will build before pushing. Do not promote, deploy to Production, or change production domains while deployment remains deferred.

The repository is public. Commit source and safe environment templates only; never add `.env` files, credentials, local databases, runtime files, uploads, test artifacts, or the reference ZIP and screenshots. The current Vercel production API is not ready: production database migrations and runtime credentials remain unconfigured. See [Vercel deployment status](vercel-deployment.md) before resuming deployment.

## Current remote state

- Active branch: `codex/lossfit-verification`.
- Latest verified code milestone: commit `c9326d6` (automated Windows local-server port fallback), with hosted CI run [42296901145](https://github.com/newsurvey0098-blip/LossFit/actions/runs/42296901145) passing all five jobs, including the Windows startup-script regression.
- Latest evidence commit: `b2e9784`, with hosted CI run [42296086101](https://github.com/newsurvey0098-blip/LossFit/actions/runs/42296086101) passing all four jobs.
- Vercel Production remains at baseline commit `fa13142`. Push `68d4d02` unexpectedly produced protected preview `dpl_8z1imaiDFPUSAuVffaDuX8Tqnh7G` (`target: null`); production was not changed. The Ignored Build Step skipped the later `c9326d6` push, producing no additional branch preview.
