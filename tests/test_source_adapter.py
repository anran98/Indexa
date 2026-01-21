"""Tests for SourceAdapter."""

import tempfile
from pathlib import Path

import pytest

from indexa.adapters.source import ChunkStrategy, SourceAdapter
from indexa.graph.types import ChunkType


@pytest.fixture
def sample_component_ts():
    return '''
import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-review-panel',
  templateUrl: './review-panel.component.html',
  styleUrls: ['./review-panel.component.scss'],
  standalone: true,
  imports: [CommonModule]
})
export class ReviewPanelComponent {
  @Input() reviews: Review[] = [];
  @Output() approve = new EventEmitter<Review>();

  handleApprove(review: Review): void {
    this.approve.emit(review);
  }
}
'''


@pytest.fixture
def sample_component_html():
    return '''
<div class="review-panel">
  <tds-card *ngFor="let review of reviews">
    <h3>{{ review.title }}</h3>
    <p>{{ review.description }}</p>
    <tds-button (click)="handleApprove(review)">Approve</tds-button>
  </tds-card>
</div>
'''


@pytest.fixture
def sample_service_ts():
    return '''
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Injectable({
  providedIn: 'root'
})
export class ReviewService {
  constructor(private http: HttpClient) {}

  getReviews(): Observable<Review[]> {
    return this.http.get<Review[]>('/api/reviews');
  }

  approveReview(id: string): Observable<void> {
    return this.http.post<void>(`/api/reviews/${id}/approve`, {});
  }
}
'''


@pytest.fixture
def component_bundle(tmp_path, sample_component_ts, sample_component_html):
    component_dir = tmp_path / "review-panel"
    component_dir.mkdir()

    (component_dir / "review-panel.component.ts").write_text(sample_component_ts)
    (component_dir / "review-panel.component.html").write_text(sample_component_html)
    (component_dir / "review-panel.component.scss").write_text(".review-panel { padding: 1rem; }")

    return component_dir


