import { ImageResponse } from "next/og";

export const size = { width: 512, height: 512 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "center",
          gap: 37,
          padding: "0 120px 120px",
          background: "#080C15",
        }}
      >
        <div style={{ width: 66, height: 92, borderRadius: 18, background: "rgba(61,123,255,0.55)" }} />
        <div style={{ width: 66, height: 164, borderRadius: 18, background: "rgba(61,123,255,0.85)" }} />
        <div style={{ width: 66, height: 260, borderRadius: 18, background: "#3D7BFF" }} />
      </div>
    ),
    { ...size },
  );
}
