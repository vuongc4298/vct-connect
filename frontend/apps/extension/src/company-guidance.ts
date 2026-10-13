// Visible cues only. The user controls navigation and closes any CAPTCHA overlay.
export function showCompanyGuidance(mode: "SHOP" | "FACTORY" | "SHOP_CAPTURE" | "FACTORY_CAPTURE", expectedShop: string, language: "vi" | "en" = "vi"): boolean {
  const previous = document.getElementById("vct-company-guidance");
  previous?.dispatchEvent(new Event("vct-dismiss"));
  previous?.remove();
  const selector = mode === "SHOP" ? "#shopNavigation a[href]" : "#hd a, #shopNavigation a, #pcTopNav a";
  const targets = Array.from(document.querySelectorAll<HTMLAnchorElement>(selector))
    .filter(a => a.getClientRects().length && (mode === "SHOP" ? new URL(a.href).origin + new URL(a.href).pathname === expectedShop
      : /^(工厂档案|工厂介绍|工厂名片|工厂资料|Factory profile)$/i.test((a.textContent || "").trim())));
  const target = targets.length >= 1 && ["SHOP", "FACTORY"].includes(mode) && (mode === "SHOP" || targets.length === 1)
    ? targets.find(a => a.classList.contains("shop-company-name")) || targets[0] : null;
  const highlight = target?.querySelector<HTMLElement>("h1") || target;
  const originalStyle = highlight?.getAttribute("style");
  if (highlight) {
    // An inset ring remains visible inside the product card's clipped layout.
    highlight.style.setProperty("box-shadow", "inset 0 0 0 3px #087d70", "important");
    highlight.style.setProperty("background-color", "#dcfce7", "important");
    highlight.style.setProperty("border-radius", "6px", "important");
    highlight.style.setProperty("outline", "3px solid #087d70", "important");
    highlight.style.setProperty("outline-offset", "-3px", "important");
    highlight.scrollIntoView({ block: "center", behavior: "smooth" });
  }
  const cue = document.createElement("aside");
  cue.id = "vct-company-guidance";
  cue.setAttribute("role", "status");
  cue.lang = language;
  // The marketplace's translation layer can rewrite injected Vietnamese text.
  cue.setAttribute("translate", "no");
  cue.classList.add("notranslate");
  cue.style.cssText = "position:fixed;top:16px;right:16px;z-index:2147483647;background:#fff;color:#163b32;border:2px solid #087d70;border-radius:16px;padding:18px;max-width:320px;font:15px/1.5 system-ui,sans-serif;box-shadow:0 8px 32px #0003";
  const title = document.createElement("strong");
  title.textContent = language === "vi" ? "VCT Connect · Bước tiếp theo" : "VCT Connect · Next step";
  cue.append(title);
  const message = document.createElement("p");
  const messages = language === "vi" ? {
    SHOP: "Đã thu thập sản phẩm. Nhấn tên nhà cung cấp được tô xanh, rồi mở tiện ích và chọn Lưu HTML cửa hàng.",
    FACTORY: "Đã lưu cửa hàng. Mở Hồ sơ nhà máy / Factory profile / 工厂档案, rồi chọn Lưu HTML nhà máy và phân tích trong tiện ích.",
    SHOP_CAPTURE: "Khi tên nhà cung cấp hoặc phần giới thiệu công ty hiển thị, mở tiện ích và chọn Lưu HTML cửa hàng.",
    FACTORY_CAPTURE: "Khi thông tin nhà máy hiển thị, mở tiện ích và chọn Lưu HTML nhà máy và phân tích.",
  } : {
    SHOP: "Product captured. Click the green supplier name, then open the extension and choose Save shop HTML.",
    FACTORY: "Shop saved. Open Factory profile / 工厂档案, then choose Save factory HTML & analyze in the extension.",
    SHOP_CAPTURE: "When the supplier header or company introduction is visible, open the extension and choose Save shop HTML.",
    FACTORY_CAPTURE: "When factory details are visible, open the extension and choose Save factory HTML & analyze.",
  };
  message.textContent = messages[mode];
  cue.append(message);
  if (!target && mode === "SHOP") {
    const link = document.createElement("a"); link.href = expectedShop; link.textContent = language === "vi" ? "Mở cửa hàng nhà cung cấp ↗" : "Open linked supplier shop ↗"; cue.append(link);
  }
  const note = document.createElement("p"); note.style.cssText = "font-size:12px;color:#5c716b";
  note.textContent = language === "vi" ? "Nếu CAPTCHA che nội dung, bạn có thể đóng bằng X khi thông tin đã hiển thị." : "You can close a CAPTCHA overlay with X when the company content is already visible.";
  cue.append(note);
  const cleanup = () => {
    if (highlight) { if (originalStyle === null || originalStyle === undefined) highlight.removeAttribute("style"); else highlight.setAttribute("style", originalStyle); }
    cue.remove();
  };
  cue.addEventListener("vct-dismiss", cleanup, { once: true });
  const close = document.createElement("button"); close.textContent = language === "vi" ? "Đóng hướng dẫn" : "Dismiss guidance";
  close.style.cssText = "border:1px solid #ccdcd6;border-radius:8px;background:#f5faf7;color:#163b32;padding:8px 12px;cursor:pointer;font:inherit";
  close.onclick = cleanup;
  cue.append(close); document.body.append(cue);
  return Boolean(target);
}
