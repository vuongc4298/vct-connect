"""Screen visibility expectations independent of extraction implementation."""
from hashlib import sha256

import httpx
import pytest

from backend.app.extraction.browser import access_wall, maybe_render
from backend.app.extraction.dom import active, prune_dom, stylesheet_hidden, tree
from backend.tests.test_browser_fallback import ADAPTERS, fixture


REPRODUCTIONS = [
    ('<style>.wall{display:none}.wall{display:block}</style>', '<div class="wall">Please sign in</div>', 'AUTH_REQUIRED'),
    ('', '<div style="display:none;display:block">Please sign in</div>', 'AUTH_REQUIRED'),
    ('', '<div style="visibility:hidden">Invisible<span style="visibility:visible">Please sign in</span></div>', 'AUTH_REQUIRED'),
    ('<style media="print">.wall{display:none}</style>', '<div class="wall">Please sign in</div>', 'AUTH_REQUIRED'),
    ('<style>.wall{opacity:0%}</style>', '<div class="wall">Please sign in</div>', None),
]


def page(styles, body):
    return '<html><head><title>Product</title>' + styles + '</head><body>' + body + '</body></html>'


@pytest.mark.parametrize('styles,body,expected', REPRODUCTIONS)
def test_recorded_screen_reproductions(styles, body, expected):
    assert access_wall(page(styles, body)) == expected


@pytest.mark.parametrize('styles,inline,expected', [
    ('.wall{display:none}.wall{display:block}', '', 'AUTH_REQUIRED'),
    ('.wall{display:none;display:inline list-item}', '', 'AUTH_REQUIRED'),
    ('.wall{display:none;display:block list-item}', '', 'AUTH_REQUIRED'),
    ('.wall{display:none;display:inline ruby}', '', 'AUTH_REQUIRED'),
    ('.wall{display:none;display:flow}', '', 'AUTH_REQUIRED'),
    ('.wall{display:none;display:ruby}', '', 'AUTH_REQUIRED'),
    ('.wall{display:ruby;display:none}', '', None),
    ('.wall{display:none!important;display:ruby}', '', None),
    ('.wall{display:none;display:ruby!important}', '', 'AUTH_REQUIRED'),
    ('.wall{display:none}.wall{display:ruby}', '', 'AUTH_REQUIRED'),
    ('.wall{display:ruby}.wall{display:none}', '', None),
    ('.wall{display:none}', 'display:none;display:ruby', 'AUTH_REQUIRED'),
    ('.wall{display:none!important;display:inline list-item}', '', None),
    ('.wall{display:none}', 'display:inline list-item', 'AUTH_REQUIRED'),
    ('.wall{display:block}.wall{display:none}', '', None),
    ('#wall{display:block}.wall{display:none}', '', 'AUTH_REQUIRED'),
    ('.wall{display:none}div{display:block}', '', None),
    ('[id="wall"]{display:block}div{display:none}', '', 'AUTH_REQUIRED'),
    ('body > .wall{display:block}.wall{display:none}', '', 'AUTH_REQUIRED'),
    ('#irrelevant,.wall{display:none}body .wall{display:block}', '', 'AUTH_REQUIRED'),
    ('#wall{display:none}', 'display:block', 'AUTH_REQUIRED'),
    ('.wall{display:none!important}', 'display:block', None),
    ('#wall{display:none!important}', 'display:block!important', 'AUTH_REQUIRED'),
    ('.wall{display:block!important}#wall{display:none}', '', 'AUTH_REQUIRED'),
    ('', 'display:none!important;display:block', None),
    ('', 'display:none;display:block!important', 'AUTH_REQUIRED'),
    ('', 'display:none!important;display:block!important', 'AUTH_REQUIRED'),
    ('', 'display:none;display:invalid', None),
    ('', 'display:/**/none;display:block', 'AUTH_REQUIRED'),
    ('.wall{display:none!important;display:block}', '', None),
    ('.wall{display:none;display:invalid}', '', None),
    ('.wall{display:none}#wall{DISPLAY:BLOCK ! IMPORTANT}', '', 'AUTH_REQUIRED'),
    ('.wall{visibility:hidden}#wall{visibility:visible}', '', 'AUTH_REQUIRED'),
    ('.wall{opacity:0}#wall{opacity:1}', '', 'AUTH_REQUIRED'),
    ('.wall{opacity:0!important}', 'opacity:100%', None),
])
def test_cascade_priority(styles, inline, expected):
    html = page('<style>' + styles + '</style>', '<div id="wall" class="wall" style="' + inline + '">Please sign in</div>')
    assert access_wall(html) == expected


