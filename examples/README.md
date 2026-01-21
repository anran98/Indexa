# Configuration Examples

This directory contains example `sources.yaml` configurations for different project types.

## Available Examples

| File | Use Case |
|------|----------|
| [`minimal.yaml`](./minimal.yaml) | Simplest possible configuration |
| [`python-monorepo.yaml`](./python-monorepo.yaml) | Python monorepo with multiple packages |
| [`react-component-library.yaml`](./react-component-library.yaml) | React/TypeScript component library |
| [`microservices.yaml`](./microservices.yaml) | Multiple microservices across repos |

## Using an Example

1. Copy the example to `config/sources.yaml`:
   ```bash
   cp examples/minimal.yaml config/sources.yaml
   ```

2. Edit the `root` paths to match your project locations

3. Build the index:
   ```bash
   indexa index
   ```

## Creating Your Own Configuration

Start with `minimal.yaml` and add complexity as needed:

```yaml
sources:
  - id: my_project           # Unique identifier
    name: "My Project"       # Display name
    root: "C:/path/to/repo"  # Absolute path
    
    include_globs:           # What to index
      - "**/*.md"
    
    exclude_globs:           # What to skip
      - "**/node_modules/**"
```

See [CONFIGURATION.md](../docs/CONFIGURATION.md) for the full reference.
