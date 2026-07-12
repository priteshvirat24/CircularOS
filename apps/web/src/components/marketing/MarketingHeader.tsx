"use client";

import React from 'react';
import Link from 'next/link';
import { ShieldAlert, Play } from 'lucide-react';
import { useJudgeMode } from '../judge/JudgeModeProvider';

export function MarketingHeader() {
  const { startJudgeMode } = useJudgeMode();

  return (
    <header className="fixed top-0 left-0 right-0 h-[72px] bg-white/80 backdrop-blur-md border-b border-[var(--border-subtle)] z-50">
      <div className="max-w-[1440px] mx-auto px-6 h-full flex items-center justify-between">
        
        {/* Logo */}
        <Link href="/" className="flex items-center space-x-3 group">
          <div className="w-8 h-8 rounded-lg bg-[var(--primary)] flex items-center justify-center shadow-md group-hover:scale-105 transition-transform">
            <ShieldAlert className="w-5 h-5 text-white" />
          </div>
          <span className="text-[18px] font-bold text-[var(--text-primary)] tracking-tight">CircularOS</span>
        </Link>

        {/* Navigation */}
        <nav className="hidden md:flex items-center space-x-8">
          <a href="#problem" className="text-[14px] font-medium text-[var(--text-secondary)] hover:text-[var(--primary)] transition-colors">Problem</a>
          <a href="#how-it-works" className="text-[14px] font-medium text-[var(--text-secondary)] hover:text-[var(--primary)] transition-colors">How It Works</a>
          <a href="#architecture" className="text-[14px] font-medium text-[var(--text-secondary)] hover:text-[var(--primary)] transition-colors">Architecture</a>
          <a href="#trust" className="text-[14px] font-medium text-[var(--text-secondary)] hover:text-[var(--primary)] transition-colors">Trust</a>
          <a href="#suptech" className="text-[14px] font-medium text-[var(--text-secondary)] hover:text-[var(--primary)] transition-colors">SupTech</a>
        </nav>

        {/* Actions */}
        <div className="flex items-center space-x-4">
          <button 
            onClick={startJudgeMode}
            className="hidden sm:flex items-center space-x-2 text-[14px] font-semibold text-[var(--text-secondary)] hover:text-[var(--primary)] transition-colors"
          >
            <Play size={16} />
            <span>Run 20s Judge Mode</span>
          </button>
          <Link 
            href="/dashboard"
            className="bg-[var(--text-primary)] text-white px-5 py-2.5 rounded-lg text-[14px] font-semibold hover:bg-black transition-colors shadow-lg active:scale-95"
          >
            Launch CircularOS
          </Link>
        </div>

      </div>
    </header>
  );
}
