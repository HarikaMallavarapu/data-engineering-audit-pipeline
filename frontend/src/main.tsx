import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AppRouter } from "./app/router";
import { Providers } from "./app/providers";
import "./styles.css";

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("The app root element is missing.");

createRoot(rootElement).render(
  <StrictMode>
    <Providers>
      <AppRouter />
    </Providers>
  </StrictMode>,
);
