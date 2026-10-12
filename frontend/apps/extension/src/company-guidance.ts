// Visible cues only. The user controls navigation and closes any CAPTCHA overlay.
export function showCompanyGuidance(mode: "SHOP" | "FACTORY" | "SHOP_CAPTURE" | "FACTORY_CAPTURE", expectedShop: string): boolean {
  document.getElementById("vct-company-guidance")?.remove();
  const selector = mode === "SHOP" ? "#shopNavigation a[href]" : "#hd a, #shopNavigation a, #pcTopNav a";
  const targets = Array.from(document.querySelectorAll<HTMLAnchorElement>(selector))
    .filter(a => a.getClientRects().length && (mode === "SHOP" ? a.href.split("?")[0] === expectedShop
      : /^(工厂档案|工厂介绍|工厂名片|工厂资料|Factory profile)$/i.test((a.textContent || "").trim())));
  const target = targets.length >= 1 && ["SHOP", "FACTORY"].includes(mode) && (mode === "SHOP" || targets.length === 1) ? targets[0] : null;
  if (target) {
    target.style.outline = "4px solid #16a085";
    target.style.outlineOffset = "4px";
    target.scrollIntoView({ block: "center", behavior: "smooth" });
  }
  const cue = document.createElement("aside");
  cue.id = "vct-company-guidance";
  cue.setAttribute("role", "status");
  cue.style.cssText = "position:fixed;top:16px;right:16px;z-index:2147483647;background:#fff;color:#163b32;border:3px solid #16a085;border-radius:12px;padding:18px;max-width:360px;font:16px/1.5 sans-serif;box-shadow:0 6px 24px #0004";
  const message = document.createElement("p");
  message.textContent = mode === "SHOP"
    ? "VCT Connect: Product captured. Click the highlighted supplier name. If a CAPTCHA overlay appears, you can close it with X. When company content is visible, open VCT Connect and click Save shop HTML."
    : mode === "FACTORY"
      ? "VCT Connect: Shop HTML captured and stored. Open Factory profile / 工厂档案 (highlighted when found). Close any CAPTCHA overlay with X if possible, then open VCT Connect and click Save factory HTML & analyze. Or finish with the captured evidence in the extension."
      : mode === "SHOP_CAPTURE"
        ? "VCT Connect: Close the CAPTCHA overlay with X if possible. When the supplier header or company introduction is visible, open the VCT Connect extension and click Save shop HTML. No CAPTCHA solution is required for already visible content."
        : "VCT Connect: Close any CAPTCHA overlay with X if possible. When the factory details are visible, open the extension and click Save factory HTML & analyze.";
  cue.append(message);
  if (!target && mode === "SHOP") {
    const link = document.createElement("a"); link.href = expectedShop; link.textContent = "Open this product's company page"; cue.append(link);
  }
  const close = document.createElement("button"); close.textContent = "Dismiss guidance";
  close.onclick = () => { cue.remove(); if (target) { target.style.outline = ""; target.style.outlineOffset = ""; } };
  cue.append(close); document.body.append(cue);
  return Boolean(target);
}