@pytest.mark.parametrize('body', [
    '<p>Please<br>sign in</p>',
    '<div>Please</div><div>sign in</div>',
    '<p>Please<span> sign </span>in</p>',
])
def test_access_wall_preserves_text_boundaries(body):
    assert access_wall(page('', body)) == 'AUTH_REQUIRED'


def test_inert_template_keeps_selector_sibling_structure():
    styles = '<style>.hint{display:none}template + .hint{display:block}</style>'
    body = '<template><p>ignored</p></template><p class="hint">Please sign in</p>'
    assert access_wall(page(styles, body)) == 'AUTH_REQUIRED'


def test_css_matching_work_budget_fails_closed_quickly():
    import time
    rules = ''.join(f'.x{i}{{display:block}}' for i in range(4500))
    body = ''.join('<i></i>' for _ in range(1000)) + '<p style="display:none">Please sign in</p>'
    started = time.monotonic()
    parsed = tree(page('<style>' + rules + '</style>', body))
    stylesheet_hidden(parsed)
    assert getattr(parsed, '_screen_work_exhausted', False)
    assert time.monotonic() - started < 2.0
    assert access_wall(page('<style>' + rules + '</style>', body)) == 'PARSE_FAILED'


@pytest.mark.parametrize('parent,child,expected', [
    ('visibility:hidden', 'visibility:visible', 'AUTH_REQUIRED'),
    ('visibility:collapse', 'visibility:visible', 'AUTH_REQUIRED'),
    ('visibility:hidden', 'visibility:initial', 'AUTH_REQUIRED'),
    ('visibility:hidden', 'visibility:inherit', None),
    ('visibility:hidden', 'visibility:unset', None),
    ('visibility:hidden', '', None),
    ('display:none', 'display:block;visibility:visible', None),
    ('opacity:0', 'opacity:1;visibility:visible', None),
    ('opacity:0%', 'opacity:100%', None),
    ('opacity:0.5', 'opacity:inherit', 'AUTH_REQUIRED'),
    ('opacity:0.5', 'opacity:0', None),
])
def test_inheritance_and_subtree_suppression(parent, child, expected):
    body = '<div style="' + parent + '">Hidden own text<span style="' + child + '">Please sign in</span></div>'
    assert access_wall(page('', body)) == expected


@pytest.mark.parametrize('opacity', ['0', '0.0', '.0', '0%', '0.00%', '+0', '-1', '-10%', '0 !important'])
def test_zero_opacity_has_no_barrier_or_selected_text(opacity):
    html = page('<style>.wall{opacity:' + opacity + '}</style>', '<div class="wall">Captcha</div><p>Public text</p>')
    parsed = tree(html)
    stylesheet_hidden(parsed)
    prune_dom(parsed)
    assert parsed.body.text(strip=True) == 'Public text'
    assert access_wall(html) is None


