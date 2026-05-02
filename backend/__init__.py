# Required so ``python -m backend.eval`` resolves from the repo root. The
# backend itself is run from inside its own directory (uvicorn main:app), so
# this package marker is only meaningful for the CLI eval harness.
