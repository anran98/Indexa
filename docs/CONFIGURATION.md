# Configuration Reference

Indexa is configured through `config/sources.yaml`. This document describes all available options.

## File Structure

```yaml
sources:
  - id: source_1
    # ... source configuration
  
  - id: source_2
    # ... source configuration
```

## Source Configuration

Each source represents a documentation repository or project.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier for the source (used in search filters and URIs) |
| `root` | string | Absolute path to the source directory |
| `include_globs` | list[string] | File patterns to include in indexing |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | `id` value | Human-readable display name |
| `description` | string | `""` | Brief description of what this source contains |
| `exclude_globs` | list[string] | `[]` | File patterns to exclude from indexing |
| `entrypoints` | list[string] | `[]` | High-value files to boost in search results |
| `adapter` | string | `"markdown"` | Single adapter (legacy format) |
| `adapters` | list[AdapterConfig] | `[]` | Multi-adapter configuration (v1.0.0+) |
| `tags` | list[string] | `[]` | Labels for categorization and filtering |

> **Note:** Use either `adapter` (simple string) or `adapters` (list with config), not both. The `adapters` format provides more control and supports multiple adapters per source.

---

## Glob Patterns

Indexa uses Python's `glob` and `fnmatch` for pattern matching.

### Common Patterns

| Pattern | Matches |
|---------|---------|
| `*.md` | All `.md` files in root directory |
| `**/*.md` | All `.md` files recursively |
| `docs/**/*.md` | All `.md` files under `docs/` |
| `**/README.md` | All `README.md` files at any depth |
| `**/AGENTS.md` | All `AGENTS.md` files at any depth |
| `src/**/*.py` | All Python files under `src/` |

### Include Patterns (`include_globs`)

Files matching ANY of these patterns will be considered for indexing.

```yaml
include_globs:
  - "docs/**/*.md"        # Documentation folder
  - "README.md"           # Root README
  - "**/README.md"        # All READMEs
  - "**/AGENTS.md"        # Module-level docs
  - "examples/**/*.md"    # Example documentation
```

### Exclude Patterns (`exclude_globs`)

Files matching ANY of these patterns will be skipped, even if they match include patterns.

```yaml
exclude_globs:
  - "**/node_modules/**"  # Node.js dependencies
  - "**/.git/**"          # Git internals
  - "**/venv/**"          # Python virtual env
  - "**/__pycache__/**"   # Python cache
  - "**/.venv/**"         # Alternative venv
  - "**/dist/**"          # Build outputs
  - "**/build/**"         # Build outputs
  - "**/*.min.js"         # Minified files
  - "**/CHANGELOG.md"     # Often noisy
```

---

## Entry Points

Entry points are high-value documentation files that get boosted in search results. Typically these are:

- Main README files
- Getting started guides
- API reference entry points
- Architecture overviews

```yaml
entrypoints:
  - "README.md"
  - "docs/GETTING_STARTED.md"
  - "docs/API_REFERENCE.md"
  - "docs/ARCHITECTURE.md"
```

**Boost factor:** Entry points receive a 1.5x score multiplier in search results.

---

## Adapters

Adapters parse different file formats into searchable chunks.

### Available Adapters

| Adapter | Extensions | Description |
|---------|------------|-------------|
| `markdown` | `.md`, `.mdx`, `.markdown` | Parses headings into sections |
| `component` | `.md`, `.mdx` | Component-aware parsing with frontmatter extraction |
| `compodoc` | `.json` | Angular Compodoc documentation.json (v1.0.0+) |
| `source` | `.ts`, `.html`, `.scss`, `.css` | Source code files (v1.0.0+) |
| `python` | `.py`, `.pyw` | Python source with docstrings and type hints (v1.1.0+) |

### Markdown Adapter (Default)

Standard markdown parsing that splits content by headings.

```yaml
adapter: markdown  # or omit (default)
```

### Component Adapter (v0.2.0+)

Enhanced parsing for UI component documentation. Extracts:
- Component metadata from YAML frontmatter
- Relationships (extends, uses, variants, related)
- Section classification (props, examples, accessibility, etc.)
- JSX component references from code blocks

```yaml
adapter: component
default_category: "General"  # Fallback category if not in frontmatter
```

**Frontmatter Schema:**

```yaml
---
component: Button          # Required: Component name
category: Forms            # Optional: Category for grouping
extends: BaseButton        # Optional: Base component
uses:                      # Optional: Components this one uses
  - Icon
  - Spinner
variants:                  # Optional: Variant components
  - IconButton
  - LoadingButton
related:                   # Optional: Related components
  - Link
  - Anchor
---
```

**Section Classification:**

The adapter automatically classifies sections based on heading text:

| Chunk Type | Detected Headings |
|------------|-------------------|
| `props` | Props, API, Properties, Attributes |
| `example` | Example, Usage, Demo, Sample |
| `variant` | Variant, Variation, Style, Size |
| `accessibility` | Accessibility, A11y, ARIA, Keyboard |
| `styling` | Styling, CSS, Theming, Customization |
| `migration` | Migration, Upgrade, Changelog |
| `best_practices` | Best Practice, Guideline, Recommendation |
| `overview` | (default for unmatched sections) |