@pytest.mark.parametrize('styles', [
    '<style media="print">.wall{display:none}</style>',
    '<style media="PRINT">.wall{display:none}</style>',
    '<style media="speech">.wall{display:none}</style>',
    '<style type="text/plain">.wall{display:none}</style>',
    '<style>@media print {.wall{display:none}}</style>',
    '<style>@supports(display:block){.wall{display:none}}</style>',
    '<style>@keyframes disappear{from{opacity:0}to{opacity:1}}</style>',
    '<style>.wall:hover{display:none}</style>',
    '<link rel="stylesheet" href="https://external.invalid/style.css">',
])
def test_unsupported_or_non_screen_styles_do_not_hide_screen_text(styles):
    assert access_wall(page(styles, '<div class="wall">Please sign in</div>')) == 'AUTH_REQUIRED'


@pytest.mark.parametrize('styles', [
    '<style media="screen">.wall{display:none}</style>',
    '<style media="all">.wall{display:none}</style>',
    '<style media="print, screen">.wall{display:none}</style>',
    '<style>.wall{display:none}</style>',
])
def test_supported_screen_styles_hide_text(styles):
    assert access_wall(page(styles, '<div class="wall">Captcha</div>')) is None


def test_hidden_ancestor_keeps_visible_descendants_and_ignores_own_text():
    parsed = tree(page('<style>.parent{visibility:hidden}.visible{visibility:visible}</style>',
        '<div class="parent">Captcha<span>Hidden</span><b class="visible">Public</b>Tail</div>'))
    stylesheet_hidden(parsed)
    assert not active(parsed.css_first('.parent'))
    assert active(parsed.css_first('.visible'))
    prune_dom(parsed)
    assert parsed.body.text(strip=True) == 'Public'
    prune_dom(parsed)
    assert parsed.body.text(strip=True) == 'Public'


@pytest.mark.parametrize('attribute', ['hidden', 'aria-hidden="true"'])
def test_explicit_hidden_attributes_suppress_visible_children(attribute):
    assert access_wall(page('', '<div ' + attribute + '><span style="visibility:visible">Captcha</span></div>')) is None


@pytest.mark.parametrize('styles', [
    '.wall {display: none; broken; display: block}',
    '.wall[data-label="unclosed] {display:none}',
    '.wall {display:unknown; opacity:invalid; visibility:bogus}',
    '.wall' + '(' * 1500 + ')' * 1500 + '{display:none}',
    '.wall[data-label=' + '[' * 1500 + ']' * 1500 + '] {display:none}',
])
def test_malformed_or_unsupported_css_has_a_finite_outcome(styles):
    assert access_wall(page('<style>' + styles + '</style>', '<div class="wall">Please sign in</div>')) == 'AUTH_REQUIRED'


def test_pruning_suppressed_document_is_repeatable():
    parsed = tree('<html style="display:none"><body>Captcha</body></html>')
    prune_dom(parsed)
    prune_dom(parsed)
    assert not parsed.css('body')


@pytest.mark.parametrize('platform', ADAPTERS)
@pytest.mark.parametrize('styles,body,expected', REPRODUCTIONS)
def test_sparse_adapter_access_outcomes_have_no_supplier_snapshot(platform, styles, body, expected):
    source, _ = fixture(platform)
    adapter, parser = ADAPTERS[platform]
    html = page(styles, body)
    parsed = parser(html, source)
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, headers={'content-type': 'text/html'}, text=html))) as client:
        fetched = adapter(source, client=client, dns_check=lambda _: True)
    for result in (parsed, fetched):
        assert result['extraction_status'] == (expected or 'PARSE_FAILED')
        assert 'supplier_data' not in result and 'raw_payload' not in result


@pytest.mark.parametrize('platform', ADAPTERS)
@pytest.mark.parametrize('styles,body,expected', REPRODUCTIONS)
def test_fallback_access_and_failure_preserve_http_evidence(platform, styles, body, expected):
    source, html = fixture(platform)
    original = ADAPTERS[platform][1](html, source)
    html = html.replace('</head>', styles + '</head>').replace('<body>', '<body>' + body)
    calls = []
    def fail_renderer(*args):
        calls.append(args)
        return {'code': 'RUNTIME_FAILED'}
    result = maybe_render(original, html, html.encode(), enabled=True, renderer=fail_renderer)
    if expected:
        assert result['extraction_status'] == expected
        assert 'supplier_data' not in result and 'raw_payload' not in result
        assert not calls
    else:
        assert result is original
        assert len(calls) == 1