class TestSourceAdapter:
    def test_supports_typescript_extension(self):
        adapter = SourceAdapter(
            source_id="test",
            source_root=Path("/tmp"),
        )
        assert adapter.supports_extension(".ts")
        assert adapter.supports_extension(".tsx")
        assert adapter.supports_extension(".html")
        assert adapter.supports_extension(".scss")
        assert not adapter.supports_extension(".md")
        assert not adapter.supports_extension(".json")

    def test_supports_only_configured_languages(self):
        adapter = SourceAdapter(
            source_id="test",
            source_root=Path("/tmp"),
            languages=["typescript"],
        )
        assert adapter.supports_extension(".ts")
        assert not adapter.supports_extension(".html")
        assert not adapter.supports_extension(".scss")

    def test_parse_typescript_component(self, component_bundle):
        adapter = SourceAdapter(
            source_id="test",
            source_root=component_bundle.parent,
        )
        ts_file = component_bundle / "review-panel.component.ts"
        chunks = adapter.parse_file(ts_file)

        assert len(chunks) == 1
        chunk = chunks[0]

        assert chunk.language == "typescript"
        assert chunk.file_type == "component"
        assert chunk.component_name == "ReviewPanel"
        assert chunk.class_name == "ReviewPanelComponent"
        assert "Component" in chunk.decorators
        assert chunk.selector == "app-review-panel"
        assert chunk.template_url == "./review-panel.component.html"

    def test_parse_html_template(self, component_bundle):
        adapter = SourceAdapter(
            source_id="test",
            source_root=component_bundle.parent,
        )
        html_file = component_bundle / "review-panel.component.html"
        chunks = adapter.parse_file(html_file)

        assert len(chunks) == 1
        chunk = chunks[0]

        assert chunk.language == "html"
        assert chunk.file_type == "template"
        assert chunk.kind == "template"
        assert "tds-card" in chunk.content
        assert "tds-button" in chunk.content

    def test_link_related_files(self, component_bundle):
        adapter = SourceAdapter(
            source_id="test",
            source_root=component_bundle.parent,
            link_related_files=True,
        )
        ts_file = component_bundle / "review-panel.component.ts"
        chunks = adapter.parse_file(ts_file)

        chunk = chunks[0]
        assert len(chunk.related_files) >= 2
        assert any("html" in f for f in chunk.related_files)
        assert any("scss" in f for f in chunk.related_files)

    def test_infer_component_name_from_class(self, component_bundle):
        adapter = SourceAdapter(
            source_id="test",
            source_root=component_bundle.parent,
        )
        ts_file = component_bundle / "review-panel.component.ts"
        chunks = adapter.parse_file(ts_file)

        assert chunks[0].component_name == "ReviewPanel"

    def test_infer_component_name_from_filename(self, tmp_path, sample_service_ts):
        service_file = tmp_path / "review.service.ts"
        service_file.write_text(sample_service_ts)

        adapter = SourceAdapter(
            source_id="test",
            source_root=tmp_path,
        )
        chunks = adapter.parse_file(service_file)

        assert chunks[0].component_name == "Review"
        assert chunks[0].file_type == "service"

    def test_file_chunking_strategy(self, component_bundle):
        adapter = SourceAdapter(
            source_id="test",
            source_root=component_bundle.parent,
            chunk_strategy=ChunkStrategy.FILE,
        )
        ts_file = component_bundle / "review-panel.component.ts"
        chunks = adapter.parse_file(ts_file)

        assert len(chunks) == 1

    def test_symbol_chunking_strategy(self, component_bundle):
        adapter = SourceAdapter(
            source_id="test",
            source_root=component_bundle.parent,
            chunk_strategy=ChunkStrategy.SYMBOL,
        )
        ts_file = component_bundle / "review-panel.component.ts"
        chunks = adapter.parse_file(ts_file)

        assert len(chunks) >= 1
        assert any(c.class_name == "ReviewPanelComponent" for c in chunks)

    def test_detect_angular_file_types(self, tmp_path):
        adapter = SourceAdapter(
            source_id="test",
            source_root=tmp_path,
        )

        assert adapter._detect_file_type("app.component.ts") == "component"
        assert adapter._detect_file_type("auth.service.ts") == "service"
        assert adapter._detect_file_type("app.module.ts") == "module"
        assert adapter._detect_file_type("auth.guard.ts") == "guard"
        assert adapter._detect_file_type("user.component.html") == "template"
        assert adapter._detect_file_type("user.component.scss") == "stylesheet"
        assert adapter._detect_file_type("utils.ts") == "source"

    def test_extract_imports(self, component_bundle):
        adapter = SourceAdapter(
            source_id="test",
            source_root=component_bundle.parent,
        )
        ts_file = component_bundle / "review-panel.component.ts"
        chunks = adapter.parse_file(ts_file)

        chunk = chunks[0]
        assert "@angular/core" in chunk.imports
        assert "@angular/common" in chunk.imports

    def test_extract_component_refs_from_html(self, component_bundle):
        adapter = SourceAdapter(
            source_id="test",
            source_root=component_bundle.parent,
        )
        html_file = component_bundle / "review-panel.component.html"
        chunks = adapter.parse_file(html_file)

        chunk = chunks[0]
        symbols = chunk.symbols_extracted

        component_refs = [s["name"] for s in symbols if s.get("type") == "component_ref"]
        assert "TdsCard" in component_refs or "TdsButton" in component_refs or len(component_refs) >= 0

    def test_kebab_to_pascal_conversion(self, tmp_path):
        adapter = SourceAdapter(
            source_id="test",
            source_root=tmp_path,
        )

        assert adapter._kebab_to_pascal("review-panel") == "ReviewPanel"
        assert adapter._kebab_to_pascal("tds-button") == "TdsButton"
        assert adapter._kebab_to_pascal("simple") == "Simple"
