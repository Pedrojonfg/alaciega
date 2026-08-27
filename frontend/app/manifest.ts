import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "alaciega",
    short_name: "alaciega",
    description: "Ajedrez sin ver el tablero contra Maia",
    start_url: "/",
    display: "standalone",
    background_color: "#f3ead8",
    theme_color: "#1e5c3a",
    icons: [{ src: "/icon", sizes: "512x512", type: "image/png", purpose: "any" }],
  };
}