@pytest.mark.parametrize('platform', ADAPTERS)
@pytest.mark.parametrize('hidden', [False, True])
def test_selected_dom_fields_and_original_hash_follow_visibility(platform, hidden):
    source, html = fixture(platform, render=False)
    if platform == '1688':
        evidence = '<div class="review-item"><span class="selected">Public review</span></div>'
        field = 'reviews'
    elif platform == 'TAOBAO':
        evidence = '<div class="shopProductShelfArea--test"><div class="shop-item-card"><a href="https://item.taobao.com/item.htm?id=777"><span class="title--test selected">Public product</span></a></div></div>'
        field = 'products'
    else:
        evidence = '<div class="product-review"><div class="product-review-list"><div class="r-relative r-whitespace-normal selected">Public review</div></div></div>'
        field = 'reviews'
    rule = '.selected{opacity:0%}' if hidden else '.selected{visibility:hidden}.selected{visibility:visible}'
    html = html.replace('</head>', '<style>' + rule + '</style></head>').replace('</body>', evidence + '</body>')
    adapter, parser = ADAPTERS[platform]
    result = parser(html, source)
    assert result['extraction_status'] == 'PARTIAL'
    if platform == 'TAOBAO':
        # The product link is visible even when its title is transparent.
        assert result['supplier_data'][field] == [{
            'offer_id': '777', 'title': None if hidden else 'Public product',
            'source_url': 'https://item.taobao.com/item.htm?id=777',
        }]
    else:
        assert bool(result['supplier_data'][field]) is not hidden
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, headers={'content-type': 'text/html; charset=utf-8'}, content=html.encode()))) as client:
        fetched = adapter(source, client=client, dns_check=lambda _: True)
    assert fetched['supplier_data'][field] == result['supplier_data'][field]
    assert fetched['raw_payload']['html_sha256'] == sha256(html.encode()).hexdigest()


@pytest.mark.parametrize('property,hidden', [('display', 'none'), ('visibility', 'hidden'), ('opacity', '0')])
@pytest.mark.parametrize('placement', ['stylesheet', 'inline'])
@pytest.mark.parametrize('important', ['', '!important'])
def test_author_revert_supersedes_author_hiding(property, hidden, placement, important):
    declarations = f'{property}:{hidden}{important};{property}:revert{important}'
    styles = '<style>.wall{' + declarations + '}</style>' if placement == 'stylesheet' else ''
    inline = declarations if placement == 'inline' else ''
    assert access_wall(page(styles, '<p class="wall" style="' + inline + '">Please sign in</p>')) == 'AUTH_REQUIRED'


@pytest.mark.parametrize('property,hidden,expected', [('display', 'none', None), ('visibility', 'hidden', None), ('opacity', '0', None)])
def test_revert_cannot_override_important_hiding(property, hidden, expected):
    assert access_wall(page('<style>.wall{' + property + ':' + hidden + '!important}</style>',
        '<p class="wall" style="' + property + ':revert">Please sign in</p>')) == expected


@pytest.mark.parametrize('placement', ['stylesheet', 'inline'])
@pytest.mark.parametrize('parent,expected', [('hidden', None), ('visible', 'AUTH_REQUIRED')])
def test_visibility_revert_inherits_after_author_rollback(placement, parent, expected):
    declarations = 'visibility:visible!important;visibility:revert!important'
    styles = '<style>.wall{' + declarations + '}</style>' if placement == 'stylesheet' else ''
    inline = declarations if placement == 'inline' else ''
    assert access_wall(page(styles, '<div style="visibility:' + parent + '"><p class="wall" style="' + inline + '">Please sign in</p></div>')) == expected


