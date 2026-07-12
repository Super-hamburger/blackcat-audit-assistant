# Stage 3 Architecture

## Plugin System

Plugins live in `plugins/<plugin_id>/`.

## Module System

Business modules live in `modules/<module_id>/`.

The main window calls `ModuleRegistry.run()` and should not import feature processors directly.

Current business modules:

- `file_paste`: Excel detection, address splitting, cell marking, output workbook generation.
- `label_compress`: PDF splitting, tracking-number recognition, duplicate detection, ZIP generation.

## Update System

The updater reads a manifest file. In the future this can be replaced with a remote URL.

## I18N

Languages are stored in `locales/*.json`.

## Installer

Portable and one-file builds are supported first. Installer wizard support is planned.