### Compodoc Adapter (v1.0.0+)

Parses Angular Compodoc-generated `documentation.json` files. Extracts:
- Components, directives, services, pipes, modules
- Input/output properties with types and descriptions
- Method signatures and documentation
- Inheritance relationships

**Multi-adapter format (recommended):**

```yaml
adapters:
  - type: compodoc
    config:
      json_path: "documentation.json"      # Path to Compodoc JSON
      include_directives: true             # Index directives (default: true)
      include_services: true               # Index services (default: true)
      include_pipes: true                  # Index pipes (default: true)
      include_modules: false               # Index modules (default: false)
      include_internal: false              # Index @internal items (default: false)
```

**Extracted chunk types:**
- `api_doc` - Component/directive/service API documentation
- `INPUTS` - @Input() properties
- `OUTPUTS` - @Output() event emitters
- `METHODS` - Public methods

### Source Adapter (v1.0.0+)

Indexes source code files for searchable implementation details. Supports:
- TypeScript (`.ts`) - Classes, methods, decorators
- HTML templates (`.html`) - Component usage, structural directives
- SCSS/CSS (`.scss`, `.css`) - Style definitions

**Multi-adapter format (recommended):**

```yaml
adapters:
  - type: source
    config:
      languages:                           # Languages to index
        - typescript
        - html
        - scss
      chunk_strategy: file                 # 'file' (whole file) or 'symbol' (per class/function)
      link_related_files: true             # Auto-link .ts/.html/.scss for same component
      max_file_size: 100000                # Skip files larger than this (bytes)
      include_comments: true               # Index comments (default: true)
      include_specs: false                 # Index .spec.ts files (default: false)
```

**Extracted chunk types:**
- `source` - TypeScript source files
- `template` - HTML template files
- `stylesheet` - SCSS/CSS style files

**Relationships created:**
- `HAS_TEMPLATE` - Component → template file
- `HAS_STYLESHEET` - Component → style file
- `HAS_SOURCE` - Component → source file
- `IMPORTS` - Import relationships between files
- `REFERENCES` - Template references to components

### Python Adapter (v1.1.0+)

Parses Python source files using the stdlib `ast` module. Extracts:
- Module-level docstrings
- Class definitions with docstrings and base classes
- Function/method signatures with type hints
- Decorators
- Import statements

**Multi-adapter format (recommended):**

```yaml
adapters:
  - type: python
    config:
      chunk_strategy: symbol              # 'file', 'symbol', or 'module'
      include_private: false              # Index _private symbols (default: false)
      include_tests: false                # Index test_*.py files (default: false)
      include_dunder: false               # Index __dunder__ methods (default: false)
```

**Chunking Strategies:**

| Strategy | Description |
|----------|-------------|
| `file` | One chunk per Python file (module-level) |
| `symbol` | One chunk per class/function (granular search) |
| `module` | Module overview + top-level symbols only |

**Extracted metadata:**
- `language`: Always "python"
- `file_type`: "module", "class", "function", "method", etc.
- `imports`: List of imported modules
- `exports`: Public symbols defined in the file
- `decorators`: Decorator names on classes/functions
- `symbols_extracted`: Detailed symbol information including signatures

**Docstring format detection:**
The adapter auto-detects docstring styles (Google, NumPy, Sphinx) for future parsing enhancements.

**Example configuration for a Python project:**

```yaml
sources:
  - id: my_python_lib
    name: "My Python Library"
    root: "/path/to/my-lib"
    
    adapters:
      - type: python
        config:
          chunk_strategy: symbol
          include_private: false
          include_tests: false
      - type: markdown
    
    include_globs:
      - "src/**/*.py"
      - "docs/**/*.md"
      - "README.md"
    
    exclude_globs:
      - "**/__pycache__/**"
      - "**/venv/**"
      - "**/*.pyc"
    
    entrypoints:
      - "README.md"
      - "src/my_lib/__init__.py"
    
    tags:
      - python
      - library
```

---

## Multi-Adapter Configuration (v1.0.0+)

For sources with multiple file types (e.g., Angular libraries), use the `adapters` array:

```yaml
sources:
  - id: tds_enterprise
    name: "TDS Enterprise"
    root: "/path/to/ng-tds-enterprise"
    
    # Multiple adapters process different file types
    adapters:
      - type: compodoc
        config:
          json_path: "documentation.json"
          include_directives: true
          include_services: true
      
      - type: source
        config:
          languages: [typescript, html, scss]
          chunk_strategy: file
          link_related_files: true
      
      - type: markdown
        # No config needed for markdown
    
    include_globs:
      - "documentation.json"
      - "projects/tds-lib/src/**/*.ts"
      - "projects/tds-lib/src/**/*.html"
      - "projects/tds-lib/src/**/*.scss"
      - "docs/**/*.md"
    
    exclude_globs:
      - "**/*.spec.ts"
      - "**/node_modules/**"
```

