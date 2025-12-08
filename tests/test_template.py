"""Tests for PromptTemplate loading and validation."""

from pathlib import Path

import pytest

from drover.classifier import PromptTemplate, TemplateError


class TestPromptTemplate:
    """Tests for PromptTemplate class."""

    def test_load_valid_template(self, tmp_path: Path) -> None:
        """Test loading a valid template with all required placeholders."""
        template_file = tmp_path / "valid.md"
        template_file.write_text(
            "---\nname: test\n---\nClassify this: {taxonomy_menu}\nContent: {document_content}"
        )

        template = PromptTemplate(template_file)
        content = template.content

        assert "{taxonomy_menu}" in content
        assert "{document_content}" in content

    def test_load_template_missing_taxonomy_menu(self, tmp_path: Path) -> None:
        """Test that missing taxonomy_menu placeholder raises TemplateError."""
        template_file = tmp_path / "missing_taxonomy.md"
        template_file.write_text("Content: {document_content}")

        template = PromptTemplate(template_file)

        with pytest.raises(TemplateError, match="missing required placeholders.*taxonomy_menu"):
            _ = template.content

    def test_load_template_missing_document_content(self, tmp_path: Path) -> None:
        """Test that missing document_content placeholder raises TemplateError."""
        template_file = tmp_path / "missing_content.md"
        template_file.write_text("Menu: {taxonomy_menu}")

        template = PromptTemplate(template_file)

        with pytest.raises(TemplateError, match="missing required placeholders.*document_content"):
            _ = template.content

    def test_load_template_missing_both_placeholders(self, tmp_path: Path) -> None:
        """Test that missing both placeholders raises TemplateError."""
        template_file = tmp_path / "missing_both.md"
        template_file.write_text("No placeholders here")

        template = PromptTemplate(template_file)

        with pytest.raises(TemplateError, match="missing required placeholders"):
            _ = template.content

    def test_load_nonexistent_file(self) -> None:
        """Test that nonexistent file raises TemplateError."""
        template = PromptTemplate(Path("/nonexistent/path/template.md"))

        with pytest.raises(TemplateError, match="Template file not found"):
            _ = template.content

    def test_load_invalid_yaml_frontmatter(self, tmp_path: Path) -> None:
        """Test that invalid YAML frontmatter raises TemplateError."""
        template_file = tmp_path / "invalid_yaml.md"
        template_file.write_text(
            "---\ninvalid: yaml: content:\n---\n{taxonomy_menu} {document_content}"
        )

        template = PromptTemplate(template_file)

        with pytest.raises(TemplateError, match="Invalid YAML frontmatter"):
            _ = template.content

    def test_render_substitutes_placeholders(self, tmp_path: Path) -> None:
        """Test that render substitutes placeholders correctly."""
        template_file = tmp_path / "render.md"
        template_file.write_text("Menu: {taxonomy_menu}\nContent: {document_content}")

        template = PromptTemplate(template_file)
        rendered = template.render(taxonomy_menu="MENU", document_content="CONTENT")

        assert "Menu: MENU" in rendered
        assert "Content: CONTENT" in rendered

    def test_frontmatter_parsed_correctly(self, tmp_path: Path) -> None:
        """Test that YAML frontmatter is parsed correctly."""
        template_file = tmp_path / "frontmatter.md"
        template_file.write_text(
            "---\nname: test_template\nversion: '1.0'\n---\n{taxonomy_menu} {document_content}"
        )

        template = PromptTemplate(template_file)

        assert template.frontmatter["name"] == "test_template"
        assert template.frontmatter["version"] == "1.0"

    def test_template_without_frontmatter(self, tmp_path: Path) -> None:
        """Test loading template without frontmatter."""
        template_file = tmp_path / "no_frontmatter.md"
        template_file.write_text("{taxonomy_menu}\n{document_content}")

        template = PromptTemplate(template_file)

        assert template.frontmatter == {}
        assert "{taxonomy_menu}" in template.content
