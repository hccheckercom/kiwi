"""Auto-detect language, framework, and tooling from project files."""

import os
import json
from dataclasses import dataclass, field
from pathlib import Path
from collections import Counter


@dataclass
class ProjectProfile:
    languages: dict = field(default_factory=dict)  # {lang: ratio}
    frameworks: list = field(default_factory=list)
    package_manager: str | None = None
    test_framework: str | None = None
    build_tool: str | None = None
    entry_points: list = field(default_factory=list)
    linter: str | None = None
    css_framework: str | None = None
    _wp_detected: bool = False

    def has_wordpress_signals(self) -> bool:
        if "wordpress" in self.frameworks:
            return True
        indicators = ["wp-content", "wp-includes", "functions.php", "style.css"]
        if any(e in str(self.entry_points) for e in indicators):
            return True
        return self._wp_detected

    def confidence_score(self) -> float:
        score = 0.1
        if self.languages:
            score += 0.2
        if self.frameworks:
            score += 0.2
        if self.package_manager:
            score += 0.1
        if self.test_framework:
            score += 0.1
        if self.build_tool:
            score += 0.1
        return min(score, 0.8)


LANG_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".php": "php",
    ".rb": "ruby",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".cs": "csharp",
    ".swift": "swift",
    ".dart": "dart",
    ".vue": "vue",
    ".svelte": "svelte",
    ".css": "css",
    ".scss": "scss",
    ".less": "less",
    ".html": "html",
    ".sql": "sql",
    ".sh": "shell",
    ".ps1": "powershell",
    ".lua": "lua",
    ".ex": "elixir",
    ".exs": "elixir",
    ".zig": "zig",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
}

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "vendor", "dist", "build",
    ".next", ".nuxt", "target", "bin", "obj", ".venv", "venv",
    "env", ".tox", "coverage", ".cache", ".output",
}


def detect(path: str, max_files: int = 2000) -> ProjectProfile:
    """Detect project profile from filesystem analysis."""
    root = Path(path)
    if not root.is_dir():
        return ProjectProfile()

    profile = ProjectProfile()

    _detect_languages(root, profile, max_files)
    _detect_from_configs(root, profile)
    _detect_entry_points(root, profile)
    _detect_wordpress_signals(root, profile)

    return profile


def _detect_languages(root: Path, profile: ProjectProfile, max_files: int) -> None:
    ext_counts = Counter()
    scanned = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            if ext in LANG_EXTENSIONS:
                ext_counts[LANG_EXTENSIONS[ext]] += 1
                scanned += 1
            if scanned >= max_files:
                break
        if scanned >= max_files:
            break

    total = sum(ext_counts.values()) or 1
    profile.languages = {
        lang: round(count / total, 3)
        for lang, count in ext_counts.most_common(10)
        if count / total >= 0.02
    }


def _detect_from_configs(root: Path, profile: ProjectProfile) -> None:
    _check_package_json(root, profile)
    _check_composer_json(root, profile)
    _check_python_configs(root, profile)
    _check_rust(root, profile)
    _check_go(root, profile)
    _check_tsconfig(root, profile)
    _check_css_framework(root, profile)
    _check_linter(root, profile)
    _check_build_tool(root, profile)


def _check_package_json(root: Path, profile: ProjectProfile) -> None:
    pkg = root / "package.json"
    if not pkg.exists():
        return

    profile.package_manager = "npm"
    if (root / "pnpm-lock.yaml").exists():
        profile.package_manager = "pnpm"
    elif (root / "yarn.lock").exists():
        profile.package_manager = "yarn"
    elif (root / "bun.lockb").exists():
        profile.package_manager = "bun"

    try:
        data = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
    except (json.JSONDecodeError, OSError):
        return

    all_deps = {}
    all_deps.update(data.get("dependencies", {}))
    all_deps.update(data.get("devDependencies", {}))

    framework_signals = {
        "next": "nextjs",
        "react": "react",
        "vue": "vue",
        "nuxt": "nuxt",
        "svelte": "svelte",
        "@sveltejs/kit": "sveltekit",
        "angular": "angular",
        "@angular/core": "angular",
        "express": "express",
        "fastify": "fastify",
        "hono": "hono",
        "remix": "remix",
        "@remix-run/react": "remix",
        "gatsby": "gatsby",
        "astro": "astro",
        "solid-js": "solid",
        "preact": "preact",
        "electron": "electron",
        "react-native": "react-native",
        "expo": "expo",
    }

    for dep, fw in framework_signals.items():
        if dep in all_deps and fw not in profile.frameworks:
            profile.frameworks.append(fw)

    test_signals = {
        "jest": "jest",
        "vitest": "vitest",
        "mocha": "mocha",
        "@testing-library/react": "testing-library",
        "cypress": "cypress",
        "playwright": "playwright",
        "@playwright/test": "playwright",
    }
    for dep, tf in test_signals.items():
        if dep in all_deps:
            profile.test_framework = tf
            break


def _check_composer_json(root: Path, profile: ProjectProfile) -> None:
    composer = root / "composer.json"
    if not composer.exists():
        return

    profile.package_manager = profile.package_manager or "composer"

    try:
        data = json.loads(composer.read_text(encoding="utf-8", errors="ignore"))
    except (json.JSONDecodeError, OSError):
        return

    all_deps = {}
    all_deps.update(data.get("require", {}))
    all_deps.update(data.get("require-dev", {}))

    if "laravel/framework" in all_deps:
        profile.frameworks.append("laravel")
    if "symfony/framework-bundle" in all_deps:
        profile.frameworks.append("symfony")
    if "wordpress" in str(data.get("type", "")).lower():
        profile.frameworks.append("wordpress")

    if "phpunit/phpunit" in all_deps:
        profile.test_framework = "phpunit"
    elif "pestphp/pest" in all_deps:
        profile.test_framework = "pest"