**Adapter Selection Logic:**

1. Each file is matched against adapters in order
2. The first adapter that can handle the file extension processes it
3. Files not matching any adapter are skipped

**Adapter to Extension Mapping:**

| Adapter | Extensions |
|---------|------------|
| `compodoc` | `.json` (only `documentation.json`) |
| `source` | `.ts`, `.html`, `.scss`, `.css` (based on `languages` config) |
| `python` | `.py`, `.pyw` |
| `markdown` | `.md`, `.mdx`, `.markdown` |
| `component` | `.md`, `.mdx` (with frontmatter detection) |

### Future Adapters (Planned)

| Adapter | Extensions | Description |
|---------|------------|-------------|
| `python` | `.py` | Extracts docstrings and signatures |
| `openapi` | `.yaml`, `.json` | Parses OpenAPI/Swagger specs |

---

## Tags

Tags help categorize sources for filtering and organization.

```yaml
tags:
  - python
  - framework
  - internal
  - api
```

Tags are currently stored with chunks but not used for filtering in search. This is planned for a future release.

---

## Complete Example

```yaml
# config/sources.yaml

sources:
  # Python backend framework (simple markdown)
  - id: agentic_search
    name: "AgenticSearch"
    description: "Multi-dialect query generation framework with multi-tenant support"
    root: "/path/to/your-project"
    
    include_globs:
      - "docs/**/*.md"
      - "examples/**/*.md"
      - "**/AGENTS.md"
      - "**/README.md"
      - "README.md"
    
    exclude_globs:
      - "**/node_modules/**"
      - "**/.git/**"
      - "**/venv/**"
      - "**/__pycache__/**"
      - "**/.venv/**"
    
    entrypoints:
      - "README.md"
      - "docs/GETTING_STARTED.md"
      - "docs/PROJECT_INDEX.md"
      - "docs/API_REFERENCE.md"
    
    adapters:
      - markdown
    
    tags:
      - python
      - query-generation
      - multi-tenant

  # React component library (with component adapter)
  - id: ui_components
    name: "UI Components"
    description: "Shared React component library"
    root: "/path/to/ui-components"
    
    # Use component adapter for graph-based search
    adapter: component
    default_category: "General"
    
    include_globs:
      - "docs/**/*.md"
      - "**/*.mdx"
      - "**/README.md"
    
    exclude_globs:
      - "**/node_modules/**"
      - "**/.git/**"
      - "**/dist/**"
      - "**/storybook-static/**"
    
    entrypoints:
      - "README.md"
      - "docs/getting-started.mdx"
    
    tags:
      - react
      - typescript
      - frontend
      - components

  # Angular library with source code (v1.0.0+)
  - id: tds_enterprise
    name: "TDS Enterprise"
    description: "Angular component library with full source indexing"
    root: "/path/to/ng-tds-enterprise"
    
    # Multi-adapter: Compodoc + Source + Markdown
    adapters:
      - type: compodoc
        config:
          json_path: "documentation.json"
          include_directives: true
          include_services: true
          include_pipes: true
      
      - type: source
        config:
          languages: [typescript, html, scss]
          chunk_strategy: file
          link_related_files: true
          include_specs: false
      
      - type: markdown
    
    include_globs:
      - "documentation.json"
      - "projects/tds-lib/src/**/*.ts"
      - "projects/tds-lib/src/**/*.html"
      - "projects/tds-lib/src/**/*.scss"
      - "docs/**/*.md"
      - "**/README.md"
    
    exclude_globs:
      - "**/*.spec.ts"
      - "**/node_modules/**"
      - "**/.git/**"
      - "**/dist/**"
    
    entrypoints:
      - "README.md"
      - "docs/GETTING_STARTED.md"
    
    tags:
      - angular
      - typescript
      - components
      - enterprise

  # API documentation
  - id: api_docs
    name: "API Documentation"
    description: "REST API reference documentation"
    root: "/path/to/api-docs"
    
    include_globs:
      - "**/*.md"
    
    exclude_globs:
      - "**/.git/**"
    
    entrypoints:
      - "README.md"
      - "authentication.md"
      - "endpoints/index.md"
    
    adapters:
      - markdown
    
    tags:
      - api
      - rest
      - reference
```

---

## Validation

Indexa validates source configurations on load:

| Check | Error Message |
|-------|---------------|
| Missing `id` | "Source 'id' is required" |
| Missing/invalid `root` | "Source root does not exist: {path}" |
| Missing `include_globs` | "At least one 'include_globs' pattern is required" |

To validate your configuration:

```bash
indexa sources
```

This will load and display all configured sources, failing if any are invalid.

---

## Path Format

Use forward slashes in paths for cross-platform compatibility:

```yaml
# Good - works on Windows and Unix
root: "/path/to/project"

# Also works on Windows
root: "/path/to/project"
```

---

## Environment Variables

Currently, Indexa does not support environment variable expansion in configuration files. Use absolute paths.

**Planned:** `${VAR}` syntax for environment variable substitution.
