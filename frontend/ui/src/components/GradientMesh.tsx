/** Animated gradient-mesh background: blurred low-opacity blobs + engineering grid + vignette. */
export function GradientMesh() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-base">
      {/* deep purple / indigo / cyan blobs */}
      <div
        className="absolute -left-[12%] -top-[18%] h-[58vw] w-[58vw] rounded-full opacity-[0.40] blur-[120px] animate-meshA"
        style={{
          background:
            "radial-gradient(circle at 50% 50%, #5b2bd6 0%, rgba(91,43,214,0) 65%)",
        }}
      />
      <div
        className="absolute -right-[14%] top-[8%] h-[52vw] w-[52vw] rounded-full opacity-[0.30] blur-[130px] animate-meshB"
        style={{
          background:
            "radial-gradient(circle at 50% 50%, #007a99 0%, rgba(0,122,153,0) 65%)",
        }}
      />
      <div
        className="absolute bottom-[-22%] left-[24%] h-[60vw] w-[60vw] rounded-full opacity-[0.26] blur-[140px] animate-meshC"
        style={{
          background:
            "radial-gradient(circle at 50% 50%, #1b3a8f 0%, rgba(27,58,143,0) 65%)",
        }}
      />
      <div
        className="absolute right-[6%] bottom-[-10%] h-[34vw] w-[34vw] rounded-full opacity-[0.18] blur-[110px] animate-meshA"
        style={{
          background:
            "radial-gradient(circle at 50% 50%, #00d9ff 0%, rgba(0,217,255,0) 60%)",
        }}
      />

      {/* fine engineering grid */}
      <div className="absolute inset-0 grid-overlay opacity-70" />

      {/* top + bottom vignette to seat the chrome */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(120% 80% at 50% 0%, rgba(10,14,39,0) 40%, rgba(6,9,24,0.9) 100%)",
        }}
      />
    </div>
  );
}
