# Getting Started with Indexa

**Indexa** is an MCP (Model Context Protocol) server that indexes your internal documentation and makes it searchable from AI assistants like Cursor.

## Prerequisites

- Python 3.11+
- pip or uv package manager
- Cursor IDE (or any MCP-compatible client)

## Installation

### 1. Clone and Install

```bash
cd /path/to/indexa
pip install -e .
```

This installs Indexa in editable mode with all dependencies including:
- `fastmcp` - MCP server framework
- `pyyaml` - Configuration parsing
- `rich` - Pretty CLI output
- `click` - CLI framework

### 2. Configure Your Documentation Sources

Edit `config/sources.yaml` to point to your documentation:

```yaml
sources:
  - id: my_project
    name: "My Project"
    description: "Internal project documentation"
    root: "C:/path/to/my/project"
    
    include_globs:
      - "docs/**/*.md"
      - "README.md"
      - "**/AGENTS.md"
    
    exclude_globs:
      - "**/node_modules/**"
      - "**/.git/**"
    
    entrypoints:
      - "README.md"
      - "docs/GETTING_STARTED.md"
    
    adapters:
      - markdown
    
    tags:
      - internal
      - python
```

### 3. Build the Index

```bash
indexa index
```

Expected output:
```
Indexing 1 source(s)...

  My Project (C:\path\to\my\project)
    OK 150 chunks indexed

Done! Indexed 150 total chunks
Index saved to: /path/to/indexa\data\index.json
```

### 4. Install to Cursor

Option A: Use the CLI command:
```bash
indexa install-cursor
```

Option B: Manually create `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "indexa": {
      "command": "python",
      "args": ["-m", "indexa.server"],
      "cwd": "/path/to/indexa"
    }
  }
}
```

### 5. Restart Cursor

After restarting, Indexa will be available as an MCP server.

---

## Verifying the Installation

### Check Index Status

```bash
indexa status
```

Output:
```
Indexa Index Status

  Index file: /path/to/indexa\data\index.json
  Version: 1.0
  Indexed at: 2026-01-11T00:26:56.202774
  Total chunks: 1262

Chunks by source:
  agentic_search: 1262
```

### Test Search

```bash
indexa search "how to install"
```

---

## Using Indexa in Cursor

Once Cursor restarts with Indexa enabled, simply ask questions about your documentation:

**Example prompts:**

- "How do I onboard a new tenant?"
- "What's the architecture of the query pipeline?"
- "Show me examples of using the vector store"

**What happens behind the scenes:**

1. Claude recognizes the question relates to your documentation
2. Calls `search("onboard tenant")` to find relevant sections
3. Calls `get_context(source, path, anchor)` to retrieve full content
4. Synthesizes an answer based on YOUR actual documentation

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `indexa index` | Build/rebuild the search index |
| `indexa status` | Show index statistics |
| `indexa sources` | List configured sources |
| `indexa search "query"` | Test search from CLI |
| `indexa install-cursor` | Install MCP config for Cursor |
| `indexa categories` | List component categories (for UI libs) |
| `indexa component-info <name>` | Show component details and relationships |

### Search Options

```bash
# Basic search
indexa search "query generation"

# Limit results
indexa search "query generation" --top-k 10

# Filter by source
indexa search "query generation" --source agentic_search
```

---

## UI Component Library Support (v0.2.0+)

Indexa v0.2.0 adds specialized support for UI component documentation with graph-based search.

### Quick Setup for Components

1. **Configure with component adapter:**
   ```yaml
   sources:
     - id: ui_components
       name: "UI Components"
       root: "C:/path/to/components"
       
       adapter: component  # Use component adapter
       default_category: "General"
       
       include_globs:
         - "**/*.mdx"
         - "**/*.md"
   ```

2. **Add frontmatter to your component docs:**
   ```mdx
   ---
   component: Button
   category: Forms
   extends: BaseButton
   uses:
     - Icon
     - Spinner
   variants:
     - IconButton
     - LoadingButton
   related:
     - Link
   ---
   
   # Button
   
   ## Props
   ...
   
   ## Example
   ...
   ```

3. **Use component-aware CLI:**
   ```bash
   # List all categories
   indexa categories
   
   # Get component info with relationships
   indexa component-info Button
   ```

### MCP Tools for Components

Once indexed, these tools are available to AI assistants:

- `search_components(query, component?, category?, chunk_type?)` - Search with filters
- `get_component_info(component)` - Get component relationships and docs
- `list_component_categories()` - List all categories
- `explore_category(category)` - Explore a category
- `find_related_components(component)` - Find related components via graph

