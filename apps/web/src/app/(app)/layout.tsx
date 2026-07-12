import { Sidebar } from "@/components/ui/Sidebar";
import { Topbar } from "@/components/ui/Topbar";

export default function AppLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="flex bg-[var(--background-secondary)] min-h-screen w-full">
      <Sidebar />
      <div className="flex-1 ml-[236px] flex flex-col min-h-screen">
        <Topbar />
        <main className="flex-1 bg-[var(--background-secondary)] pt-[64px]">
          <div className="max-w-[1440px] mx-auto px-6 py-8 lg:px-10 lg:py-12 animate-fade-in">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
