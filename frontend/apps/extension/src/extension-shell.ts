import { supportedOffer } from "./capture";

export type ExtensionPageState =
  | { status: "checking" }
  | { status: "unsupported" }
  | { status: "supported"; sourceUrl: string; sourceId: string; kind: "1688" | "taobao-item" | "taobao-shop" };

export type ExtensionGate = "loading-auth" | "signed-out" | "checking-page" | "unsupported-page" | "ready";

export function classifyExtensionPage(url: string | undefined): ExtensionPageState {
  if (!url) return { status: "unsupported" };
  const supported = supportedOffer(url);
  if (!supported) return { status: "unsupported" };
  return {
    status: "supported",
    sourceUrl: supported.sourceUrl,
    sourceId: supported.offerId,
    kind: supported.kind === "item" ? "taobao-item" : supported.kind === "shop" ? "taobao-shop" : "1688",
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
