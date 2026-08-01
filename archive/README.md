# Archive — dead code, kept for reference only

Nothing in here is imported by the live codebase. Files land here when they are
superseded but still worth an occasional skim; everything here gets deleted at
final cleanup (agent-context INF-3).

## ppo_legacy/

The pre-rewrite PPO training stack (train / eval / policy / buffer / ppo,
372 lines), already entirely commented out before archiving — dead since the
DQN-to-PPO rewrite was itself superseded by the fresh micromouse rebuild. It was
built against the old unicycle body and abstract 7-ray sensor contract, so none
of it ports to the differential-drive world; see agent-context
`03_SIM_simulation.md` for what replaced it.
