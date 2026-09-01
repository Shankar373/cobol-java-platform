# Phase 22: Bugs, Hangs, and Code Smells

- **Stale Lock Files**: Force-killing processes leaves `backend.lock` and `launcher.lock` files on disk, preventing Docker Desktop from launching until deleted.
- **Orphaned Docker Containers**: Terminated runs do not actively stop background Docker containers, causing resource locking.
- **Level 78 Constant Limitations**: OpenSourceCOBOL4J does not support Level 78 variables, throwing syntax errors.