@pytest.mark.parametrize('link_style,title_style,selected,title', [
    ('visibility:hidden', '', False, None),
    ('visibility:hidden', 'visibility:visible', True, 'Public product'),
    ('', 'visibility:hidden', True, None),
    ('display:none', 'visibility:visible', False, None),
    ('opacity:0', 'visibility:visible', False, None),
])
def test_taobao_shop_selects_only_visible_links_or_restored_descendants(link_style, title_style, selected, title):
    source, html = fixture('TAOBAO', render=False)
    evidence = ('<div class="shopProductShelfArea--test"><div class="shop-item-card">'
                '<a style="' + link_style + '" href="https://item.taobao.com/item.htm?id=777">'
                '<span class="title--test" style="' + title_style + '">Public product</span></a></div></div>')
    html = html.replace('</body>', evidence + '</body>')
    result = ADAPTERS['TAOBAO'][1](html, source)
    expected = [{'offer_id': '777', 'title': title, 'source_url': 'https://item.taobao.com/item.htm?id=777'}]
    assert result['extraction_status'] == 'PARTIAL'
    assert result['supplier_data']['products'] == (expected if selected else None)
    assert result['raw_payload']['public_fields']['products'] == (expected if selected else [])
    assert ('products' in result['supplier_data']['missing_fields']) is not selected
    assert result['raw_payload']['html_sha256'] == sha256(html.encode()).hexdigest()


@pytest.mark.parametrize('style,expected', [('', 'AUTH_REQUIRED'), ('visibility:hidden', 'PARSE_FAILED'), ('opacity:0', 'PARSE_FAILED'), ('display:none', 'PARSE_FAILED')])
def test_alibaba_password_access_classification_requires_visible_control(style, expected):
    source, _ = fixture('ALIBABA', render=False)
    html = page('', '<form><input type="password" style="' + style + '"></form>')
    result = ADAPTERS['ALIBABA'][1](html, source)
    assert result['extraction_status'] == expected
    assert 'supplier_data' not in result and 'raw_payload' not in result


@pytest.mark.parametrize('hidden_field', ['supplier_name', 'products'])
@pytest.mark.parametrize('style', ['visibility:hidden', 'opacity:0%', 'display:none'])
def test_model_free_1688_hidden_headings_are_absent_from_normalized_and_raw_evidence(hidden_field, style):
    source, _ = fixture('1688', render=False)
    supplier_style = style if hidden_field == 'supplier_name' else ''
    title_style = style if hidden_field == 'products' else ''
    html = page('', f'<link rel="canonical" href="{source}">'
        f'<div class="shop-company-name"><h1 style="{supplier_style}">Public supplier</h1></div>'
        f'<div class="title-content"><h1 style="{title_style}">Public product</h1></div>')
    result = ADAPTERS['1688'][1](html, source)
    data, raw = result['supplier_data'], result['raw_payload']
    assert result['extraction_status'] == 'PARTIAL'
    assert data[hidden_field] is None and hidden_field in data['missing_fields']
    assert data['completeness'] == round(1 / 12, 4)
    assert len(data['missing_fields']) == 11
    assert data['supplier_name'] == (None if hidden_field == 'supplier_name' else 'Public supplier')
    assert data['products'] == (None if hidden_field == 'products' else [{'offer_id': '987654321012', 'title': 'Public product'}])
    assert raw['public_fields']['title'] == (None if hidden_field == 'products' else 'Public product')
    assert all(value is None for value in raw['public_fields']['shop_info'].values())
    assert raw['html_sha256'] == sha256(html.encode()).hexdigest()


