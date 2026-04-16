"""generate_readme.py のテストを定義する"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from generate_readme import (
    generate_recipes_section,
    parse_recipe_file,
    scan_category,
    update_readme,
)


# ---------------------------------------------------------------------------
# parse_recipe_file
# ---------------------------------------------------------------------------


def test_parse_recipe_file_with_frontmatter(tmp_path: Path) -> None:
    """フロントマター付きレシピファイルからタイトルとURLを取得する"""
    recipe = tmp_path / "test.md"
    recipe.write_text(
        "---\nhackmd_url: https://example.com/abc\n---\n\n# テストレシピ\n\n## 食材\n",
        encoding="utf-8",
    )
    result = parse_recipe_file(recipe)
    assert result["title"] == "テストレシピ"
    assert result["hackmd_url"] == "https://example.com/abc"
    assert result["path"] == recipe


def test_parse_recipe_file_without_hackmd_url(tmp_path: Path) -> None:
    """hackmd_urlが空のレシピファイルではNoneを返す"""
    recipe = tmp_path / "test.md"
    recipe.write_text(
        "---\nhackmd_url:\n---\n\n# テストレシピ\n",
        encoding="utf-8",
    )
    result = parse_recipe_file(recipe)
    assert result["title"] == "テストレシピ"
    assert result["hackmd_url"] is None


def test_parse_recipe_file_without_frontmatter(tmp_path: Path) -> None:
    """フロントマターがないレシピファイルではhackmd_urlがNoneになる"""
    recipe = tmp_path / "test.md"
    recipe.write_text("# テストレシピ\n\n本文\n", encoding="utf-8")
    result = parse_recipe_file(recipe)
    assert result["title"] == "テストレシピ"
    assert result["hackmd_url"] is None


def test_parse_recipe_file_without_heading(tmp_path: Path) -> None:
    """見出しがないレシピファイルではファイル名をタイトルにする"""
    recipe = tmp_path / "テストレシピ.md"
    recipe.write_text("---\nhackmd_url: https://example.com\n---\n\n本文\n", encoding="utf-8")
    result = parse_recipe_file(recipe)
    assert result["title"] == "テストレシピ"
    assert result["hackmd_url"] == "https://example.com"


# ---------------------------------------------------------------------------
# scan_category
# ---------------------------------------------------------------------------


def test_scan_category_flat(tmp_path: Path) -> None:
    """カテゴリディレクトリ直下の.mdファイルをソート済みで返す"""
    category_dir = tmp_path / "和食"
    category_dir.mkdir()
    (category_dir / "豚バラ大根.md").write_text(
        "---\nhackmd_url: https://example.com/1\n---\n\n# 豚バラ大根\n", encoding="utf-8"
    )
    (category_dir / "イワシの梅煮.md").write_text(
        "---\nhackmd_url: https://example.com/2\n---\n\n# イワシの梅煮\n", encoding="utf-8"
    )
    result = scan_category(category_dir)
    assert len(result["recipes"]) == 2
    # タイトルでソートされていることを確認する
    assert result["recipes"][0]["title"] == "イワシの梅煮"
    assert result["recipes"][1]["title"] == "豚バラ大根"
    assert result["subcategories"] == {}


def test_scan_category_with_subcategory(tmp_path: Path) -> None:
    """サブディレクトリを持つカテゴリでsubcategoriesを返す"""
    category_dir = tmp_path / "和食"
    category_dir.mkdir()
    (category_dir / "豚バラ大根.md").write_text(
        "---\nhackmd_url: https://example.com/1\n---\n\n# 豚バラ大根\n", encoding="utf-8"
    )
    sub_dir = category_dir / "おせち"
    sub_dir.mkdir()
    (sub_dir / "いくらの醤油漬け.md").write_text(
        "---\nhackmd_url: https://example.com/2\n---\n\n# いくらの醤油漬け\n", encoding="utf-8"
    )
    result = scan_category(category_dir)
    assert len(result["recipes"]) == 1
    assert "おせち" in result["subcategories"]
    assert len(result["subcategories"]["おせち"]) == 1
    assert result["subcategories"]["おせち"][0]["title"] == "いくらの醤油漬け"


# ---------------------------------------------------------------------------
# generate_recipes_section
# ---------------------------------------------------------------------------


def _create_test_repo(tmp_path: Path) -> Path:
    """テスト用のリポジトリ構造を作成する"""
    root = tmp_path / "repo"
    root.mkdir()

    # おつまみ
    otsumami = root / "おつまみ"
    otsumami.mkdir()
    (otsumami / "枝豆.md").write_text(
        "---\nhackmd_url: https://example.com/edamame\n---\n\n# 枝豆\n", encoding="utf-8"
    )

    # 和食
    washoku = root / "和食"
    washoku.mkdir()
    (washoku / "肉じゃが.md").write_text(
        "---\nhackmd_url: https://example.com/nikujaga\n---\n\n# 肉じゃが\n", encoding="utf-8"
    )

    return root


def test_generate_recipes_section(tmp_path: Path) -> None:
    """カテゴリ順にレシピセクションを生成する"""
    root = _create_test_repo(tmp_path)
    categories = ["おつまみ", "和食"]

    section, messages = generate_recipes_section(root, categories)

    assert "### おつまみ" in section
    assert "### 和食" in section
    assert "* [枝豆](https://example.com/edamame)" in section
    assert "* [肉じゃが](https://example.com/nikujaga)" in section
    # おつまみが和食より前に出力されることを確認する
    assert section.index("### おつまみ") < section.index("### 和食")


def test_generate_recipes_section_skips_missing_url(tmp_path: Path) -> None:
    """hackmd_urlが未設定のレシピをスキップしてメッセージに記録する"""
    root = tmp_path / "repo"
    root.mkdir()
    cat_dir = root / "おつまみ"
    cat_dir.mkdir()
    (cat_dir / "枝豆.md").write_text(
        "---\nhackmd_url:\n---\n\n# 枝豆\n", encoding="utf-8"
    )

    section, messages = generate_recipes_section(root, ["おつまみ"])

    assert "枝豆" not in section
    assert any("skipped:" in m and "hackmd_url not set" in m for m in messages)


def test_generate_recipes_section_warns_unlisted_dir(tmp_path: Path) -> None:
    """categories.ymlに載っていないディレクトリに対して警告する"""
    root = tmp_path / "repo"
    root.mkdir()
    unknown_dir = root / "未知のカテゴリ"
    unknown_dir.mkdir()
    (unknown_dir / "何か.md").write_text(
        "---\nhackmd_url: https://example.com\n---\n\n# 何か\n", encoding="utf-8"
    )

    section, messages = generate_recipes_section(root, ["おつまみ"])

    assert any("warning:" in m and "未知のカテゴリ" in m and "not listed in categories.yml" in m for m in messages)


def test_generate_recipes_section_skips_empty_category(tmp_path: Path) -> None:
    """レシピが0件のカテゴリを出力しない"""
    root = tmp_path / "repo"
    root.mkdir()
    # URLなしレシピのみのカテゴリを作成する
    cat_dir = root / "おつまみ"
    cat_dir.mkdir()
    (cat_dir / "枝豆.md").write_text(
        "---\nhackmd_url:\n---\n\n# 枝豆\n", encoding="utf-8"
    )
    # URL付きレシピを持つカテゴリを作成する
    cat_dir2 = root / "和食"
    cat_dir2.mkdir()
    (cat_dir2 / "肉じゃが.md").write_text(
        "---\nhackmd_url: https://example.com/nikujaga\n---\n\n# 肉じゃが\n", encoding="utf-8"
    )

    section, messages = generate_recipes_section(root, ["おつまみ", "和食"])

    assert "### おつまみ" not in section
    assert "### 和食" in section


# ---------------------------------------------------------------------------
# update_readme
# ---------------------------------------------------------------------------


def test_update_readme_replaces_marker_content(tmp_path: Path) -> None:
    """マーカー間のコンテンツを置換する"""
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Title\n\n<!-- recipes:start -->\nold content\n<!-- recipes:end -->\n\nfooter\n",
        encoding="utf-8",
    )
    update_readme(readme, "\n### 新しいセクション\n\n* [テスト](https://example.com)\n\n")
    content = readme.read_text(encoding="utf-8")
    assert "old content" not in content
    assert "### 新しいセクション" in content
    assert "* [テスト](https://example.com)" in content
    assert "# Title" in content
    assert "footer" in content
    # マーカーが保持されていることを確認する
    assert "<!-- recipes:start -->" in content
    assert "<!-- recipes:end -->" in content


def test_update_readme_fails_without_markers(tmp_path: Path) -> None:
    """マーカーがない場合にSystemExitを発生させる"""
    readme = tmp_path / "README.md"
    readme.write_text("# Title\n\nno markers here\n", encoding="utf-8")
    import pytest

    with pytest.raises(SystemExit):
        update_readme(readme, "new content")
