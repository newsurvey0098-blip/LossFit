# GitHub milestone workflow

The LossFit source of truth is kept in local Git on `main` and published to [newsurvey0098-blip/LossFit](https://github.com/newsurvey0098-blip/LossFit). Keep each coherent implementation phase in its own descriptive commit. Update `docs/verification.md` with the checks and remaining gaps before publishing a milestone. Push the commit only after its targeted checks pass; do not mark an integration complete when its provider or deployment was not exercised.

This workstation's Git credential is for a different GitHub account and cannot push to this repository. Repository writes use the connected GitHub account, which has admin and push access. Never copy provider credentials into the repository or write them into logs. The repository is currently public, so commits must contain source and safe templates only; `.env`, local databases, runtime files, uploads, test outputs, and the reference ZIP/images remain ignored or outside Git.

The local branch retains the detailed implementation history. Initial remote synchronization should reproduce the meaningful commit sequence on the repository's `main` branch. Future verified milestones should be committed locally and published with the connected GitHub repository integration.