@pytest.mark.parametrize('rules,expected', [
    ('[data-x="]"]{display:none}', None),
    ('[data-x="]"]{display:none}p{display:block}', None),
    ('[data-x="]"]{display:none}[data-x="]"]{display:block}', 'AUTH_REQUIRED'),
    ('[data-x="]"]{display:none}p{display:block!important}', 'AUTH_REQUIRED'),
])
def test_quoted_bracket_selector_keeps_specificity_priority_and_order(rules, expected):
    assert access_wall(page('<style>' + rules + '</style>', '<p data-x="]">Please sign in</p>')) == expected


@pytest.mark.parametrize('platform', ADAPTERS)
@pytest.mark.parametrize('rules,selected', [
    ('[data-x="]"]{display:none}', False),
    ('[data-x="]"]{display:none}[data-x="]"]{display:inline list-item}', True),
    ('[data-x="]"]{display:none!important}[data-x="]"]{display:inline list-item}', False),
    ('[data-x="]"]{display:none;display:ruby}', True),
    ('[data-x="]"]{display:ruby;display:none}', False),
    ('[data-x="]"]{display:none!important;display:ruby}', False),
    ('[data-x="]"]{display:none;display:ruby!important}', True),
])
def test_supported_css_corrections_control_selected_evidence_and_original_hash(platform, rules, selected):
    source, html = fixture(platform, render=False)
    if platform == '1688':
        evidence, field = '<p class="review-item" data-x="]">Public review</p>', 'reviews'
    elif platform == 'TAOBAO':
        evidence, field = ('<div class="shopProductShelfArea--test"><div class="shop-item-card">'
            '<a data-x="]" href="https://item.taobao.com/item.htm?id=777">'
            '<span class="title--test">Public product</span></a></div></div>'), 'products'
    else:
        evidence, field = ('<div class="product-review"><div class="product-review-list">'
            '<div class="r-relative r-whitespace-normal" data-x="]">Public review</div></div></div>'), 'reviews'
    html = html.replace('</head>', '<style>' + rules + '</style></head>').replace('</body>', evidence + '</body>')
    result = ADAPTERS[platform][1](html, source)
    assert result['extraction_status'] == 'PARTIAL'
    data, raw = result['supplier_data'], result['raw_payload']
    assert bool(data[field]) is selected
    assert bool(raw['public_fields']['review_bodies' if platform == 'ALIBABA' else field]) is selected
    assert (field in data['missing_fields']) is not selected
    assert raw['html_sha256'] == sha256(html.encode()).hexdigest()


@pytest.mark.parametrize('platform', ADAPTERS)
@pytest.mark.parametrize('wall', [True, False])
def test_exhausted_cascade_rejects_models_and_hidden_selected_evidence(platform, wall):
    source, html = fixture(platform)
    if platform == '1688':
        model = '<script>})(window.contextPath,{"result":{"data":{"productTitle":{"fields":{"shopInfo":{"companyName":"Public supplier"}}},"Root":{"fields":{"dataJson":{"offerBaseInfo":{"offerId":"987654321012"}}}}}}})</script>'
        html = html.replace('</body>', model + '</body>')
    assert ADAPTERS[platform][1](html, source)['extraction_status'] == 'PARTIAL'
    rules = '.x{display:block}' * 4500 + '.private{display:none}'
    evidence = '<p>Captcha</p>' if wall else '<div class="private review-item product-review"><div class="product-review-list"><div class="r-relative r-whitespace-normal">HIDDEN_REVIEW_SENTINEL</div></div></div>'
    nodes = '<i class="x"></i>' if platform == '1688' and wall else '<i></i>'
    html = html.replace('</head>', '<style>' + rules + '</style></head>').replace('</body>', nodes * 1000 + evidence + '</body>')
    parser_result = ADAPTERS[platform][1](html, source)
    calls = []
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, headers={'content-type': 'text/html'}, content=html.encode()))) as client:
        fetched = ADAPTERS[platform][0](source, client=client, dns_check=lambda _: True,
            browser_fallback=True, browser_renderer=lambda *args: calls.append(args))
    for result in (parser_result, fetched):
        assert result['extraction_status'] == 'PARSE_FAILED' and result['reason'] == 'PARSER_LIMIT'
        assert 'supplier_data' not in result and 'raw_payload' not in result and 'reviews' not in result
        assert 'HIDDEN_REVIEW_SENTINEL' not in str(result)
    assert not calls
    original = ADAPTERS[platform][1](fixture(platform)[1], source)
    selected = maybe_render(original, html, html.encode(), enabled=True, renderer=lambda *args: calls.append(args))
    assert selected['extraction_status'] == 'PARSE_FAILED' and selected['reason'] == 'PARSER_LIMIT'
    assert 'supplier_data' not in selected and 'raw_payload' not in selected and not calls


