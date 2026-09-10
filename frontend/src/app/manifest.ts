import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ThesisLedger",
    short_name: "ThesisLedger",
    description:
      "Turn an investment thesis into testable claims checked against SEC filings.",
    start_url: "/",
    display: "standalone",
    background_color: "#080c15",
    theme_color: "#080c15",
    orientation: "portrait",
    icons: [
      {
        src: "/icon.svg",
        type: "image/svg+xml",
        sizes: "any",
        purpose: "any",
      },
      {
        src: "/icon",
        type: "image/png",
        sizes: "512x512",
        purpose: "maskable",
      },
    ],
  };
}
