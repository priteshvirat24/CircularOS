"use client";

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  LayoutDashboard, 
  FileText, 
  CheckSquare, 
  Cpu,
  ShieldAlert,
  Library,
  Scale,
  BellRing
} from 'lucide-react';
import { cn } from '@/lib/utils';

export function Sidebar() {
  return (
    <aside className="w-[236px] bg-white border-r border-[var(--border-subtle)] h-screen fixed left-0 top-0 flex flex-col z-50">
      <div className="h-[64px] px-6 border-b border-[var(--border-subtle)] flex items-center space-x-3 shrink-0">
        <div className="w-7 h-7 rounded-lg bg-[var(--primary)] flex items-center justify-center shadow-sm">
          <ShieldAlert className="w-4 h-4 text-white" />
        </div>
        <div>
          <h1 className="text-[15px] font-semibold text-[var(--text-primary)] tracking-tight">
            CircularOS
          </h1>
        </div>
      </div>
      
      <div className="flex-1 overflow-y-auto py-6 space-y-6">
        <NavGroup title="OPERATE">
          <SidebarLink href="/dashboard" icon={<LayoutDashboard size={16} />} label="Dashboard" />
          <SidebarLink href="/documents" icon={<FileText size={16} />} label="Documents" />
          <SidebarLink href="/obligations" icon={<Scale size={16} />} label="Obligation Registry" />
          <SidebarLink href="/changes" icon={<BellRing size={16} />} label="Regulatory Changes" />
          <SidebarLink href="/workbench" icon={<CheckSquare size={16} />} label="Review Workbench" />
        </NavGroup>

        <NavGroup title="IMPLEMENT">
          <SidebarLink href="/controls" icon={<Library size={16} />} label="Control Library" />
        </NavGroup>

        <NavGroup title="INTELLIGENCE">
          <SidebarLink href="/agents" icon={<Cpu size={16} />} label="Agent Runs" />
        </NavGroup>
      </div>
      
      <div className="p-4 border-t border-[var(--border-subtle)]">
        <div className="flex items-center space-x-3 p-2 rounded-lg bg-[var(--surface-subtle)] border border-[var(--border-subtle)] transition-all hover:border-[var(--border-default)] hover:bg-[var(--surface-hover)] cursor-pointer">
          <div className="w-7 h-7 rounded-full bg-[var(--primary)] flex items-center justify-center text-white font-medium text-[11px] shadow-sm shrink-0">
            JD
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[13px] font-medium text-[var(--text-primary)] truncate">John Doe</p>
            <p className="text-[11px] text-[var(--text-secondary)] truncate">Compliance Officer</p>
          </div>
        </div>
      </div>
    </aside>
  );
}

function NavGroup({ title, children }: { title: string, children: React.ReactNode }) {
  return (
    <div className="px-4">
      <h3 className="text-[11px] font-bold text-[var(--text-muted)] tracking-wider uppercase mb-2 px-3">
        {title}
      </h3>
      <nav className="space-y-0.5">
        {children}
      </nav>
    </div>
  );
}

function SidebarLink({ href, icon, label }: { href: string; icon: React.ReactNode; label: string }) {
  const pathname = usePathname();
  const isActive = pathname === href || (href !== "/" && pathname.startsWith(href));
  
  return (
    <Link 
      href={href}
      className={cn(
        "flex items-center space-x-3 px-3 py-2 rounded-md transition-all duration-200 group relative",
        isActive 
          ? "text-[var(--primary)] bg-[var(--surface-selected)] font-medium" 
          : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)]"
      )}
    >
      <div className={cn(
        "transition-transform duration-200",
        isActive ? "text-[var(--primary)]" : "opacity-80 group-hover:opacity-100 group-hover:text-[var(--primary)]"
      )}>
        {icon}
      </div>
      <span className="text-[13px] z-10 relative">{label}</span>
      
      {/* Animated active indicator */}
      {isActive && (
        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4 bg-[var(--primary)] rounded-r-full" />
      )}
    </Link>
  );
}