@pytest.mark.parametrize('body,status', [
    ('<p>cap<span>tcha</span></p>', 'BLOCKED'),
    ('<p>Please<br>sign in</p>', 'AUTH_REQUIRED'),
    ('<div>Please</div><div>sign in</div>', 'AUTH_REQUIRED'),
    *[(f'<span style="display:{value}">Please</span><span style="display:{value}">sign in</span>', 'AUTH_REQUIRED')
      for value in ('block flow', 'block flow-root', 'block flex', 'block grid', 'block list-item')],
    ('<p>cap<span style="display:none">IGNORE</span>tcha</p>', 'BLOCKED'),
    ('<p style="visibility:hidden"><span style="visibility:visible">cap<b>tcha</b></span></p>', 'BLOCKED'),
])
@pytest.mark.parametrize('platform', ADAPTERS)
def test_access_text_consumers_preserve_inline_and_layout_boundaries(platform, body, status):
    source, _ = fixture(platform)
    html = page('', body)
    assert access_wall(html) == status
    parsed = ADAPTERS[platform][1](html, source)
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, headers={'content-type': 'text/html'}, text=html))) as client:
        fetched = ADAPTERS[platform][0](source, client=client, dns_check=lambda _: True)
    for result in (parsed, fetched):
        assert result['extraction_status'] == status
        assert 'supplier_data' not in result and 'raw_payload' not in result


@pytest.mark.parametrize('platform', ADAPTERS)
@pytest.mark.parametrize('style,css', [
    ('display:inline', ''),
    ('display:initial', ''),
    ('display:unset', ''),
    ('display:inline flow', ''),
    ('display:inline flex', ''),
    ('', '.inline{display:inline}'),
])
def test_access_text_respects_explicit_inline_display_on_block_tags(platform, style, css):
    source, _ = fixture(platform)
    html = page('<style>' + css + '</style>', 'cap<div class="inline" style="' + style + '">tcha</div>')
    assert access_wall(html) == 'BLOCKED'
    parsed = ADAPTERS[platform][1](html, source)
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, headers={'content-type': 'text/html'}, text=html))) as client:
        fetched = ADAPTERS[platform][0](source, client=client, dns_check=lambda _: True)
    for result in (parsed, fetched):
        assert result['extraction_status'] == 'BLOCKED'
        assert 'supplier_data' not in result and 'raw_payload' not in result


def test_hidden_taobao_link_is_not_admitted_by_visible_following_sibling():
    source, html = fixture('TAOBAO', render=False)
    evidence = '<div class="shopProductShelfArea--test"><div class="shop-item-card"><a style="visibility:hidden" href="https://item.taobao.com/item.htm?id=888">Hidden product</a><span class="title--test">Visible sibling</span></div></div>'
    html = html.replace('</body>', evidence + '</body>')
    result = ADAPTERS['TAOBAO'][1](html, source)
    assert result['extraction_status'] == 'PARTIAL'
    assert result['supplier_data']['products'] is None
    assert 'products' in result['supplier_data']['missing_fields']
    assert result['raw_payload']['public_fields']['products'] == []
    assert result['raw_payload']['html_sha256'] == sha256(html.encode()).hexdigest()
