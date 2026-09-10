import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "center",
          gap: 13,
          padding: "0 40px 40px",
          background: "#080C15",
        }}
      >
        <div style={{ width: 23, height: 32, borderRadius: 6, background: "rgba(61,123,255,0.55)" }} />
        <div style={{ width: 23, height: 58, borderRadius: 6, background: "rgba(61,123,255,0.85)" }} />
        <div style={{ width: 23, height: 92, borderRadius: 6, background: "#3D7BFF" }} />
      </div>
    ),
    { ...size },
  );
}
