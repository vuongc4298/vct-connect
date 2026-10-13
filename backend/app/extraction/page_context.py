"""Bounded source text from already sanitized, identity-checked HTML captures."""
from hashlib import sha256
import json
import re

VERSION = 'page-context.v1'
MAX_CONTEXT_BYTES = 12_000
MAX_SECTIONS = 24
PRIORITY = re.compile(r'售后|退款|退货|换货|赔付|保障|认证|证书|价格|起批|refund|return|exchange|warranty|after.sales|certif|minimum.order|MOQ|payment|price|hậu mãi|hoàn tiền|đổi trả', re.I)


def collect_context(parsed, page, url, html_sha256):
    if page == 'PRODUCT':
        roots = [node for selector in ['#mainPrice', '#mainServices', '#shippingServices', '#description',
                 '#productAttributes', '#productWarning', '#officialInspection', '#productPackInfo']
                 for node in parsed.css(selector)]
    elif page == 'SHOP':
        roots = parsed.css('#pcMainCompanyNameV2, #pcV2ServiceScoreLabel, #pcV2ServiceScoreValue')
        for link in parsed.css('#bd_2_container_0 a[href]'):
            if link.attributes.get('href') == url + 'page/creditdetail.html':
                node = link
                while node and 'module-wrapper' not in node.attributes.get('class', '').split():
                    node = node.parent
                if node: roots.append(node)
    else:
        roots = parsed.css('#pc_card_baseinfo, #pc_card_exhibition')
    sections, seen = [], set()
    for root in roots:
        heading = root.css_first('h1,h2,h3,h4')
        label = ' '.join(heading.text().split())[:120] if heading else root.attributes.get('id', page)
        candidates = root.css('p,li,tr,dl')
        # Include leaf divs, preserving local label/value text within the source module.
        candidates += [node for node in root.css('div') if not node.css('div,p,li,tr,dl')]
        if not candidates: candidates = [root]
        for node in candidates[:500]:
            text = ' '.join(node.text(separator=' ').split())
            if len(text) < 16 or text in seen: continue
            seen.add(text)
            for start in range(0, min(len(text), 6000), 700):
                fragment = text[start:start + 900]
                if len(fragment) < 16: continue
                digest = sha256((url + fragment).encode()).hexdigest()[:16]
                sections.append({'section_id': page.lower() + ':' + digest, 'page': page,
                                 'source_url': url, 'heading': label, 'text': fragment,
                                 'html_sha256': html_sha256, 'source_text_truncated': len(text) > 6000})
    return sections


def select_context(sections, max_bytes=MAX_CONTEXT_BYTES):
    selected, seen, truncated = [], set(), any(item.get('source_text_truncated') for item in sections)
    ranked = sorted(sections, key=lambda item: not bool(PRIORITY.search(item.get('text', ''))))
    for section in ranked:
        if section['section_id'] in seen: continue
        seen.add(section['section_id'])
        candidate = {'version': VERSION, 'sections': selected + [section], 'truncated': False,
                     'selection': 'relevant policies and terms first; bounded captured source text'}
        if len(selected) >= MAX_SECTIONS or len(json.dumps(candidate, ensure_ascii=False).encode()) > max_bytes:
            truncated = True
            continue
        selected.append(section)
    return {'version': VERSION, 'sections': selected, 'truncated': truncated,
            'selection': 'relevant policies and terms first; bounded captured source text'}


def matching_context_sections(context, quote):
    if not isinstance(context, dict) or not isinstance(quote, str) or len(quote.strip()) < 16:
        return []
    # Metadata, URL or field-name matches cannot support a risk assessment.
    return [section for section in context.get('sections', []) if isinstance(section, dict)
            and isinstance(section.get('text'), str) and quote in section['text']]
