import { shopUrl, factoryUrl } from "./linked-capture";
import { supportedOffer } from "./capture";

export type ExtensionPageState =
  | { status: "checking" }
  | { status: "unsupported" }
  | { status: "supported"; sourceUrl: string; sourceId: string; kind: "1688" | "taobao-item" | "taobao-shop" | "1688-company" | "1688-factory" | "alibaba" | "alibaba-company" | "alibaba-profile" };

export type ExtensionGate = "loading-auth" | "signed-out" | "checking-page" | "unsupported-page" | "ready";

export function classifyExtensionPage(url: string | undefined): ExtensionPageState {
  if (!url) return { status: "unsupported" };
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
    kind: supported.kind === "alibaba" ? "alibaba" : supported.kind === "item" ? "taobao-item" : supported.kind === "shop" ? "taobao-shop" : "1688",
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
  if (input.page.status !== "supported") return "unsupported-page";
  return "ready";
}

export function canSubmitEnhancedEvidence(gate: ExtensionGate): boolean {
  return gate === "ready";
}
