// Visible cues only. The user controls navigation and closes any CAPTCHA overlay.
export function showCompanyGuidance(mode: "SHOP" | "FACTORY" | "SHOP_CAPTURE" | "FACTORY_CAPTURE", expectedShop: string, language: "vi" | "en" = "vi"): boolean {
  const previous = document.getElementById("vct-company-guidance");
  previous?.dispatchEvent(new Event("vct-dismiss"));
  previous?.remove();
  const alibaba = expectedShop.endsWith(".en.alibaba.com/");
  function visible(a: HTMLElement): boolean {
    if (!a.getClientRects().length) return false;
    if (!alibaba) return true;
    if (a.closest('[hidden],[aria-hidden="true"]')) return false;
    for (let node: HTMLElement | null = a; node; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (style.display === "none" || style.visibility !== "visible" || style.opacity === "0") return false;
    }
    return true;
  }
  const selector = alibaba ? mode === "SHOP" ? ".module_unifed_company_card a[href]" : ".nav-item a[href],a.menu-link[href]" : mode === "SHOP" ? "#shopNavigation a[href]" : "#hd a, #shopNavigation a, #pcTopNav a";
  const targets = Array.from(document.querySelectorAll<HTMLAnchorElement>(selector))
    .filter(a => visible(a) && (alibaba ? (() => {
      const u = new URL(a.href), host = /^([a-z0-9-]+)\.(?:m\.)?en\.alibaba\.com$/.exec(u.hostname);
      return u.protocol === "https:" && !u.port && !u.username && !u.password && !!host && `https://${host[1]}.en.alibaba.com/` === expectedShop &&
        (mode === "SHOP" ? ["/", "/index.html"].includes(u.pathname) : u.pathname === "/company_profile.html");
    })() : mode === "SHOP" ? new URL(a.href).origin + new URL(a.href).pathname === expectedShop
      : /^(工厂档案|工厂介绍|工厂名片|工厂资料|Factory profile)$/i.test((a.textContent || "").trim())));
  const target = targets.length >= 1 && ["SHOP", "FACTORY"].includes(mode) && (alibaba || mode === "SHOP" || targets.length === 1)
    ? (alibaba && mode === "SHOP" ? targets.find(a => a.textContent?.trim()) : targets.find(a => a.classList.contains("shop-company-name"))) || targets[0] : null;
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
  const alibabaMessages = language === "vi" ? {
    SHOP: "Đã thu thập sản phẩm. Nhấn liên kết cửa hàng nhà cung cấp được tô xanh hoặc liên kết bên dưới, rồi chọn Lưu HTML cửa hàng trong tiện ích.",
    FACTORY: "Đã lưu cửa hàng. Nhấn Company overview / Company profile được tô xanh, rồi chọn Lưu HTML hồ sơ công ty và phân tích.",
    SHOP_CAPTURE: "Khi tên nhà cung cấp hoặc phần giới thiệu hiển thị, chọn Lưu HTML cửa hàng trong tiện ích.",
    FACTORY_CAPTURE: "Khi thông tin công ty hiển thị, chọn Lưu HTML hồ sơ công ty và phân tích trong tiện ích.",
  } : {
    SHOP: "Product captured. Click the highlighted supplier storefront link or the link below, then choose Save shop HTML in the extension.",
    FACTORY: "Shop saved. Click the highlighted Company overview / Company profile, then choose Save company HTML & analyze.",
    SHOP_CAPTURE: "When the supplier name or introduction is visible, choose Save shop HTML in the extension.",
    FACTORY_CAPTURE: "When company information is visible, choose Save company HTML & analyze in the extension.",
  };
  message.textContent = alibaba ? alibabaMessages[mode] : messages[mode];
  cue.append(message);
  if ((!target || alibaba) && mode === "SHOP" || alibaba && mode === "FACTORY") {
    const link = document.createElement("a"); link.href = mode === "FACTORY" ? expectedShop + "company_profile.html" : expectedShop;
    link.textContent = mode === "FACTORY" ? language === "vi" ? "Mở hồ sơ công ty ↗" : "Open Company overview ↗" : language === "vi" ? "Mở cửa hàng nhà cung cấp ↗" : "Open linked supplier shop ↗"; cue.append(link);
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
