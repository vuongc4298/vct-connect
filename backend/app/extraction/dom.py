"""Shared inert-source, visible-DOM and static access-wall mechanics.

These helpers tokenize source data; they never execute source scripts.
"""
from html.parser import HTMLParser as SourceParser
import re

from selectolax.parser import HTMLParser
import tinycss2

from .evidence import text


# Bound selector matching independently of the HTTP byte limit. Supported
# selectors are intentionally simple, so charging one document scan per small
# selector segment is a conservative upper bound on the expensive work.
CSS_MATCH_WORK_LIMIT = 4_000_000


class _Document(HTMLParser):
    """Keep resolved visibility with this document, without source attributes."""


def tree(html):
    # HTML tree repair can move a head-level noscript's script outside its
    # inactive ancestor. Remove inert source regions before that repair. The
    # tokenizer treats script/style contents as text and never runs them.
    class ActiveSource(SourceParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.inert = []
            self.parts = []

        def handle_starttag(self, tag, attrs):
            if tag in {"noscript", "template"}:
                # Keep the inert container itself so sibling/child combinators
                # see the authored structure, while still excluding its contents.
                if not self.inert:
                    self.parts.append(self.get_starttag_text())
                self.inert.append(tag)
            elif not self.inert:
                self.parts.append(self.get_starttag_text())

        def handle_startendtag(self, tag, attrs):
            if not self.inert:
                self.parts.append(self.get_starttag_text())

        def handle_endtag(self, tag):
            if self.inert:
                if tag == self.inert[-1]:
                    self.inert.pop()
                    if not self.inert:
                        self.parts.append(f"</{tag}>")
            else:
                self.parts.append(f"</{tag}>")

        def handle_data(self, data):
            if not self.inert:
                self.parts.append(data)

        def handle_entityref(self, name):
            self.handle_data(f"&{name};")

        def handle_charref(self, name):
            self.handle_data(f"&#{name};")

        def handle_comment(self, data):
            pass

    source = ActiveSource()
    source.feed(html)
    source.close()
    return _Document("".join(source.parts))


def active(node):
    if node is None:
        return True
    state = _states(node.parser).get(node.mem_id)
    return state is not None and not state[0] and state[1] == "visible"


def scripts(tree):
    def executable(node):
        while node is not None:
            if node.tag in {"template", "noscript"}:
                return False
            node = node.parent
        return True
    return [node for node in tree.css("script") if executable(node) and "src" not in node.attributes
            and (node.attributes.get("type") or "").strip().lower() in {"", "text/javascript", "application/javascript", "text/ecmascript", "application/ecmascript", "module"}]


def prune_dom(tree):
    if tree.root is None:
        return
    states = _states(tree)
    hidden_roots, hidden_text = [], []
    for node in tree.root.traverse(include_text=True):
        if node.tag == "-text":
            state = states.get(node.parent.mem_id)
            if state and not state[0] and state[1] != "visible":
                hidden_text.append(node)
            continue
        state = states[node.mem_id]
        parent = states.get(node.parent.mem_id) if node.parent else None
        if state[0] and (parent is None or not parent[0]):
            hidden_roots.append(node)
    # Visibility hides an element's own text, but a descendant can restore it.
    # Keep the ancestors/selector structure of those visible descendants.
    for node in hidden_text:
        node.decompose()
    for node in hidden_roots:
        node.decompose()
    tree.strip_tags(["script", "style"])


def stylesheet_hidden(tree):
    """Resolve the supported static screen cascade, without editing source CSS.

    Supports top-level type/id/class/attribute selectors and combinators, inline
    declarations, important priority and simple screen/all style media lists.
    Conditional at-rules, pseudo selectors, functions and external CSS remain
    outside this static boundary. CSS tokenization is delegated to tinycss2.
    """
    _states(tree)


def visibility_exhausted(tree):
    _states(tree)
    return bool(getattr(tree, '_screen_work_exhausted', False))


def require_visibility(tree):
    if visibility_exhausted(tree):
        raise RecursionError('Screen cascade work limit')


# Access text alone needs layout boundaries; selected evidence keeps its existing
# formatting. Inline fragments are contiguous unless the author supplied space.
_BLOCK_TAGS = frozenset('html body address article aside blockquote dd div dl dt fieldset figcaption figure footer form h1 h2 h3 h4 h5 h6 header hr li main nav ol p pre section table tbody td tfoot th thead tr ul'.split())


def access_text(node, limit=2000):
    if node is None:
        return ''
    parts, length = [], 0
    pending = [(node, False)]
    while pending and length < limit:
        current, closing = pending.pop()
        if current.tag == '-text':
            value = re.sub(r'\s+', ' ', current.text())
        else:
            if current.tag in {'script', 'style', 'template', 'noscript'}:
                continue
            state = _states(current.parser).get(current.mem_id)
            boundary = (current.tag == 'br'
                        or state and state[2].split()[0] in {'block', 'flow', 'flex', 'grid', 'table', 'table-cell', 'table-row', 'list-item', 'flow-root'})
            value = ' ' if boundary and parts else ''
            if not closing:
                if boundary:
                    pending.append((current, True))
                children = []
                child = current.child
                while child is not None:
                    children.append((child, False))
                    child = child.next
                pending.extend(reversed(children))
        if parts and parts[-1].endswith(' ') and value.startswith(' '):
            value = value[1:]
        value = value[:limit-length]
        if value:
            parts.append(value)
            length += len(value)
    return ''.join(parts).strip()


_SELECTOR_TOKEN = re.compile(r'''\[(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\[\]"'])+\]|[.#][A-Za-z0-9_-]+|[A-Za-z_-][A-Za-z0-9_-]*|\*|\s+|[>+~]''')
_DISPLAY_VALUES = {
    "none", "contents", "block", "inline", "inline-block", "flow-root", "flex", "ruby",
    "inline-flex", "grid", "inline-grid", "table", "inline-table", "table-row",
    "table-cell", "table-caption", "table-row-group", "table-header-group",
    "table-footer-group", "table-column", "table-column-group", "list-item",
    "block flow", "inline flow", "block flow-root", "inline flow-root",
    "block flex", "inline flex", "block grid", "inline grid",
    "flow", "run-in", "inline ruby", "block ruby", "run-in flow", "run-in flow-root",
    "run-in flex", "run-in grid", "run-in ruby", "block list-item", "inline list-item",
    "flow list-item", "flow-root list-item", "block flow list-item", "inline flow list-item",
    "block flow-root list-item", "inline flow-root list-item", "run-in list-item",
    "run-in flow list-item", "run-in flow-root list-item",
}


def _specificity(selector):
    tokens = _SELECTOR_TOKEN.findall(selector)
    if "".join(tokens) != selector or not selector.strip():
        return None
    return (sum(token.startswith("#") for token in tokens),
            sum(token.startswith((".", "[")) for token in tokens),
            sum(bool(re.fullmatch(r"[A-Za-z_-][A-Za-z0-9_-]*", token)) for token in tokens))


def _declarations(source):
    for declaration in tinycss2.parse_declaration_list(source, skip_comments=True, skip_whitespace=True):
        if declaration.type != "declaration" or declaration.lower_name not in {"display", "visibility", "opacity"}:
            continue
        name = declaration.lower_name
        tokens = [token for token in declaration.value if token.type not in {"whitespace", "comment"}]
        value = " ".join(token.lower_value for token in tokens if token.type == "ident")
        if tokens and all(token.type == "ident" for token in tokens):
            if value not in {"initial", "inherit", "unset", "revert"}:
                if name == "opacity" or (name == "visibility" and value not in {"hidden", "collapse", "visible"}):
                    continue
                if name == "display" and value not in _DISPLAY_VALUES:
                    continue
        elif name == "opacity" and len(tokens) == 1 and tokens[0].type in {"number", "percentage"}:
            value = min(1., max(0., tokens[0].value / (100 if tokens[0].type == "percentage" else 1)))
        else:
            continue
        yield name, value, declaration.important


def _states(tree):
    cached = getattr(tree, "_screen_state", None)
    if cached is not None:
        return cached
    if tree.root is None:
        return {}
    winners = {}
    order = 0
    node_count = sum(1 for _ in tree.root.traverse())
    work_left = CSS_MATCH_WORK_LIMIT
    def apply(node, declarations, specificity, inline=0):
        selected = winners.setdefault(node.mem_id, {})
        for name, value, important, position in declarations:
            priority = (important, inline, *specificity, position)
            if name not in selected or priority >= selected[name][0]:
                selected[name] = priority, value

    for style in tree.css("style"):
        attrs = style.attributes
        if (attrs.get("type") or "text/css").strip().lower() != "text/css":
            continue
        media = getattr(tree, '_screen_stylesheet_media', {}).get(style.mem_id, attrs.get('media') or '')
        if media is None:
            continue
        media = media.strip().lower()
        if media and not any(part.strip() in {"screen", "all"} for part in media.split(",")):
            continue
        source = getattr(tree, '_screen_stylesheet_rules', {}).get(style.mem_id, style.text())
        for rule in tinycss2.parse_stylesheet(source, skip_comments=True, skip_whitespace=True):
            if rule.type != "qualified-rule":
                continue
            declarations = []
            for name, value, important in _declarations(rule.content):
                order += 1
                declarations.append((name, value, important, order))
            if not declarations:
                continue
            groups = [[]]
            for token in rule.prelude:
                if token.type == "literal" and token.value == ",":
                    groups.append([])
                elif token.type != "comment":
                    groups[-1].append(token)
            # Reject nested/functional selectors before serialization, including
            # malformed deep input which cannot be a supported static selector.
            if any(token.type not in {"ident", "hash", "literal", "whitespace", "[] block"}
                   or token.type == "[] block" and any(part.type not in {"ident", "literal", "whitespace", "string", "number"} for part in token.content)
                   for group in groups for token in group):
                continue
            selectors = [tinycss2.serialize(group).strip() for group in groups]
            specificities = [_specificity(selector) for selector in selectors]
            # An unsupported selector invalidates this rule, rather than giving
            # its supported siblings an incorrect part of the browser cascade.
            if any(specificity is None for specificity in specificities):
                continue
            cost = sum(node_count * max(1, (len(selector) + 15) // 16) for selector in selectors)
            if cost > work_left:
                # A partial cascade could turn hidden author content into public
                # evidence. Suppress the document instead of using incomplete
                # visibility state.
                states = {node.mem_id: (True, "hidden", "none", 0.) for node in tree.root.traverse()}
                if isinstance(tree, _Document):
                    tree._screen_state = states
                tree._screen_work_exhausted = True
                return states
            work_left -= cost
            try:
                matches = [tree.css(selector) for selector in selectors]
            except ValueError:
                continue
            for nodes, specificity in zip(matches, specificities):
                for node in nodes:
                    apply(node, declarations, specificity)
    for node in tree.css("[style]"):
        declarations = []
        for name, value, important in _declarations(node.attributes.get("style") or ""):
            order += 1
            declarations.append((name, value, important, order))
        apply(node, declarations, (0, 0, 0), inline=1)

    states = {}
    for node in tree.root.traverse():
        parent = states.get(node.parent.mem_id, (False, "visible", "inline", 1.)) if node.parent else (False, "visible", "inline", 1.)
        specified = winners.get(node.mem_id, {})
        computed = {}
        for name, initial, inherited in (("display", "inline", parent[2]), ("visibility", "visible", parent[1]), ("opacity", 1., parent[3])):
            default_display = 'block' if node.tag in _BLOCK_TAGS else 'inline'
            value = specified.get(name, (None, default_display if name == 'display' else 'unset'))[1]
            # Only the author origin is supported here. Revert therefore rolls
            # back to the default/inherited value, not an earlier author rule.
            if value == "inherit" or value in {"unset", "revert"} and name == "visibility":
                value = inherited
            elif value in {"initial", "unset", "revert"}:
                value = default_display if name == 'display' and value == 'revert' else initial
            computed[name] = value
        attrs = node.attributes
        suppressed = (parent[0] or node.tag in {"template", "noscript"} or "hidden" in attrs
                      or attrs.get("aria-hidden") == "true" or computed["display"] == "none" or computed["opacity"] == 0)
        states[node.mem_id] = (suppressed, computed["visibility"], computed["display"], computed["opacity"])
    if isinstance(tree, _Document):
        tree._screen_state = states
    return states


def login_page(tree: HTMLParser, *, has_public_evidence=False) -> bool:
    title = access_text(tree.css_first("title")).lower()
    body = access_text(tree.css_first("body")).lower()
    markers = ("login required", "please log in", "please sign in", "登录后", "请登录")
    return (any(marker in title for marker in markers)
            or title.strip() in {"login", "sign in", "登录", "用户登录", "会员登录", "1688登录"}
            or not has_public_evidence and any(marker in body for marker in markers))
