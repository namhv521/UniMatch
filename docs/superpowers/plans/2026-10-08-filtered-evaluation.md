# Filtered snapshot and evaluation plan

Goal: exclude the five sources explicitly requested, retain evidence and evaluate real policies plus baselines without mixing toy scores.

Architecture: archive the current curated/features inputs, preserve split membership and frozen preprocessing, subset matrix rows, pin the new serving contract. A combined runner uses the original snapshot to verify old checkpoint provenance and evaluates on the filtered validation split with transfer status. Toy checkpoints are rejected explicitly; a separate training command produces real policies for all six algorithms using existing trainers.

- [ ] Add a failing regression for exclusion, split preservation and transfer contract validation.
- [ ] Implement repeatable preparation with source backup and excluded records.
- [ ] Update serving contract checks for the pinned filtered snapshot.
- [ ] Implement combined evaluation and long-running training runner.
- [ ] Run preparation, focused checks and existing-model validation evaluation; document commands and limitations.

No promotion of transfer models, no test-set selection, no automatic long training, no unrelated worktree changes.