def _check_python_configs(root: Path, profile: ProjectProfile) -> None:
    has_python = False

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        has_python = True
        try:
            content = pyproject.read_text(encoding="utf-8", errors="ignore")
            if "pytest" in content:
                profile.test_framework = "pytest"
            if "django" in content.lower():
                profile.frameworks.append("django")
            if "flask" in content.lower():
                profile.frameworks.append("flask")
            if "fastapi" in content.lower():
                profile.frameworks.append("fastapi")
            if "[tool.poetry]" in content:
                profile.package_manager = profile.package_manager or "poetry"
            elif "hatchling" in content or "[tool.hatch]" in content:
                profile.package_manager = profile.package_manager or "hatch"
            else:
                profile.package_manager = profile.package_manager or "pip"
        except OSError:
            pass

    if (root / "requirements.txt").exists() or (root / "setup.py").exists():
        has_python = True
        profile.package_manager = profile.package_manager or "pip"

    if has_python and not profile.test_framework:
        if (root / "pytest.ini").exists() or (root / "conftest.py").exists():
            profile.test_framework = "pytest"


def _check_rust(root: Path, profile: ProjectProfile) -> None:
    if (root / "Cargo.toml").exists():
        profile.package_manager = profile.package_manager or "cargo"
        profile.build_tool = profile.build_tool or "cargo"


def _check_go(root: Path, profile: ProjectProfile) -> None:
    if (root / "go.mod").exists():
        profile.package_manager = profile.package_manager or "go"
        profile.build_tool = profile.build_tool or "go"


def _check_tsconfig(root: Path, profile: ProjectProfile) -> None:
    if (root / "tsconfig.json").exists():
        if "typescript" not in profile.languages:
            profile.languages["typescript"] = profile.languages.get("typescript", 0.0)


def _check_css_framework(root: Path, profile: ProjectProfile) -> None:
    for name in ("tailwind.config.js", "tailwind.config.ts", "tailwind.config.mjs"):
        if (root / name).exists():
            profile.css_framework = "tailwind"
            return
    if (root / "postcss.config.js").exists():
        profile.css_framework = "postcss"


def _check_linter(root: Path, profile: ProjectProfile) -> None:
    linter_files = {
        ".eslintrc.js": "eslint",
        ".eslintrc.json": "eslint",
        ".eslintrc.yml": "eslint",
        "eslint.config.js": "eslint",
        "eslint.config.mjs": "eslint",
        "biome.json": "biome",
        ".prettierrc": "prettier",
        "ruff.toml": "ruff",
        ".flake8": "flake8",
        ".pylintrc": "pylint",
        "phpcs.xml": "phpcs",
        ".php-cs-fixer.php": "php-cs-fixer",
    }
    for filename, linter in linter_files.items():
        if (root / filename).exists():
            profile.linter = linter
            return


def _check_build_tool(root: Path, profile: ProjectProfile) -> None:
    if profile.build_tool:
        return

    build_signals = {
        "vite.config.ts": "vite",
        "vite.config.js": "vite",
        "webpack.config.js": "webpack",
        "webpack.config.ts": "webpack",
        "rollup.config.js": "rollup",
        "esbuild.config.js": "esbuild",
        "turbo.json": "turborepo",
        "nx.json": "nx",
        "Makefile": "make",
        "CMakeLists.txt": "cmake",
        "Gruntfile.js": "grunt",
        "gulpfile.js": "gulp",
    }
    for filename, tool in build_signals.items():
        if (root / filename).exists():
            profile.build_tool = tool
            return


def _detect_entry_points(root: Path, profile: ProjectProfile) -> None:
    candidates = [
        "src/index.ts", "src/index.tsx", "src/index.js",
        "src/main.ts", "src/main.tsx", "src/main.js",
        "src/app.ts", "src/app.js",
        "app/page.tsx", "app/layout.tsx",
        "pages/index.tsx", "pages/index.js",
        "main.py", "app.py", "manage.py",
        "src/main.rs", "src/lib.rs",
        "main.go", "cmd/main.go",
        "index.php", "functions.php",
    ]
    for c in candidates:
        if (root / c).exists():
            profile.entry_points.append(c)


def _detect_wordpress_signals(root: Path, profile: ProjectProfile) -> None:
    """Detect WordPress-specific signals beyond config files."""
    wp_indicators = [
        "wp-content", "wp-includes", "wp-admin",
        "mu-plugins", "wp-config.php", "wp-load.php",
    ]
    for ind in wp_indicators:
        if (root / ind).exists():
            profile._wp_detected = True
            return

    # Check for WP function patterns in PHP files
    wp_patterns = ("add_action(", "add_filter(", "wp_enqueue", "wz_", "wezone_")
    php_count = 0
    wp_hits = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if not f.endswith(".php"):
                continue
            php_count += 1
            if php_count > 30:
                break
            try:
                content = Path(os.path.join(dirpath, f)).read_text(
                    encoding="utf-8", errors="ignore"
                )[:2000]
            except OSError:
                continue
            if any(p in content for p in wp_patterns):
                wp_hits += 1
        if php_count > 30:
            break

    if php_count > 0 and wp_hits / php_count > 0.3:
        profile._wp_detected = True
