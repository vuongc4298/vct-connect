"""Shared inert-source, visible-DOM and static access-wall mechanics.

These helpers tokenize source data; they never execute source scripts.
"""
from html.parser import HTMLParser as SourceParser
import re

from selectolax.parser import HTMLParser

from .evidence import text


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
                self.inert.append(tag)
            elif not self.inert:
                self.parts.append(self.get_starttag_text())

        def handle_startendtag(self, tag, attrs):
            if not self.inert and tag not in {"noscript", "template"}:
                self.parts.append(self.get_starttag_text())

        def handle_endtag(self, tag):
            if self.inert:
                if tag == self.inert[-1]:
                    self.inert.pop()
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
    return HTMLParser("".join(source.parts))


def active(node):
    while node is not None:
        if node.tag in {"template", "noscript"} or "hidden" in node.attributes or node.attributes.get("aria-hidden") == "true":
            return False
        style = re.sub(r"\s+", "", (node.attributes.get("style") or "").lower())
        if "display:none" in style or "visibility:hidden" in style or "visibility:collapse" in style or re.search(
                r"(?:^|;)opacity:(?:0+(?:\.0*)?|\.0+)(?:%|!important|%!important)?(?:;|$)", style):
            return False
        node = node.parent
    return True


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
    hidden_roots = [node for node in tree.css("[hidden], [aria-hidden], [style]")
                    if not active(node) and active(node.parent)]
    for node in hidden_roots:
        node.decompose()
    tree.strip_tags(["script", "style"])


def stylesheet_hidden(tree):
    """Remove identifiable static hiding rules from active inline styles only.

    Simple top-level selectors use the existing CSS selector engine. Conditional
    at-rules and selectors requiring interactive CSS state are not evaluated.
    """
    for style in tree.css('style'):
        if not active(style):
            continue
        css = re.sub(r'/\*[\s\S]*?\*/', '', style.text())
        for match in re.finditer(r'([^{}]+)\{([^{}]*)\}', css):
            prefix = css[:match.start()]
            if prefix.count('{') != prefix.count('}'):
                continue
            selectors, declarations = match[1].strip(), match[2]
            if not re.fullmatch(r'''[A-Za-z0-9_.#\-\s,>+~\[\]="'|*]+''', selectors):
                continue
            properties = dict(re.findall(r'(?:^|;)\s*(display|visibility|opacity)\s*:\s*([^;]+)', declarations.lower()))
            properties = {key: re.sub(r'\s+|!important', '', value) for key, value in properties.items()}
            hidden = properties.get('display') == 'none' or properties.get('visibility') in {'hidden', 'collapse'} or re.fullmatch(r'0+(?:\.0*)?|\.0+', properties.get('opacity', ''))
            if not hidden:
                continue
            try:
                for node in tree.css(selectors):
                    node.attrs['hidden'] = ''
            except ValueError:
                continue


def login_page(tree: HTMLParser, *, has_public_evidence=False) -> bool:
    title = (text(tree.css_first("title")) or "").lower()
    body = (text(tree.css_first("body")) or "")[:2000].lower()
    markers = ("login required", "please log in", "please sign in", "登录后", "请登录")
    return (any(marker in title for marker in markers)
            or title.strip() in {"login", "sign in", "登录", "用户登录", "会员登录", "1688登录"}
            or not has_public_evidence and any(marker in body for marker in markers))