---

## Angular Library Support (v1.0.0+)

Indexa v1.0.0 adds full support for Angular component libraries, including:
- Compodoc documentation.json parsing
- TypeScript/HTML/SCSS source code indexing
- Component relationship graphs

### Quick Setup for Angular Libraries

1. **Generate Compodoc documentation:**
   ```bash
   cd /path/to/ng-library
   npx @compodoc/compodoc -p tsconfig.lib.json --exportFormat json
   ```

2. **Configure multi-adapter source:**
   ```yaml
   sources:
     - id: tds_enterprise
       name: "TDS Enterprise"
       root: "/path/to/ng-tds-enterprise"
       
       # Multi-adapter configuration
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

3. **Build the index:**
   ```bash
   indexa index
   ```

### MCP Tools for Source Code

Once indexed, these additional tools are available:

- `search_source(query, language?, file_type?, component?)` - Search source code
- `get_component_source(component, include_template?, include_styles?)` - Get all files for a component
- `find_component_usage(component)` - Find where a component is used

### Example Queries in Cursor

> "Show me how ButtonComponent handles click events"

Claude will:
1. Call `search_source("click event ButtonComponent")`
2. Call `get_component_source("ButtonComponent")` for full implementation
3. Provide the relevant TypeScript code

> "Where is the TdsDatePicker used?"

Claude will:
1. Call `find_component_usage("TdsDatePicker")`
2. Return all templates that reference `<tds-date-picker>`

> "What are the inputs for TdsModal?"

Claude will:
1. Call `search_source("TdsModal inputs", file_type="api_doc")`
2. Return @Input() properties from Compodoc documentation

---

## Python Project Support (v1.1.0+)

Indexa v1.1.0 adds native Python source code indexing using AST parsing:
- Extracts docstrings (Google, NumPy, Sphinx formats)
- Parses function/method signatures with type hints
- Tracks class inheritance and decorators
- Indexes import statements

### Quick Setup for Python Projects

1. **Configure with python adapter:**
   ```yaml
   sources:
     - id: my_python_lib
       name: "My Python Library"
       root: "/path/to/my-lib"
       
       adapters:
         - type: python
           config:
             chunk_strategy: symbol    # 'file', 'symbol', or 'module'
             include_private: false    # Skip _private symbols
             include_tests: false      # Skip test_*.py files
         - type: markdown
       
       include_globs:
         - "src/**/*.py"
         - "docs/**/*.md"
         - "README.md"
       
       exclude_globs:
         - "**/__pycache__/**"
         - "**/venv/**"
         - "**/*.pyc"
   ```

2. **Build the index:**
   ```bash
   indexa index
   ```

### Chunking Strategies

| Strategy | Description | Best For |
|----------|-------------|----------|
| `file` | One chunk per .py file | Small modules |
| `symbol` | One chunk per class/function | Large codebases, granular search |
| `module` | Overview + top-level symbols | API documentation |

### Example Queries in Cursor

> "How does the UserService authenticate users?"

Claude will:
1. Search Python files for `UserService` and `authenticate`
2. Return the relevant method with its docstring and signature

> "What parameters does process_data accept?"

Claude will:
1. Find the `process_data` function
2. Return its signature with type hints and docstring

> "Show me all classes that inherit from BaseHandler"

Claude will:
1. Search for classes with `BaseHandler` in bases
2. Return class definitions with their methods

---

## Updating Documentation

When your documentation changes:

1. **Re-index from CLI:**
   ```bash
   indexa index
   ```

2. **Or re-index from Cursor:**
   Just ask: "Reload the indexa index"
   
   Claude will call the `reload()` tool automatically.

---

## Troubleshooting

### "Index not found"

Run `indexa index` to build the index first.

### "Source root does not exist"

Check that the `root` path in `config/sources.yaml` exists and is accessible.

### "No results found"

- Verify your `include_globs` patterns match your documentation files
- Check that files aren't being excluded by `exclude_globs`
- Try broader search terms

### Cursor doesn't show Indexa

1. Verify `.cursor/mcp.json` exists and has correct paths
2. Restart Cursor completely (not just reload)
3. Check Cursor's MCP logs for errors

---

## Next Steps

- [Configuration Reference](./CONFIGURATION.md) - Detailed sources.yaml options
- [Architecture](./ARCHITECTURE.md) - How Indexa works internally
- [Examples](../examples/) - Sample configurations for different project types
