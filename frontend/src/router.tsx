import { createBrowserRouter, Navigate } from "react-router-dom";
import Shell from "./components/layout/Shell";
import Upload from "./pages/Upload";
import Dashboard from "./pages/Dashboard";
import CareerMap from "./pages/CareerMap";
import Analyzer from "./pages/Analyzer";
import Interview from "./pages/Interview";
import BuiltWith from "./pages/BuiltWith";
import { hasCV, useProfileStore } from "./store/profile";

/** "/" goes to the dashboard once a CV has been uploaded, otherwise to the upload screen. */
function Home() {
  const profile = useProfileStore((s) => s.profile);
  return <Navigate to={hasCV(profile) ? "/dashboard" : "/upload"} replace />;
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Shell />,
    children: [
      { index: true, element: <Home /> },
      { path: "upload", element: <Upload /> },
      { path: "dashboard", element: <Dashboard /> },
      { path: "career", element: <CareerMap /> },
      { path: "analyzer", element: <Analyzer /> },
      { path: "interview", element: <Interview /> },
      { path: "built-with", element: <BuiltWith /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
