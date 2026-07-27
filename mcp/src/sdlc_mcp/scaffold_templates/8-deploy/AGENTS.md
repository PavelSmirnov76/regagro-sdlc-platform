Ship only what cleared ../7-security-check/.

Every release records:
- the deployment config and release notes
- its rollout and rollback plan — a release with no way back is not ready
- the environment and version it landed in

An item leaves this stage once it is live and being watched in
../9-observation/.
