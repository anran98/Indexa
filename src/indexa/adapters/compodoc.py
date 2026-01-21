"""Compodoc adapter - parses Angular documentation.json into chunks."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from indexa.adapters.base import BaseAdapter
from indexa.graph.types import ChunkType
from indexa.indexing.chunk import NormalizedChunk
from indexa.indexing.component_chunk import ComponentChunk


class CompodocAdapter(BaseAdapter):
    """Parse Compodoc documentation.json into ComponentChunks."""

    SUPPORTED_EXTENSIONS = {".json"}

    def __init__(
        self,
        source_id: str,
        source_root: Path,
        json_path: str = "documentation.json",
        include_directives: bool = True,
        include_services: bool = True,
        include_pipes: bool = False,
        category_from_path: bool = True,
        default_category: str = "Components",
    ):
        self.source_id = source_id
        self.source_root = source_root
        self.json_path = json_path
        self.include_directives = include_directives
        self.include_services = include_services
        self.include_pipes = include_pipes
        self.category_from_path = category_from_path
        self.default_category = default_category

    def supports_extension(self, extension: str) -> bool:
        return extension.lower() in self.SUPPORTED_EXTENSIONS

    def parse_file(self, file_path: Path) -> list[NormalizedChunk]:
        if file_path.name != self.json_path.split("/")[-1]:
            return []

        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)
        file_modified = datetime.fromtimestamp(file_path.stat().st_mtime)

        chunks: list[NormalizedChunk] = []

        for component in data.get("components", []):
            chunks.extend(self._process_component(component, file_modified))

        if self.include_directives:
            for directive in data.get("directives", []):
                chunks.extend(self._process_directive(directive, file_modified))

        if self.include_services:
            for injectable in data.get("injectables", []):
                chunks.extend(self._process_injectable(injectable, file_modified))

        return chunks

    def _process_component(
        self,
        comp: dict[str, Any],
        file_modified: datetime,
    ) -> list[ComponentChunk]:
        chunks: list[ComponentChunk] = []

        name = comp.get("name", "Unknown")
        file_path = comp.get("file", "")
        selector = comp.get("selector", "")
        description = comp.get("description", "") or comp.get("rawdescription", "")
        category = self._infer_category(file_path)
        extends = comp.get("extends")
        imports = comp.get("imports", [])

        chunks.append(self._create_overview_chunk(
            name=name,
            selector=selector,
            description=description,
            category=category,
            file_path=file_path,
            file_modified=file_modified,
            extends=extends,
            imports=imports,
            standalone=comp.get("standalone", False),
        ))

        inputs = comp.get("inputsClass", [])
        if inputs:
            chunks.append(self._create_inputs_chunk(
                name=name,
                inputs=inputs,
                category=category,
                file_path=file_path,
                file_modified=file_modified,
            ))

        outputs = comp.get("outputsClass", [])
        if outputs:
            chunks.append(self._create_outputs_chunk(
                name=name,
                outputs=outputs,
                category=category,
                file_path=file_path,
                file_modified=file_modified,
            ))

        methods = [m for m in comp.get("methodsClass", [])
                   if not m.get("name", "").startswith("ng")]
        if methods:
            chunks.append(self._create_methods_chunk(
                name=name,
                methods=methods,
                category=category,
                file_path=file_path,
                file_modified=file_modified,
            ))

        return chunks

    def _create_overview_chunk(
        self,
        name: str,
        selector: str,
        description: str,
        category: str,
        file_path: str,
        file_modified: datetime,
        extends: str | None,
        imports: list[str],
        standalone: bool,
    ) -> ComponentChunk:
        content_parts = [f"# {name}"]

        if description:
            content_parts.append(f"\n{self._clean_html(description)}")

        if selector:
            content_parts.append(f"\n**Selector:** `{selector}`")
        content_parts.append(f"\n**Category:** {category}")

        if standalone:
            content_parts.append("\n**Standalone:** Yes")

        if extends:
            content_parts.append(f"\n**Extends:** {extends}")

        content = "\n".join(filter(None, content_parts))

        return ComponentChunk(
            id=self._generate_id(name, "overview"),
            source_id=self.source_id,
            path=file_path,
            anchor=None,
            title=name,
            content=content,
            kind="api_doc",
            depth=1,
            is_entrypoint=True,
            file_modified=file_modified,
            component_name=name,
            component_category=category,
            chunk_type=ChunkType.OVERVIEW,
            extends=extends,
            uses=[self._extract_component_name(i) for i in imports if i],
        )

    def _create_inputs_chunk(
        self,
        name: str,
        inputs: list[dict[str, Any]],
        category: str,
        file_path: str,
        file_modified: datetime,
    ) -> ComponentChunk:
        lines = [
            f"# {name} Inputs",
            "",
            "| Input | Type | Default | Description |",
            "|-------|------|---------|-------------|",
        ]

        props_mentioned = []
        for inp in inputs:
            inp_name = inp.get("name", "")
            inp_type = inp.get("type", "any")
            inp_default = inp.get("defaultValue", "-") or "-"
            inp_desc = self._clean_html(
                inp.get("description", "") or inp.get("rawdescription", "")
            )
            inp_desc = inp_desc.replace("\n", " ").strip() or "-"

            if inp.get("deprecated"):
                inp_desc = f"**DEPRECATED** {inp_desc}"

            lines.append(
                f"| `{inp_name}` | `{inp_type}` | `{inp_default}` | {inp_desc} |"
            )
            props_mentioned.append(inp_name)

        content = "\n".join(lines)

        return ComponentChunk(
            id=self._generate_id(name, "inputs"),
            source_id=self.source_id,
            path=file_path,
            anchor="inputs",
            title=f"{name} Inputs",
            content=content,
            kind="api_doc",
            depth=2,
            has_table=True,
            file_modified=file_modified,
            component_name=name,
            component_category=category,
            chunk_type=ChunkType.INPUTS,
            props_mentioned=props_mentioned,
        )

    def _create_outputs_chunk(
        self,
        name: str,
        outputs: list[dict[str, Any]],
        category: str,
        file_path: str,
        file_modified: datetime,
    ) -> ComponentChunk:
        lines = [
            f"# {name} Outputs",
            "",
            "| Output | Type | Description |",
            "|--------|------|-------------|",
        ]

        for out in outputs:
            out_name = out.get("name", "")
            out_type = out.get("type", "EventEmitter")
            out_desc = self._clean_html(
                out.get("description", "") or out.get("rawdescription", "")
            )
            out_desc = out_desc.replace("\n", " ").strip() or "-"

            if out.get("deprecated"):
                out_desc = f"**DEPRECATED** {out_desc}"

            lines.append(f"| `{out_name}` | `{out_type}` | {out_desc} |")

        content = "\n".join(lines)

        return ComponentChunk(
            id=self._generate_id(name, "outputs"),
            source_id=self.source_id,
            path=file_path,
            anchor="outputs",
            title=f"{name} Outputs",
            content=content,
            kind="api_doc",
            depth=2,
            has_table=True,
            file_modified=file_modified,
            component_name=name,
            component_category=category,
            chunk_type=ChunkType.OUTPUTS,
        )

    def _create_methods_chunk(
        self,
        name: str,
        methods: list[dict[str, Any]],
        category: str,
        file_path: str,
        file_modified: datetime,
    ) -> ComponentChunk:
        lines = [f"# {name} Methods", ""]

        for method in methods:
            method_name = method.get("name", "")
            args = method.get("args", [])
            return_type = method.get("returnType", "void")
            description = self._clean_html(
                method.get("description", "") or method.get("rawdescription", "")
            )

            arg_str = ", ".join(
                f"{a.get('name', 'arg')}: {a.get('type', 'any')}"
                for a in args
            )
            signature = f"{method_name}({arg_str}): {return_type}"

            lines.append(f"## `{signature}`")
            if description:
                lines.append(f"\n{description}")
            lines.append("")

        content = "\n".join(lines)

        return ComponentChunk(
            id=self._generate_id(name, "methods"),
            source_id=self.source_id,
            path=file_path,
            anchor="methods",
            title=f"{name} Methods",
            content=content,
            kind="api_doc",
            depth=2,
            file_modified=file_modified,
            component_name=name,
            component_category=category,
            chunk_type=ChunkType.METHODS,
        )

    def _process_directive(
        self,
        directive: dict[str, Any],
        file_modified: datetime,
    ) -> list[ComponentChunk]:
        name = directive.get("name", "Unknown")
        file_path = directive.get("file", "")
        selector = directive.get("selector", "")
        description = directive.get("description", "") or directive.get("rawdescription", "")
        category = self._infer_category(file_path) or "Directives"

        chunks = []

        content = f"# {name} (Directive)\n\n"
        if description:
            content += f"{self._clean_html(description)}\n\n"
        if selector:
            content += f"**Selector:** `{selector}`\n"

        chunks.append(ComponentChunk(
            id=self._generate_id(name, "directive-overview"),
            source_id=self.source_id,
            path=file_path,
            anchor=None,
            title=f"{name} (Directive)",
            content=content,
            kind="api_doc",
            depth=1,
            file_modified=file_modified,
            component_name=name,
            component_category=category,
            chunk_type=ChunkType.OVERVIEW,
        ))

        inputs = directive.get("inputsClass", [])
        if inputs:
            chunks.append(self._create_inputs_chunk(
                name=name,
                inputs=inputs,
                category=category,
                file_path=file_path,
                file_modified=file_modified,
            ))

        return chunks

    def _process_injectable(
        self,
        injectable: dict[str, Any],
        file_modified: datetime,
    ) -> list[ComponentChunk]:
        name = injectable.get("name", "Unknown")
        file_path = injectable.get("file", "")
        description = injectable.get("description", "") or injectable.get("rawdescription", "")
        category = self._infer_category(file_path) or "Services"

        content = f"# {name} (Service)\n\n"
        if description:
            content += f"{self._clean_html(description)}\n\n"

        methods = injectable.get("methodsClass", [])
        if methods:
            content += "## Methods\n\n"
            for method in methods:
                method_name = method.get("name", "")
                return_type = method.get("returnType", "void")
                content += f"- `{method_name}(): {return_type}`\n"

        return [ComponentChunk(
            id=self._generate_id(name, "service-overview"),
            source_id=self.source_id,
            path=file_path,
            anchor=None,
            title=f"{name} (Service)",
            content=content,
            kind="api_doc",
            depth=1,
            file_modified=file_modified,
            component_name=name,
            component_category=category,
            chunk_type=ChunkType.OVERVIEW,
        )]

    def _generate_id(self, name: str, chunk_type: str) -> str:
        id_source = f"{self.source_id}:compodoc:{name}:{chunk_type}"
        return hashlib.sha256(id_source.encode()).hexdigest()[:16]

    def _infer_category(self, file_path: str) -> str:
        if not self.category_from_path or not file_path:
            return self.default_category

        parts = file_path.replace("\\", "/").lower().split("/")

        category_indicators = {
            "forms", "buttons", "layout", "navigation", "data-display",
            "feedback", "overlay", "typography", "icons", "tables",
            "inputs", "modals", "dialogs", "menus", "cards",
        }

        for part in parts:
            if part in category_indicators:
                return part.replace("-", " ").title()

        for i, part in enumerate(parts):
            if part.endswith(".component.ts") or part.endswith(".directive.ts"):
                if i > 0:
                    parent = parts[i - 1]
                    if parent not in {"lib", "src", "app", "components"}:
                        return parent.replace("-", " ").title()

        return self.default_category

    def _clean_html(self, text: str) -> str:
        if not text:
            return ""
        clean = re.sub(r"<[^>]+>", "", text)
        clean = re.sub(r"\s+", " ", clean)
        return clean.strip()

    def _extract_component_name(self, import_str: str) -> str:
        if import_str.endswith("Module"):
            return import_str[:-6]
        if import_str.endswith("Component"):
            return import_str[:-9]
        return import_str
