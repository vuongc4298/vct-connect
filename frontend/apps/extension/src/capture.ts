export type LegacyCapture = {
  source_url: string;
  canonical_url?: string;
  offer_id: string;
  fields: {
    supplier_name?: string;
    product_title?: string;
    price_text?: string;
    company_location?: string;
    review_count?: number;
  };
};

export type TaobaoCapture = {
  source_url: string; canonical_url?: string; source_kind: "item" | "shop"; source_id: string;
  fields: { supplier_name?: string; product_title?: string; shop_metrics?: string[];
    reviews?: { text: string; original_length: number }[]; products?: { source_url: string; title?: string }[] };
};
export type SelectedCapture = LegacyCapture | TaobaoCapture;

export function supportedOffer(url: string): { sourceUrl: string; offerId: string; kind?: "item" | "shop" } | null {
  try {
    const parsed = new URL(url);
    const match = /^\/offer\/([0-9]{6,20})\.html$/.exec(parsed.pathname);
    if (parsed.protocol !== "https:" || parsed.port || parsed.username || parsed.password || parsed.hash || /[\s\\]/.test(url)
        || /^https:\/\/[^/]*:/.test(url) || url.length > 2048) return null;
    if (parsed.host === "detail.1688.com" && match) return { sourceUrl: `https://detail.1688.com${parsed.pathname}`, offerId: match[1] };
    const ids = parsed.searchParams.getAll("id");
    if (parsed.host === "item.taobao.com" && parsed.pathname === "/item.htm" && ids.length === 1 && /^[1-9][0-9]{0,19}$/.test(ids[0])) {
      return { sourceUrl: `https://item.taobao.com/item.htm?id=${ids[0]}`, offerId: ids[0], kind: "item" };
    }
    const shop = /^shop([1-9][0-9]{0,19})\.(?:world\.)?taobao\.com$/.exec(parsed.hostname);
    if (shop && ["/", "/index.htm", "/category.htm"].includes(parsed.pathname)) return {
      sourceUrl: `${parsed.origin}${parsed.pathname}`, offerId: shop[1], kind: "shop",
    };
    return null;
  } catch { return null; }
}

