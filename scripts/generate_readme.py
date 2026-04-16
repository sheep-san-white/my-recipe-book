# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""レシピディレクトリを走査してREADME.mdのレシピセクションを自動生成する"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

# README生成対象外のディレクトリ名を定義する
IGNORED_DIRS = {".git", ".github", "docs", "scripts", "tests", "node_modules"}


def parse_recipe_file(file_path: Path) -> dict:
    """レシピ .md ファイルからメタデータを取得する"""
    text = file_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    hackmd_url = None
    title = None
    body_start = 0

    # YAMLフロントマターを解析する
    if lines and lines[0].strip() == "---":
        end_index = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_index = i
                break
        if end_index is not None:
            frontmatter_text = "\n".join(lines[1:end_index])
            frontmatter = yaml.safe_load(frontmatter_text)
            if isinstance(frontmatter, dict):
                url = frontmatter.get("hackmd_url")
                # 空文字列やNoneの場合はNoneにする
                if url:
                    hackmd_url = str(url)
            body_start = end_index + 1

    # フロントマター以降から最初の # 見出しを取得する
    for line in lines[body_start:]:
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped[2:].strip()
            break

    # 見出しがない場合はファイル名をタイトルにする
    if title is None:
        title = file_path.stem

    return {"title": title, "hackmd_url": hackmd_url, "path": file_path}


def scan_category(category_dir: Path) -> dict:
    """カテゴリディレクトリを走査してレシピとサブカテゴリを返す"""
    recipes = []
    subcategories = {}

    for entry in sorted(category_dir.iterdir()):
        if entry.is_file() and entry.suffix == ".md":
            recipes.append(parse_recipe_file(entry))
        elif entry.is_dir():
            # サブディレクトリ内の.mdファイルを取得する
            sub_recipes = []
            for sub_entry in sorted(entry.iterdir()):
                if sub_entry.is_file() and sub_entry.suffix == ".md":
                    sub_recipes.append(parse_recipe_file(sub_entry))
            if sub_recipes:
                # サブカテゴリ内もタイトルでソートする
                sub_recipes.sort(key=lambda r: r["title"])
                subcategories[entry.name] = sub_recipes

    # レシピをタイトルでソートする
    recipes.sort(key=lambda r: r["title"])

    return {"recipes": recipes, "subcategories": subcategories}


def generate_recipes_section(root: Path, categories: list[str]) -> tuple[str, list[str]]:
    """レシピセクションのMarkdownテキストとメッセージのリストを生成する"""
    messages: list[str] = []
    parts: list[str] = []

    # categories.ymlに載っていないディレクトリを検出する
    all_dirs = set()
    for entry in root.iterdir():
        if entry.is_dir() and entry.name not in IGNORED_DIRS and not entry.name.startswith("."):
            all_dirs.add(entry.name)

    for dir_name in sorted(all_dirs):
        if dir_name not in categories:
            messages.append(f"warning: {dir_name}/ is not listed in categories.yml")

    # カテゴリ順にレシピセクションを生成する
    for category in categories:
        category_dir = root / category
        if not category_dir.is_dir():
            continue

        data = scan_category(category_dir)

        # URLが設定されているレシピだけを抽出する
        valid_recipes = []
        for recipe in data["recipes"]:
            if recipe["hackmd_url"]:
                valid_recipes.append(recipe)
            else:
                rel_path = recipe["path"].relative_to(root)
                messages.append(f"skipped: {rel_path} (hackmd_url not set)")

        valid_subcategories = {}
        for sub_name, sub_recipes in data["subcategories"].items():
            valid_sub = []
            for recipe in sub_recipes:
                if recipe["hackmd_url"]:
                    valid_sub.append(recipe)
                else:
                    rel_path = recipe["path"].relative_to(root)
                    messages.append(f"skipped: {rel_path} (hackmd_url not set)")
            if valid_sub:
                valid_subcategories[sub_name] = valid_sub

        # URLを持つレシピが1つもなければカテゴリをスキップする
        if not valid_recipes and not valid_subcategories:
            continue

        parts.append(f"### {category}\n")

        for recipe in valid_recipes:
            parts.append(f"* [{recipe['title']}]({recipe['hackmd_url']})")

        for sub_name in sorted(valid_subcategories.keys()):
            parts.append(f"\n#### {sub_name}\n")
            for recipe in valid_subcategories[sub_name]:
                parts.append(f"* [{recipe['title']}]({recipe['hackmd_url']})")

        parts.append("")

    section = "\n".join(parts)
    return section, messages


def update_readme(readme_path: Path, recipes_section: str) -> None:
    """README.mdのマーカー間をレシピセクションで置換する"""
    content = readme_path.read_text(encoding="utf-8")

    start_marker = "<!-- recipes:start -->"
    end_marker = "<!-- recipes:end -->"

    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)

    if start_idx == -1 or end_idx == -1:
        print("error: README.md にマーカーが見つからない", file=sys.stderr)
        sys.exit(1)

    # マーカー間のコンテンツを置換する
    new_content = (
        content[: start_idx + len(start_marker)]
        + "\n"
        + recipes_section
        + content[end_idx:]
    )

    readme_path.write_text(new_content, encoding="utf-8")


def main() -> None:
    """メインエントリポイント: README.mdのレシピセクションを再生成する"""
    # scripts/ の親ディレクトリをルートとする
    root = Path(__file__).resolve().parent.parent

    # categories.yml からカテゴリ順序を読み込む
    categories_path = root / "categories.yml"
    with open(categories_path, encoding="utf-8") as f:
        categories_data = yaml.safe_load(f)
    categories = categories_data["order"]

    # レシピセクションを生成する
    section, messages = generate_recipes_section(root, categories)

    # README.md を更新する
    readme_path = root / "README.md"
    update_readme(readme_path, section)

    # メッセージを出力する
    for msg in messages:
        print(msg)


if __name__ == "__main__":
    main()
