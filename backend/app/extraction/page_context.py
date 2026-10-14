"""Bounded source text from already sanitized, identity-checked HTML captures."""
from hashlib import sha256
import json
import re

VERSION = 'page-context.v1'
MAX_CONTEXT_BYTES = 12_000
MAX_SECTIONS = 24
LLM_CONTEXT_BYTES = 4_000
POLICY = re.compile(r'售后|退款|退货|换货|赔付|refund|return|exchange|warranty|after.sales|dispute|compensation|payment|MOQ|minimum.order|hậu mãi|hoàn tiền|đổi trả', re.I)
BOILERPLATE = re.compile(r'pre.event price|underlined price|uncrossed price|release price|price under (?:non.)?platform activities|same style:|跨平台|划线价格|活动前价格', re.I)
POLICY_DETAIL = re.compile(r'售后|退款|退货|换货|赔付|refund|return shipping|return damaged|exchange|warranty|after.sales|dispute|compensation|hoàn tiền|đổi trả|hậu mãi', re.I)


def supplemental_context(context, evidence, max_bytes=LLM_CONTEXT_BYTES):
    """Send only new relevant passages; retain full source provenance for audit."""
    def fragments(value):
        if isinstance(value, str):
            yield ' '.join(value.split())
        elif isinstance(value, dict):
            for item in value.values():
                yield from fragments(item)
        elif isinstance(value, list):
            for item in value:
                yield from fragments(item)

    represented = list(fragments(evidence))
    candidates = []
    for section in context.get('sections', []):
        if not isinstance(section, dict) or not isinstance(section.get('text'), str):
            continue
        text = ' '.join(section['text'].split())
        if BOILERPLATE.search(text) or not POLICY.search(text):
            continue
        # Keep one concise policy excerpt even when buried in a general field;
        # its explicit policy routing is useful and adds little repeated text.
        if any(text in existing for existing in represented) and not POLICY_DETAIL.search(text):
            continue
        if any(text in existing['text'] for existing in candidates):
            continue
        candidates = [existing for existing in candidates if existing['text'] not in text]
        candidates.append({**section, 'text': text})
    packet = select_context(candidates, max_bytes=max(0, max_bytes - 128))
    packet['selection'] = 'fact-first: new policies and terms only; duplicates and platform price definitions omitted'
    packet['truncated'] = packet['truncated'] or bool(context.get('truncated'))
    return packet
PRIORITY = re.compile(r'售后|退款|退货|换货|赔付|保障|认证|证书|价格|起批|refund|return|exchange|warranty|after.sales|certif|minimum.order|MOQ|payment|price|hậu mãi|hoàn tiền|đổi trả', re.I)


def collect_context(parsed, page, url, html_sha256):
    if '.alibaba.com/' in url:
        roots = parsed.css('#vct-alibaba-policy, #vct-alibaba-price, #vct-alibaba-introduction, #vct-alibaba-company-claims, #vct-alibaba-shop-claims')
    elif page == 'PRODUCT':
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
        # Preserve compact label/value groups as well as leaf text.
        candidates += [node for node in root.css('div')
                       if not node.css('p,li,tr,dl') and len(node.css('div')) <= 8
                       and len(' '.join(node.text(separator=' ').split())) <= 900]
        if not candidates: candidates = [root]
        for node in candidates[:500]:
            text = ' '.join(node.text(separator=' ').split())
            minimum = 6 if re.search(r'[\u3400-\u9fff]', text) else 16
            if len(text) < minimum or text in seen: continue
            seen.add(text)
            for start in range(0, min(len(text), 6000), 700):
                fragment = text[start:start + 900]
                if len(fragment) < minimum: continue
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
    if not isinstance(context, dict) or not isinstance(quote, str):
        return []
    minimum = 6 if re.search(r'[\u3400-\u9fff]', quote) else 16
    if len(quote.strip()) < minimum: return []
    # Metadata, URL or field-name matches cannot support a risk assessment.
    return [section for section in context.get('sections', []) if isinstance(section, dict)
            and isinstance(section.get('text'), str) and quote in section['text']]
