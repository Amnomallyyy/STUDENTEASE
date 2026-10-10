// Temporary entry point until M2's scaffold (App.tsx, router.tsx) lands.
//   #/            mock interview (M3 + M4)
//   #/vision      M4 vision playground with the debug panel, for threshold tuning
import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import VisionPlayground from "./dev/VisionPlayground";
import Interview from "./pages/Interview";

function Root() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const onHash = () => setHash(window.location.hash);
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  return hash.startsWith("#/vision") ? <VisionPlayground /> : <Interview />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
