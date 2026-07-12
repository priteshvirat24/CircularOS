"use client";

import React, { useRef } from 'react';
import { useScroll, useTransform, motion } from 'framer-motion';

export function LandingProblem() {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start end", "end start"]
  });

  const opacity = useTransform(scrollYProgress, [0.1, 0.3, 0.7, 0.9], [0, 1, 1, 0]);
  const y = useTransform(scrollYProgress, [0.1, 0.3, 0.7, 0.9], [50, 0, 0, -50]);

  const stages = [
    "NEW CIRCULAR",
    "200+ PAGES",
    "MANUAL INTERPRETATION",
    "SPREADSHEETS",
    "EMAIL COORDINATION",
    "CONTROL UPDATES",
    "EVIDENCE COLLECTION",
    "MANUAL REPORTING"
  ];

  return (
    <section id="problem" className="bg-[var(--background)] py-32 border-t border-[var(--border-subtle)]" ref={containerRef}>
      <motion.div 
        style={{ opacity, y }}
        className="max-w-4xl mx-auto px-6 text-center"
      >
        <h2 className="text-[32px] md:text-[40px] font-semibold tracking-tight text-[var(--text-primary)] mb-2">
          THE CIRCULAR IS PUBLISHED IN MINUTES.
        </h2>
        <h3 className="text-[32px] md:text-[40px] font-semibold tracking-tight text-[var(--text-secondary)] mb-20">
          OPERATIONALIZING IT TAKES DAYS.
        </h3>

        <div className="flex flex-col items-center space-y-6 mb-24 relative before:absolute before:inset-0 before:ml-auto before:mr-auto before:w-px before:bg-gradient-to-b before:from-[var(--border-subtle)] before:via-[var(--primary)] before:to-[var(--border-subtle)]">
          {stages.map((stage, i) => (
            <motion.div 
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ delay: i * 0.1, duration: 0.5 }}
              className="bg-white border border-[var(--border-default)] px-6 py-3 rounded-lg shadow-sm z-10 font-mono text-[13px] text-[var(--text-primary)] tracking-widest font-semibold"
            >
              {stage}
            </motion.div>
          ))}
        </div>

        <div className="space-y-4 text-left max-w-lg mx-auto">
          <p className="text-[18px] text-[var(--text-muted)] border-l-2 border-[var(--border-subtle)] pl-4">What changed?</p>
          <p className="text-[18px] text-[var(--text-muted)] border-l-2 border-[var(--border-subtle)] pl-4">Who is affected?</p>
          <p className="text-[18px] text-[var(--text-muted)] border-l-2 border-[var(--border-subtle)] pl-4">Which controls must change?</p>
          <p className="text-[18px] text-[var(--text-muted)] border-l-2 border-[var(--border-subtle)] pl-4">What evidence is required?</p>
          <p className="text-[18px] text-[var(--text-muted)] border-l-2 border-[var(--border-subtle)] pl-4">Has implementation actually happened?</p>
        </div>

        <div className="mt-24">
          <p className="text-[16px] tracking-widest text-[var(--text-secondary)] uppercase font-semibold mb-6">Today, these questions are answered</p>
          <div className="text-[64px] font-bold tracking-tighter flex items-center justify-center space-x-4">
            <span className="text-[var(--text-muted)] line-through">MANUALLY</span>
            <span className="text-[var(--primary)]">CIRCULAROS.</span>
          </div>
        </div>
      </motion.div>
    </section>
  );
}
