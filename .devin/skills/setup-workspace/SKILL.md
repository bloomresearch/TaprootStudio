---
name: setup-workspace
description: Initializes submodules so Geminode Studio and Enscript are available for cross-project reference
triggers: [user]
---

# Setup Workspace Skill

Ensure all submodule dependencies are populated and up to date so agents can reference them.

## Procedure

1. Check submodule status: `git submodule status`
2. If any submodule shows a `-` prefix (not yet initialized), run: `git submodule update --init --recursive`
3. If submodules are initialized but stale, run: `git submodule update --remote --merge`
4. Confirm contents are present:
   - `packages/geminode-studio/` — Geminode Studio Workspace
   - `packages/reaction-studio/` — Reaction Studio
5. Report status to user.

## Submodule Registry

| Name | Path | Remote |
|------|------|--------|
| Geminode Studio | `packages/geminode-studio/` | https://github.com/bloomresearch/geminodestudio.git |
| Reaction Studio | `packages/reaction-studio/` | git@github.com:bloomresearch/ReactionStudio.git |

## Notes

- Use `--depth 1` on fresh clones for speed: `git submodule update --init --recursive --depth 1`
- Submodules are read-only references — make changes in the original repo, then update here with `git submodule update --remote`
- For fresh clones of TaprootStudio: `git clone --recurse-submodules https://github.com/bloomresearch/TaprootStudio.git`
