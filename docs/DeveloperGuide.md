# Developer Guide

Project Foundation M1 establishes the formal project structure.

V4.1.0 moves business features into `modules/`.

- UI code stays under `ui/` and only collects input, shows state, and calls modules.
- Business feature logic stays under `modules/<module_id>/`.
- Shared infrastructure stays under `core/`.
- Assets stay under `assets/`.

Read `modules/README.md` before adding, removing, or changing a feature module.
