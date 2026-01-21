"""Query expansion with synonyms and abbreviations."""

from __future__ import annotations

import re


class QueryExpander:
    """Expand queries with synonyms and common abbreviations.

    This helps bridge the gap between user terminology and documentation terms.
    For example:
    - "btn" → ["btn", "button"]
    - "auth" → ["auth", "authentication", "authorize"]
    - "config" → ["config", "configuration", "configure"]

    The expander maintains bidirectional mappings so both directions work.
    """

    # Common abbreviations in programming/tech docs
    # Format: abbreviation -> full form
    ABBREVIATIONS: dict[str, str] = {
        # UI Components
        "btn": "button",
        "btns": "buttons",
        "img": "image",
        "imgs": "images",
        "nav": "navigation",
        "hdr": "header",
        "ftr": "footer",
        "dlg": "dialog",
        "mod": "modal",
        "lbl": "label",
        "txt": "text",
        "chk": "checkbox",
        "chkbox": "checkbox",
        "rad": "radio",
        "sel": "select",
        "opt": "option",
        "opts": "options",
        "drp": "dropdown",
        "tbl": "table",
        "col": "column",
        "cols": "columns",
        "row": "row",
        "rows": "rows",
        "pg": "page",
        "pgs": "pages",
        "sec": "section",
        "secs": "sections",
        "cmp": "component",
        "cmps": "components",
        "elem": "element",
        "elems": "elements",
        # Actions
        "cfg": "configuration",
        "config": "configuration",
        "configs": "configurations",
        "init": "initialize",
        "auth": "authentication",
        "authn": "authentication",
        "authz": "authorization",
        "msg": "message",
        "msgs": "messages",
        "err": "error",
        "errs": "errors",
        "warn": "warning",
        "warns": "warnings",
        "info": "information",
        "req": "request",
        "reqs": "requests",
        "res": "response",
        "resp": "response",
        "resps": "responses",
        "cb": "callback",
        "fn": "function",
        "func": "function",
        "funcs": "functions",
        "param": "parameter",
        "params": "parameters",
        "arg": "argument",
        "args": "arguments",
        "val": "value",
        "vals": "values",
        "var": "variable",
        "vars": "variables",
        "const": "constant",
        "consts": "constants",
        "prop": "property",
        "props": "properties",
        "attr": "attribute",
        "attrs": "attributes",
        "evt": "event",
        "evts": "events",
        "ref": "reference",
        "refs": "references",
        "doc": "document",
        "docs": "documents",
        "dir": "directory",
        "dirs": "directories",
        "env": "environment",
        "envs": "environments",
        "dev": "development",
        "prod": "production",
        "stg": "staging",
        "db": "database",
        "dbs": "databases",
        "api": "interface",
        "repo": "repository",
        "repos": "repositories",
        "pkg": "package",
        "pkgs": "packages",
        "lib": "library",
        "libs": "libraries",
        "dep": "dependency",
        "deps": "dependencies",
        "util": "utility",
        "utils": "utilities",
        "src": "source",
        "dest": "destination",
        "tmp": "temporary",
        "temp": "temporary",
        "max": "maximum",
        "min": "minimum",
        "avg": "average",
        "std": "standard",
        "num": "number",
        "nums": "numbers",
        "idx": "index",
        "len": "length",
        "cnt": "count",
        "qty": "quantity",
        "amt": "amount",
        "pct": "percent",
        "perc": "percentage",
        "desc": "description",
        "spec": "specification",
        "specs": "specifications",
        "impl": "implementation",
        "impls": "implementations",
        "exe": "execute",
        "exec": "execute",
        "cmd": "command",
        "cmds": "commands",
        "async": "asynchronous",
        "sync": "synchronous",
        "prev": "previous",
        "cur": "current",
        "curr": "current",
    }

    # Synonym groups - words that should expand to each other
    # Each tuple contains words that are synonymous in context
    SYNONYM_GROUPS: list[tuple[str, ...]] = [
        # UI terms
        ("button", "btn"),
        ("dialog", "modal", "popup", "overlay"),
        ("input", "textfield", "textbox", "field"),
        ("dropdown", "select", "combobox", "picker"),
        ("checkbox", "check", "toggle"),
        ("switch", "toggle"),
        ("slider", "range"),
        ("accordion", "collapsible", "expandable"),
        ("tabs", "tablist", "tabpanel"),
        ("tooltip", "hint", "popover"),
        ("notification", "alert", "toast", "snackbar"),
        ("spinner", "loader", "loading"),
        ("skeleton", "placeholder", "shimmer"),
        ("avatar", "profile", "userpic"),
        ("badge", "tag", "chip", "pill"),
        ("card", "tile", "panel"),
        ("list", "listbox", "menu"),
        ("grid", "layout", "container"),
        ("sidebar", "drawer", "nav"),
        ("breadcrumb", "breadcrumbs", "navigation"),
        # Actions
        ("create", "add", "new", "insert"),
        ("delete", "remove", "destroy", "drop"),
        ("update", "edit", "modify", "change"),
        ("get", "fetch", "retrieve", "read", "load"),
        ("save", "store", "persist", "write"),
        ("search", "find", "query", "filter", "lookup"),
        ("show", "display", "render", "view"),
        ("hide", "conceal", "collapse"),
        ("open", "expand", "show"),
        ("close", "collapse", "hide", "dismiss"),
        ("enable", "activate", "turn on"),
        ("disable", "deactivate", "turn off"),
        ("validate", "verify", "check"),
        ("submit", "send", "post"),
        ("cancel", "abort", "discard"),
        ("reset", "clear", "empty"),
        ("refresh", "reload", "update"),
        ("import", "load", "read"),
        ("export", "save", "download"),
        ("upload", "import", "send"),
        ("download", "export", "fetch"),
        # States
        ("active", "selected", "current", "focused"),
        ("disabled", "inactive", "readonly"),
        ("error", "invalid", "failed"),
        ("success", "valid", "passed"),
        ("loading", "pending", "processing"),
        ("empty", "blank", "none", "null"),
        # Concepts
        ("auth", "authentication", "login", "signin"),
        ("logout", "signout", "logoff"),
        ("permission", "access", "role", "authorization"),
        ("user", "account", "profile"),
        ("settings", "preferences", "options", "config"),
        ("theme", "style", "appearance", "skin"),
        ("dark", "night", "dark mode"),
        ("light", "day", "light mode"),
    ]

    def __init__(self) -> None:
        """Initialize the query expander."""
        # Build reverse abbreviation map
        self._abbrev_to_full: dict[str, str] = dict(self.ABBREVIATIONS)
        self._full_to_abbrev: dict[str, str] = {
            v: k for k, v in self.ABBREVIATIONS.items()
        }

        # Build synonym lookup
        self._synonyms: dict[str, set[str]] = {}
        for group in self.SYNONYM_GROUPS:
            group_set = set(group)
            for word in group:
                if word not in self._synonyms:
                    self._synonyms[word] = set()
                self._synonyms[word].update(group_set - {word})

    def expand(self, query: str) -> str:
        """Expand a query with synonyms and abbreviations.

        Returns an expanded query string suitable for search.

        Args:
            query: Original query string

        Returns:
            Expanded query with additional terms
        """
        tokens = self._tokenize(query)
        expanded_tokens: list[str] = []

        for token in tokens:
            # Add original token
            expanded_tokens.append(token)

            # Add expansions
            expansions = self.get_expansions(token)
            expanded_tokens.extend(expansions)

        # Remove duplicates while preserving order
        seen: set[str] = set()
        unique_tokens: list[str] = []
        for t in expanded_tokens:
            if t not in seen:
                seen.add(t)
                unique_tokens.append(t)

        return " ".join(unique_tokens)

    def get_expansions(self, term: str) -> list[str]:
        """Get all expansions for a single term.

        Args:
            term: Term to expand

        Returns:
            List of expanded terms (not including original)
        """
        term_lower = term.lower()
        expansions: set[str] = set()

        # Check abbreviations (both directions)
        if term_lower in self._abbrev_to_full:
            expansions.add(self._abbrev_to_full[term_lower])
        if term_lower in self._full_to_abbrev:
            expansions.add(self._full_to_abbrev[term_lower])

        # Check synonyms
        if term_lower in self._synonyms:
            expansions.update(self._synonyms[term_lower])

        return list(expansions)

    def get_all_terms(self, query: str) -> list[str]:
        """Get all terms including expansions.

        Useful for BM25 search with OR queries.

        Args:
            query: Original query

        Returns:
            List of all terms (original + expanded)
        """
        tokens = self._tokenize(query)
        all_terms: set[str] = set(tokens)

        for token in tokens:
            all_terms.update(self.get_expansions(token))

        return list(all_terms)

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into words.

        Args:
            text: Text to tokenize

        Returns:
            List of lowercase tokens
        """
        text = text.lower()
        return re.findall(r"\w+", text)

    def add_abbreviation(self, abbrev: str, full: str) -> None:
        """Add a custom abbreviation mapping.

        Args:
            abbrev: Abbreviation
            full: Full form
        """
        self._abbrev_to_full[abbrev.lower()] = full.lower()
        self._full_to_abbrev[full.lower()] = abbrev.lower()

    def add_synonyms(self, *words: str) -> None:
        """Add a custom synonym group.

        Args:
            words: Words that are synonymous
        """
        word_set = set(w.lower() for w in words)
        for word in word_set:
            if word not in self._synonyms:
                self._synonyms[word] = set()
            self._synonyms[word].update(word_set - {word})
