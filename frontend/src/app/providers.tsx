import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { ThemeProvider } from "./ThemeProvider";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 5_000 },
    mutations: { retry: 0 },
  },
});

export function Providers({ children }: PropsWithChildren) {
  return <QueryClientProvider client={queryClient}><ThemeProvider>{children}</ThemeProvider></QueryClientProvider>;
}
