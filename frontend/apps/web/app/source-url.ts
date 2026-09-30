/** Canonical forms emitted by admission; never render an arbitrary result URL. */
export function safeSourceUrl(value: string | undefined): string | null {
  if (!value) return null;
  if (/^https:\/\/detail\.1688\.com\/offer\/[0-9]{6,20}\.html$/.test(value)
    || /^https:\/\/item\.taobao\.com\/item\.htm\?id=[1-9][0-9]{0,19}$/.test(value)
    || /^https:\/\/shop[1-9][0-9]{0,19}\.(?:world\.)?taobao\.com\/(?:index\.htm|category\.htm)?$/.test(value)) return value;
  return null;
}

export function sourceLabel(value: string | undefined): "Taobao" | "1688" {
  const safe = safeSourceUrl(value);
  return safe?.includes("taobao.com") ? "Taobao" : "1688";
}
