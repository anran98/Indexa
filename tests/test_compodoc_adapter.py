"""Tests for CompodocAdapter."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from indexa.adapters.compodoc import CompodocAdapter
from indexa.graph.types import ChunkType


@pytest.fixture
def sample_compodoc_json():
    return {
        "components": [
            {
                "name": "TdsButtonComponent",
                "file": "projects/tds-lib/src/lib/button/button.component.ts",
                "selector": "tds-button",
                "description": "<p>Primary button for user interactions.</p>",
                "rawdescription": "Primary button for user interactions.",
                "inputsClass": [
                    {
                        "name": "variant",
                        "type": "string",
                        "defaultValue": "'primary'",
                        "description": "Visual style variant",
                        "deprecated": False,
                    },
                    {
                        "name": "disabled",
                        "type": "boolean",
                        "defaultValue": "false",
                        "description": "Disable the button",
                        "deprecated": False,
                    },
                ],
                "outputsClass": [
                    {
                        "name": "clicked",
                        "type": "EventEmitter<MouseEvent>",
                        "description": "Emitted when clicked",
                    },
                ],
                "methodsClass": [
                    {
                        "name": "focus",
                        "args": [],
                        "returnType": "void",
                        "description": "Focus the button",
                    },
                    {
                        "name": "ngOnInit",
                        "args": [],
                        "returnType": "void",
                        "description": "",
                    },
                ],
                "standalone": True,
                "imports": ["CommonModule", "TdsIconComponent"],
            }
        ],
        "directives": [
            {
                "name": "TdsTooltipDirective",
                "file": "projects/tds-lib/src/lib/tooltip/tooltip.directive.ts",
                "selector": "[tdsTooltip]",
                "description": "Adds tooltip to elements",
                "inputsClass": [
                    {
                        "name": "tdsTooltip",
                        "type": "string",
                        "description": "Tooltip text",
                    },
                ],
            }
        ],
        "injectables": [
            {
                "name": "TdsDialogService",
                "file": "projects/tds-lib/src/lib/dialog/dialog.service.ts",
                "description": "Service for opening dialogs",
                "methodsClass": [
                    {
                        "name": "open",
                        "returnType": "DialogRef",
                    },
                    {
                        "name": "close",
                        "returnType": "void",
                    },
                ],
            }
        ],
    }


@pytest.fixture
def compodoc_file(sample_compodoc_json, tmp_path):
    json_file = tmp_path / "documentation.json"
    json_file.write_text(json.dumps(sample_compodoc_json))
    return json_file


class TestCompodocAdapter:
    def test_supports_json_extension(self):
        adapter = CompodocAdapter(
            source_id="test",
            source_root=Path("/tmp"),
        )
        assert adapter.supports_extension(".json")
        assert not adapter.supports_extension(".ts")
        assert not adapter.supports_extension(".md")

    def test_parse_component_creates_overview_chunk(self, compodoc_file, tmp_path):
        adapter = CompodocAdapter(
            source_id="test",
            source_root=tmp_path,
        )
        chunks = adapter.parse_file(compodoc_file)

        overview_chunks = [c for c in chunks if c.chunk_type == ChunkType.OVERVIEW]
        assert len(overview_chunks) >= 1

        button_overview = next(
            (c for c in overview_chunks if c.component_name == "TdsButtonComponent"),
            None,
        )
        assert button_overview is not None
        assert "tds-button" in button_overview.content
        assert "Primary button" in button_overview.content

    def test_parse_component_creates_inputs_chunk(self, compodoc_file, tmp_path):
        adapter = CompodocAdapter(
            source_id="test",
            source_root=tmp_path,
        )
        chunks = adapter.parse_file(compodoc_file)

        inputs_chunks = [c for c in chunks if c.chunk_type == ChunkType.INPUTS]
        assert len(inputs_chunks) >= 1

        button_inputs = next(
            (c for c in inputs_chunks if c.component_name == "TdsButtonComponent"),
            None,
        )
        assert button_inputs is not None
        assert "variant" in button_inputs.content
        assert "disabled" in button_inputs.content
        assert button_inputs.has_table

    def test_parse_component_creates_outputs_chunk(self, compodoc_file, tmp_path):
        adapter = CompodocAdapter(
            source_id="test",
            source_root=tmp_path,
        )
        chunks = adapter.parse_file(compodoc_file)

        outputs_chunks = [c for c in chunks if c.chunk_type == ChunkType.OUTPUTS]
        assert len(outputs_chunks) >= 1

        button_outputs = next(
            (c for c in outputs_chunks if c.component_name == "TdsButtonComponent"),
            None,
        )
        assert button_outputs is not None
        assert "clicked" in button_outputs.content

    def test_parse_component_creates_methods_chunk_without_lifecycle(
        self, compodoc_file, tmp_path
    ):
        adapter = CompodocAdapter(
            source_id="test",
            source_root=tmp_path,
        )
        chunks = adapter.parse_file(compodoc_file)

        methods_chunks = [c for c in chunks if c.chunk_type == ChunkType.METHODS]

        button_methods = next(
            (c for c in methods_chunks if c.component_name == "TdsButtonComponent"),
            None,
        )
        assert button_methods is not None
        assert "focus" in button_methods.content
        assert "ngOnInit" not in button_methods.content

    def test_parse_directive(self, compodoc_file, tmp_path):
        adapter = CompodocAdapter(
            source_id="test",
            source_root=tmp_path,
            include_directives=True,
        )
        chunks = adapter.parse_file(compodoc_file)

        directive_chunks = [c for c in chunks if "Directive" in c.title]
        assert len(directive_chunks) >= 1

        tooltip = next(
            (c for c in directive_chunks if "TdsTooltipDirective" in c.title),
            None,
        )
        assert tooltip is not None

    def test_parse_injectable(self, compodoc_file, tmp_path):
        adapter = CompodocAdapter(
            source_id="test",
            source_root=tmp_path,
            include_services=True,
        )
        chunks = adapter.parse_file(compodoc_file)

        service_chunks = [c for c in chunks if "Service" in c.title]
        assert len(service_chunks) >= 1

    def test_exclude_directives_when_disabled(self, compodoc_file, tmp_path):
        adapter = CompodocAdapter(
            source_id="test",
            source_root=tmp_path,
            include_directives=False,
        )
        chunks = adapter.parse_file(compodoc_file)

        directive_chunks = [c for c in chunks if "Directive" in c.title]
        assert len(directive_chunks) == 0

    def test_infer_category_from_path(self, tmp_path):
        adapter = CompodocAdapter(
            source_id="test",
            source_root=tmp_path,
            category_from_path=True,
        )

        assert adapter._infer_category("lib/buttons/button.component.ts") == "Buttons"
        assert adapter._infer_category("lib/forms/input.component.ts") == "Forms"
        assert adapter._infer_category("lib/unknown/thing.ts") == "Components"

    def test_extract_uses_from_imports(self, compodoc_file, tmp_path):
        adapter = CompodocAdapter(
            source_id="test",
            source_root=tmp_path,
        )
        chunks = adapter.parse_file(compodoc_file)

        button_overview = next(
            (
                c
                for c in chunks
                if c.component_name == "TdsButtonComponent"
                and c.chunk_type == ChunkType.OVERVIEW
            ),
            None,
        )
        assert button_overview is not None
        assert "TdsIcon" in button_overview.uses
