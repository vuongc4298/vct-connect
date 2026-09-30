export type SelectedCapture = {
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

export function supportedOffer(url: string): { sourceUrl: string; offerId: string } | null {
  try {
    const parsed = new URL(url);
    const match = /^\/offer\/([0-9]{6,20})\.html$/.exec(parsed.pathname);
    if (parsed.protocol !== "https:" || parsed.host !== "detail.1688.com" || !match || parsed.hash) return null;
    return { sourceUrl: `https://detail.1688.com${parsed.pathname}`, offerId: match[1] };
  } catch { return null; }
}

// This function is injected only after a popup action grants activeTab. Keep it self-contained.
export function captureSelectedDom(): SelectedCapture {
  const match = /^\/offer\/([0-9]{6,20})\.html$/.exec(location.pathname);
  if (location.protocol !== "https:" || location.host !== "detail.1688.com" || !match) {
    throw new Error("Open a supported 1688 offer first");
  }
  function selectedText(selectors: string, maximum: number): string | undefined {
    for (const element of document.querySelectorAll<HTMLElement>(selectors)) {
      if (!element.getClientRects().length) continue;
      const style = getComputedStyle(element);
      if (style.visibility === "hidden" || style.display === "none") continue;
      const text = (element.innerText || "").replace(/\s+/g, " ").trim();
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
