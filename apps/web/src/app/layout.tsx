import type { Metadata } from "next";
import { Inter, Outfit } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/ui/Sidebar";
import { cn } from "@/lib/utils";

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
    <html lang="en" className="dark">
      <body className={cn(inter.className, outfit.variable, "bg-[#0b0f19] text-slate-100 flex")}>
        <Sidebar />
        <main className="flex-1 ml-64 min-h-screen">
          <div className="max-w-7xl mx-auto p-8 animate-fade-in">
            {children}
          </div>
        </main>
      </body>
    </html>
  );
}
