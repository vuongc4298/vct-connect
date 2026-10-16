import { shopUrl, factoryUrl } from "./linked-capture";
import { supportedOffer } from "./capture";

export type ExtensionPageState =
  | { status: "checking" }
  | { status: "unsupported" }
  | { status: "paused"; platform: "Taobao" }
  | { status: "supported"; sourceUrl: string; sourceId: string; kind: "1688" | "1688-company" | "1688-factory" | "alibaba" | "alibaba-company" | "alibaba-profile" };

export type ExtensionGate = "loading-auth" | "signed-out" | "checking-page" | "unsupported-page" | "paused-page" | "ready";

export const TAOBAO_PAUSED_NOTICE = "Taobao capture is temporarily paused because CAPTCHA prevents login. Use 1688 or Alibaba. Your saved reports are still available.";

export function classifyExtensionPage(url: string | undefined): ExtensionPageState {
  if (!url) return { status: "unsupported" };
  try {
    const hostname = new URL(url).hostname;
    if (hostname === "taobao.com" || hostname.endsWith(".taobao.com")) return { status: "paused", platform: "Taobao" };
  } catch { return { status: "unsupported" }; }
  const supported = supportedOffer(url);
  if (!supported) {
    const company = shopUrl(url), factory = factoryUrl(url);
    if (company) return { status: "supported", sourceUrl: company, sourceId: company, kind: company.endsWith(".en.alibaba.com/") ? "alibaba-company" : "1688-company" };
    if (factory) return { status: "supported", sourceUrl: factory, sourceId: factory, kind: factory.endsWith(".en.alibaba.com/company_profile.html") ? "alibaba-profile" : "1688-factory" };
    return { status: "unsupported" };
  }
  return {
    status: "supported",
    sourceUrl: supported.sourceUrl,
    sourceId: supported.offerId,
    kind: supported.kind === "alibaba" ? "alibaba" : "1688",
  };
}

export function extensionGate(input: {
  authLoaded: boolean;
  signedIn: boolean;
  page: ExtensionPageState;
}): ExtensionGate {
  if (!input.authLoaded) return "loading-auth";
  if (!input.signedIn) return "signed-out";
  if (input.page.status === "checking") return "checking-page";
  if (input.page.status === "paused") return "paused-page";
  if (input.page.status !== "supported") return "unsupported-page";
  return "ready";
}

export function canSubmitEnhancedEvidence(gate: ExtensionGate): boolean {
  return gate === "ready";
}
