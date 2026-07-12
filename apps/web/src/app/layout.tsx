import type { Metadata } from "next";
import { Inter, Outfit } from "next/font/google";
import "./globals.css";
import { cn } from "@/lib/utils";
import { JudgeModeProvider } from "@/components/judge/JudgeModeProvider";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const outfit = Outfit({ subsets: ["latin"], variable: "--font-outfit" });

export const metadata: Metadata = {
  title: "CircularOS | Agentic Regulatory Intelligence",
  description: "Agentic Regulatory Intelligence, Compliance Operations, and Supervisory Technology Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="scroll-smooth">
      <body className={cn(inter.className, outfit.variable, "bg-[var(--background)] text-[var(--text-primary)] antialiased min-h-screen")}>
        <JudgeModeProvider>
          {children}
        </JudgeModeProvider>
      </body>
    </html>
  );
}
