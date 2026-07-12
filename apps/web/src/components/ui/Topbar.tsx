"use client";

import React from 'react';
import { usePathname } from 'next/navigation';
import { Play, Search, Bell, ChevronRight, Activity } from 'lucide-react';
import { useJudgeMode } from '../judge/JudgeModeProvider';

export function Topbar() {
  const pathname = usePathname();
  const { startJudgeMode } = useJudgeMode();

  // Basic breadcrumb generation
  const pathParts = pathname.split('/').filter(Boolean);
  const breadcrumb = pathParts.length > 0 
    ? pathParts[0].charAt(0).toUpperCase() + pathParts[0].slice(1)
    : 'Dashboard';

  return (
    <header className="h-[64px] bg-white border-b border-[var(--border-subtle)] fixed top-0 right-0 left-[236px] z-40 flex items-center justify-between px-6">
      
      {/* Left: Breadcrumbs & Workflow Indicator */}
      <div className="flex items-center space-x-6">
        <div className="flex items-center space-x-2 text-[13px] font-medium text-[var(--text-secondary)]">
          <span className="text-[var(--text-muted)]">Operate</span>
          <ChevronRight size={14} className="text-[var(--border-strong)]" />
          <span className="text-[var(--text-primary)]">{breadcrumb}</span>
        </div>

        <div className="h-4 w-px bg-[var(--border-default)]"></div>

        <div className="flex items-center space-x-2 px-2.5 py-1 bg-[var(--surface-subtle)] border border-[var(--border-subtle)] rounded-full text-[12px] font-medium text-[var(--text-secondary)] shadow-sm">
          <Activity size={12} className="text-[var(--primary)]" />
          <span>Active Workflow: Q3 Amendments</span>
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center space-x-4">
        
        {/* Global Search Trigger */}
        <button className="flex items-center space-x-2 px-3 py-1.5 border border-[var(--border-default)] rounded-md text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:border-[var(--border-strong)] transition-all group bg-[var(--background-secondary)] w-64 shadow-inner">
          <Search size={14} className="group-hover:text-[var(--primary)] transition-colors" />
          <span className="text-[13px]">Search CircularOS...</span>
          <div className="ml-auto flex space-x-1">
            <span className="text-[10px] bg-white border border-[var(--border-subtle)] px-1 rounded shadow-sm font-mono">⌘</span>
            <span className="text-[10px] bg-white border border-[var(--border-subtle)] px-1 rounded shadow-sm font-mono">K</span>
          </div>
        </button>

        <div className="h-6 w-px bg-[var(--border-default)]"></div>

        {/* Judge Mode Button */}
        <button 
          onClick={startJudgeMode}
          className="flex items-center space-x-2 bg-gradient-to-r from-[var(--primary)] to-[var(--secondary-brand)] text-white px-4 py-1.5 rounded-md hover:shadow-md hover:-translate-y-px transition-all font-medium text-[13px]"
        >
          <Play size={14} className="fill-white" />
          <span>Run 20s Judge Mode</span>
        </button>

        {/* Notifications */}
        <button className="p-1.5 text-[var(--text-muted)] hover:text-[var(--primary)] hover:bg-[var(--surface-hover)] rounded-md transition-colors relative">
          <Bell size={18} />
          <span className="absolute top-1 right-1 w-2 h-2 bg-[var(--danger)] rounded-full border border-white"></span>
        </button>

        {/* Organization Switcher / Profile */}
        <button className="flex items-center space-x-2 p-1 pl-2 pr-3 border border-[var(--border-default)] rounded-md hover:bg-[var(--surface-hover)] transition-colors">
          <div className="w-6 h-6 bg-[var(--primary-subtle)] text-[var(--primary)] rounded flex items-center justify-center font-bold text-[10px] border border-[var(--primary-light)]">
            AC
          </div>
          <span className="text-[13px] font-medium text-[var(--text-primary)]">Acme Corp</span>
        </button>
      </div>

    </header>
  );
}