// This function is injected only after a popup action grants activeTab. Keep it self-contained.
export function captureSelectedDom(): SelectedCapture {
  function visible(element: HTMLElement): boolean {
    if (element.closest?.('template, noscript, [hidden], [aria-hidden="true"]')) return false;
    if (!element.getClientRects().length) return false;
    for (let current: HTMLElement | null = element; current; current = current.parentElement) {
      const style = getComputedStyle(current);
      if (style.visibility === "hidden" || style.visibility === "collapse" || style.display === "none" || style.opacity === "0") return false;
    }
    return true;
  }
  function nodes(root: Document | HTMLElement, prefix: string): HTMLElement[] {
    return Array.from(root.querySelectorAll<HTMLElement>(`[class*="${prefix}"]`)).filter(element =>
      Array.from(element.classList).some(token => token.startsWith(prefix)) && visible(element));
  }
  function renderedText(element: HTMLElement): string {
    if (!Array.from(element.querySelectorAll<HTMLElement>("*")).some(child => !visible(child))) return element.innerText || "";
    // innerText can include rendered aria-hidden or transparent descendants.
    // Read text nodes only inside the selected region and skip hidden parents.
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    const parts: string[] = [];
    let previousBlock: HTMLElement | null = null;
    function block(parent: HTMLElement): HTMLElement {
      for (let current: HTMLElement | null = parent; current && current !== element; current = current.parentElement) {
        if (["block", "list-item", "flex", "grid", "table-row"].includes(getComputedStyle(current).display)) return current;
      }
      return element;
    }
    function lineBreak() { if (parts.length && !parts[parts.length - 1].endsWith("\n")) parts.push("\n"); }
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (node.nodeType === 1) {
        const child = node as HTMLElement;
        if (child.tagName.toLowerCase() === "br" && visible(child)) lineBreak();
      } else if (node.parentElement && visible(node.parentElement)) {
        const currentBlock = block(node.parentElement);
        if (previousBlock && previousBlock !== currentBlock) lineBreak();
        parts.push(node.textContent || "");
        previousBlock = currentBlock;
      }
    }
    return parts.join("");
  }
  function rawText(element: HTMLElement, maximum: number): string | undefined {
    const text = renderedText(element);
    return text?.trim() && Array.from(text).length <= maximum ? text : undefined;
  }
  const currentUrl = new URL(location.href);
  const itemIds = currentUrl.searchParams.getAll("id");
  const shop = /^shop([1-9][0-9]{0,19})\.(?:world\.)?taobao\.com$/.exec(location.hostname);
  const item = location.host === "item.taobao.com" && location.pathname === "/item.htm"
    && itemIds.length === 1 && /^[1-9][0-9]{0,19}$/.test(itemIds[0]);
  if (location.protocol === "https:" && !location.port && !location.hash && !currentUrl.username && !currentUrl.password
      && (item || shop && ["/", "/index.htm", "/category.htm"].includes(location.pathname))) {
    const canonicalNodes = Array.from(document.querySelectorAll<HTMLLinkElement>("link[rel]")).filter(link =>
      (link.getAttribute("rel") || "").toLowerCase().split(/\s+/).includes("canonical"));
    if (canonicalNodes.length > 1) throw new Error("Ambiguous canonical page identity");
    const canonical = canonicalNodes[0]?.href;
    if (canonical) {
      let hint: URL;
      try { hint = new URL(canonical); }
      catch { throw new Error("Canonical URL does not match the active page"); }
      const ids = hint.searchParams.getAll("id");
      const hintShop = /^shop([1-9][0-9]{0,19})\.(?:world\.)?taobao\.com$/.exec(hint.hostname);
      const same = item ? hint.host === "item.taobao.com" && hint.pathname === "/item.htm" && ids.length === 1 && ids[0] === itemIds[0]
        : hintShop?.[1] === shop![1] && ["/", "/index.htm", "/category.htm"].includes(hint.pathname);
      if (!same || hint.protocol !== "https:" || hint.port || hint.username || hint.password || hint.hash || /^https:\/\/[^/]*:/.test(canonical))
        throw new Error("Canonical URL does not match the active page");
    }
    function prefix(element: HTMLElement | null, value: string): boolean {
      return !!element && Array.from(element.classList).some(token => token.startsWith(value));
    }
    function supplierContainer(name: HTMLElement): HTMLElement | null {
      const parent = name.parentElement, middle = parent?.parentElement ?? null, outer = middle?.parentElement ?? null;
      if (item && prefix(parent, "shopNameWrap--") && prefix(middle, "shopNameLevelWrapper--") && prefix(outer, "leftWrap--")) return outer;
      if (!item && prefix(parent, "shopNameContainer--") && prefix(middle, "leftContainer--") && prefix(outer, "shopInfo--")) return outer;
      if (!item && prefix(parent, "shopInfo--") && prefix(middle, "leftContainer--") && prefix(outer, "stickyHeaderContent--")) return parent;
      return null;
    }
    const names = nodes(document, "shopName--").filter(name => supplierContainer(name));
    const distinctNames = new Set(names.map(element => renderedText(element).replace(/\s+/g, " ").trim()).filter(Boolean));
    if (distinctNames.size > 1) throw new Error("Ambiguous shop evidence");
    const supplier = names.map(element => rawText(element, 240)).find(Boolean);
    const fields: TaobaoCapture["fields"] = { ...(supplier ? { supplier_name: supplier } : {}) };
    if (item) {
      const titles = nodes(document, "ItemTitle--").flatMap(region => nodes(region, "MainTitle--")
        .flatMap(container => nodes(container, "mainTitle--")));
      if (titles.length > 1) throw new Error("Ambiguous product title");
      const title = titles[0] ? rawText(titles[0], 500) : undefined;
      if (title) fields.product_title = title;
      const reviews = nodes(document, "Comments--").flatMap(section => nodes(section, "Comment--")
        .flatMap(card => nodes(card, "contentWrapper--").flatMap(wrapper => nodes(wrapper, "content--"))))
        .map(element => renderedText(element)).filter(text => text?.trim()).slice(0, 20)
        .map(text => ({ text: Array.from(text).slice(0, 2000).join(""), original_length: Array.from(text).length }));
      if (reviews.length) fields.reviews = reviews;
      const container = names[0] ? supplierContainer(names[0]) : null;
      if (container) fields.shop_metrics = [...nodes(container, "starNum--"), ...nodes(container, "storeLabelItem--")]
        .map(element => rawText(element, 240)).filter((text): text is string => !!text).slice(0, 10);
    } else {
      const products: NonNullable<TaobaoCapture["fields"]["products"]> = [];
      for (const shelf of nodes(document, "shopProductShelfArea--")) {
        for (const card of shelf.querySelectorAll<HTMLElement>(".shop-item-card")) {
          if (!visible(card)) continue;
          const links = [...(card.matches("a[href]") ? [card as HTMLAnchorElement] : []),
            ...card.querySelectorAll<HTMLAnchorElement>("a[href]")];
          for (const link of links) {
            if (!visible(link)) continue;
            let url: URL;
            try { url = new URL(link.href); }
            catch { continue; }
            const ids = url.searchParams.getAll("id");
            if (url.protocol !== "https:" || url.host !== "item.taobao.com" || url.username || url.password || url.hash
                || url.pathname !== "/item.htm" || ids.length !== 1 || !/^[1-9][0-9]{0,19}$/.test(ids[0])) continue;
            const source = `https://item.taobao.com/item.htm?id=${ids[0]}`;
            if (products.some(product => product.source_url === source)) continue;
            const titleNode = nodes(card, "title--")[0];
            const text = titleNode?.getAttribute("title") || (titleNode ? renderedText(titleNode) : undefined);
            const title = text && Array.from(text).length <= 500 ? text : undefined;
            products.push({ source_url: source, ...(title ? { title } : {}) });
            break;
          }
          if (products.length >= 20) break;
        }
        if (products.length >= 20) break;
      }
      if (products.length) fields.products = products;
    }
    const capture: TaobaoCapture = { source_url: item ? `https://item.taobao.com/item.htm?id=${itemIds[0]}` : `${location.origin}${location.pathname}`,
      ...(canonical ? { canonical_url: canonical } : {}), source_kind: item ? "item" : "shop",
      source_id: item ? itemIds[0] : shop![1], fields };
    // Bound the serialized request, preserving declared review extents.
    while (new TextEncoder().encode(JSON.stringify(capture)).length > 16_384) {
      if (fields.reviews?.length) fields.reviews.pop();
      else if (fields.products?.length) fields.products.pop();
      else throw new Error("Selected evidence exceeds 16 KB");
    }
    return capture;
  }
  const match = /^\/offer\/([0-9]{6,20})\.html$/.exec(location.pathname);
  if (location.protocol !== "https:" || location.host !== "detail.1688.com" || !match) {
    throw new Error("Open a supported 1688 offer or Taobao item/shop first");
  }
  function selectedText(selectors: string, maximum: number): string | undefined {
    for (const element of document.querySelectorAll<HTMLElement>(selectors)) {
      if (!visible(element)) continue;
      const text = renderedText(element).replace(/\s+/g, " ").trim();
      if (text) return Array.from(text).slice(0, maximum).join("");
    }
    return undefined;
  }
  const canonical = document.querySelector<HTMLLinkElement>('link[rel="canonical"]')?.href;
  const sourceUrl = `https://detail.1688.com${location.pathname}`;
  const supplierName = selectedText(".shop-company-name h1", 240);
  const productTitle = selectedText(".title-content h1", 500);
  const priceText = selectedText("#mainPrice .price-info", 160);
  return {
    source_url: sourceUrl,
    ...(canonical ? { canonical_url: canonical } : {}),
    offer_id: match[1],
    fields: {
      ...(supplierName ? { supplier_name: supplierName } : {}),
      ...(productTitle ? { product_title: productTitle } : {}),
      ...(priceText ? { price_text: priceText } : {}),
    },
  };
}
