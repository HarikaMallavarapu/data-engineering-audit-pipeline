import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Outlet, useLocation } from "react-router-dom";

import { checkHealth } from "../../services/api";
import { Header } from "./Header";
import { MobileNavigation, Sidebar } from "./Sidebar";

export function MainLayout() {
  const location = useLocation();
  const apiHealth = useQuery({ queryKey: ["health"], queryFn: checkHealth, refetchInterval: 15_000 });
  const apiState = apiHealth.isPending ? "checking" : apiHealth.isError ? "offline" : "online";
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);
  const previousRoute = useRef(`${location.pathname}${location.search}`);

  useEffect(() => {
    setMobileNavigationOpen(false);
    const route = `${location.pathname}${location.search}`;
    if (previousRoute.current === route) return;
    previousRoute.current = route;
    const frame = window.requestAnimationFrame(() => {
      const heading = document.querySelector<HTMLElement>("#main-content h1");
      if (heading) {
        heading.tabIndex = -1;
        heading.focus({ preventScroll: true });
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [location.pathname, location.search]);

  useEffect(() => {
    if (!mobileNavigationOpen) return;
    function handleEscape(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setMobileNavigationOpen(false);
      window.requestAnimationFrame(() => document.querySelector<HTMLButtonElement>(".mobile-menu-toggle")?.focus());
    }
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [mobileNavigationOpen]);

  function closeMobileNavigation() {
    setMobileNavigationOpen(false);
    window.requestAnimationFrame(() => document.querySelector<HTMLButtonElement>(".mobile-menu-toggle")?.focus());
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed((collapsed) => !collapsed)} />
      <div className="workspace">
        <Header
          apiState={apiState}
          mobileNavigationOpen={mobileNavigationOpen}
          onMobileNavigationToggle={() => setMobileNavigationOpen((open) => !open)}
        />
        <MobileNavigation isOpen={mobileNavigationOpen} onNavigate={closeMobileNavigation} />
        <main className="main-content" id="main-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
