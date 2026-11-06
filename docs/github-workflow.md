# GitHub milestone workflow

The repository is `newsurvey0098-blip/LossFit`; use the local Git remote `origin` for commits and pushes. The active implementation branch is `codex/lossfit-verification`, which tracks the matching GitHub branch. The hosted `main` branch remains at the earlier baseline while the implementation branch carries the verified work. Keep coherent implementation phases in descriptive commits and update `docs/verification.md` and `docs/acceptance-matrix.md` with evidence before publishing each milestone.

## Publishing a milestone

1. Check the working tree and current branch. Keep unrelated changes out of the milestone.
2. Run the phase's targeted checks, plus the relevant local acceptance checks. Do not state that a live integration or deployment was verified unless it was exercised.
3. Update the acceptance evidence, run `git diff --check`, and commit the complete change.
4. Push the implementation branch with `git push origin codex/lossfit-verification`. GitHub Actions runs CI for this branch. Verify the run result before reporting the milestone as hosted-verified.
5. Check Vercel deployment history. During local implementation, preview deployments have been temporarily disabled for both connected LossFit projects only around branch pushes, then restored. Confirm no branch deployment was created. Do not promote, deploy to Production, or change production domains while deployment remains deferred.

The repository is public. Commit source and safe environment templates only; never add `.env` files, credentials, local databases, runtime files, uploads, test artifacts, or the reference ZIP and screenshots. The current Vercel production API is not ready: production database migrations and runtime credentials remain unconfigured. See [Vercel deployment status](vercel-deployment.md) before resuming deployment.

## Current remote state

- Active branch: `codex/lossfit-verification`.
- Latest verified code milestone: commit `e4c1076` (Windows development server port selection), with hosted CI run [42293832637](https://github.com/newsurvey0098-blip/LossFit/actions/runs/42293832637) passing all four jobs.
- Latest evidence commit: `65f70d6`, with hosted CI run [42292683632](https://github.com/newsurvey0098-blip/LossFit/actions/runs/42292683632) passing all four jobs.
- Vercel Production deployment remains at baseline commit `fa13142`; no new deployment was created for these verification-branch pushes.
