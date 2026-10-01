/** Canonical forms emitted by admission; never render an arbitrary result URL. */
export function safeSourceUrl(value: string | undefined): string | null {
  if (!value) return null;
  if (/^https:\/\/detail\.1688\.com\/offer\/[0-9]{6,20}\.html$/.test(value)
    || /^https:\/\/item\.taobao\.com\/item\.htm\?id=[1-9][0-9]{0,19}$/.test(value)
    || /^https:\/\/shop[1-9][0-9]{0,19}\.(?:world\.)?taobao\.com\/(?:index\.htm|category\.htm)?$/.test(value)
    || /^https:\/\/www\.alibaba\.com\/product-detail\/[A-Za-z0-9][A-Za-z0-9-]{0,199}_[1-9][0-9]{0,19}\.html$/.test(value)
    || /^https:\/\/[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.en\.alibaba\.com\/company_profile\.html$/.test(value)) return value;
  return null;
}

export function sourceLabel(value: string | undefined): "Taobao" | "1688" | "Alibaba" {
  const safe = safeSourceUrl(value);
  return safe?.includes("taobao.com") ? "Taobao" : safe?.includes(".alibaba.com/") ? "Alibaba" : "1688";
}
