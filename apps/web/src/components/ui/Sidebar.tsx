"use client";

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  LayoutDashboard, 
  FileText, 
  CheckSquare, 
  Cpu, 
  Settings,
  ShieldAlert,
  Library,
  Scale,
  BellRing
} from 'lucide-react';
import { cn } from '@/lib/utils';

export function Sidebar() {
  return (
    <aside className="w-64 glass-panel h-screen fixed left-0 top-0 flex flex-col z-50">
      <div className="p-6 border-b border-slate-800/50 flex items-center space-x-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
          <ShieldAlert className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent tracking-tight">
            CircularOS
          </h1>
        </div>
      </div>
      
      <nav className="flex-1 py-6 px-4 space-y-1.5 overflow-y-auto">
        <SidebarLink href="/" icon={<LayoutDashboard size={20} />} label="Dashboard" />
        <SidebarLink href="/documents" icon={<FileText size={20} />} label="Documents" />
        <SidebarLink href="/workbench" icon={<CheckSquare size={20} />} label="Review Workbench" />
        <SidebarLink href="/obligations" icon={<Scale size={20} />} label="Obligation Registry" />
        <SidebarLink href="/controls" icon={<Library size={20} />} label="Control Library" />
        <SidebarLink href="/changes" icon={<BellRing size={20} />} label="Regulatory Changes" />
        <SidebarLink href="/agents" icon={<Cpu size={20} />} label="Agent Traces" />
        <SidebarLink href="/settings" icon={<Settings size={20} />} label="Settings" />
      </nav>
      
      <div className="p-4 border-t border-slate-800/50">
        <div className="flex items-center space-x-3 p-3 rounded-lg bg-slate-800/30 border border-slate-700/50 transition-all hover:bg-slate-800/50 cursor-pointer">
          <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-blue-500 to-purple-500 flex items-center justify-center text-white font-bold text-sm shadow-lg shadow-blue-500/20">
            JD
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-slate-200 truncate">John Doe</p>
            <p className="text-xs text-slate-400 truncate">Compliance Officer</p>
          </div>
        </div>
      </div>
    </aside>
  );
}

function SidebarLink({ href, icon, label }: { href: string; icon: React.ReactNode; label: string }) {
  const pathname = usePathname();
  const isActive = pathname === href || (href !== "/" && pathname.startsWith(href));
  
  return (
    <Link 
      href={href}
      className={cn(
        "flex items-center space-x-3 px-3 py-2.5 rounded-lg transition-all duration-200 group relative overflow-hidden",
        isActive 
          ? "text-blue-400 bg-blue-500/10 font-medium border border-blue-500/20" 
          : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border border-transparent"
      )}
    >
      {isActive && (
        <span className="absolute left-0 top-0 bottom-0 w-1 bg-blue-500 rounded-r-md"></span>
      )}
      <div className={cn(
        "transition-transform duration-300",
        isActive ? "scale-110" : "opacity-70 group-hover:opacity-100 group-hover:scale-110"
      )}>
        {icon}
      </div>
      <span className="text-sm z-10 relative">{label}</span>
      
      {/* Hover glow effect */}
      <div className="absolute inset-0 bg-gradient-to-r from-blue-500/0 via-blue-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity -z-10 translate-x-[-100%] group-hover:translate-x-0 duration-500"></div>
    </Link>
  );
}
