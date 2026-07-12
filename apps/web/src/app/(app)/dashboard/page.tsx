import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { FileText, ShieldAlert, CheckSquare, Activity, ArrowUpRight, Cpu } from 'lucide-react';

export default function DashboardPage() {
  return (
    <div className="space-y-8 pb-12">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-[32px] font-semibold tracking-tight text-[var(--text-primary)]">Dashboard</h1>
          <p className="text-[var(--text-secondary)] mt-1">Welcome to the Regulatory Intelligence Platform</p>
        </div>
        <div className="flex items-center space-x-2 text-sm text-[var(--text-secondary)] bg-white px-4 py-2 rounded-full border border-[var(--border-subtle)] shadow-sm">
          <div className="w-2 h-2 rounded-full bg-[var(--success)]"></div>
          <span className="font-medium">System Healthy</span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          title="Total Documents" 
          value="1,248" 
          trend="+12%" 
          icon={<FileText className="text-[var(--primary)] w-5 h-5" />} 
        />
        <StatCard 
          title="Extracted Obligations" 
          value="4,823" 
          trend="+5%" 
          icon={<CheckSquare className="text-[var(--secondary-brand)] w-5 h-5" />} 
        />
        <StatCard 
          title="Pending Reviews" 
          value="142" 
          trend="-3%" 
          icon={<ShieldAlert className="text-[var(--warning)] w-5 h-5" />} 
          trendColor="warning"
        />
        <StatCard 
          title="Agent Runs (24h)" 
          value="856" 
          trend="+22%" 
          icon={<Cpu className="text-[var(--accent-blue)] w-5 h-5" />} 
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Activity */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="h-full">
            <CardHeader className="flex flex-row items-center justify-between border-b border-[var(--border-subtle)] pb-4">
              <div>
                <CardTitle>Recent Extractions</CardTitle>
                <CardDescription>Latest regulatory documents processed by the AI pipeline</CardDescription>
              </div>
              <Activity className="text-[var(--text-muted)] w-5 h-5" />
            </CardHeader>
            <CardContent className="pt-6">
              <div className="space-y-3">
                {[
                  { title: 'SEBI Master Circular on Surveillance', type: 'SEBI', status: 'Completed', time: '10 mins ago', obl: 45 },
                  { title: 'RBI Cyber Security Framework', type: 'RBI', status: 'Extracting', time: '1 hour ago', obl: '-' },
                  { title: 'NSE Trading Halt Procedures', type: 'NSE', status: 'Review Pending', time: '3 hours ago', obl: 12 },
                  { title: 'BSE Listing Obligations', type: 'BSE', status: 'Completed', time: '5 hours ago', obl: 230 },
                ].map((item, i) => (
                  <div key={i} className="flex items-center justify-between p-4 rounded-xl border border-[var(--border-subtle)] hover:border-[var(--border-default)] hover:bg-[var(--surface-hover)] transition-colors">
                    <div className="flex items-start space-x-4">
                      <div className="w-10 h-10 rounded-lg bg-[var(--surface-subtle)] border border-[var(--border-subtle)] flex items-center justify-center font-medium text-sm text-[var(--text-primary)]">
                        {item.type}
                      </div>
                      <div>
                        <p className="font-medium text-[var(--text-primary)]">{item.title}</p>
                        <p className="text-xs text-[var(--text-secondary)] mt-1">{item.time}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium ${
                        item.status === 'Completed' ? 'bg-[#ECFDF5] text-[#059669]' :
                        item.status === 'Extracting' ? 'bg-[#EFF6FF] text-[#2563EB]' :
                        'bg-[#FFFBEB] text-[#D97706]'
                      }`}>
                        {item.status}
                      </span>
                      <p className="text-xs text-[var(--text-muted)] mt-2">{item.obl} obligations</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Regulatory Updates */}
        <div className="space-y-6">
          <Card className="h-full">
            <CardHeader className="border-b border-[var(--border-subtle)] pb-4">
              <CardTitle>AI Action Items</CardTitle>
              <CardDescription>Items flagged for human review</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <div className="space-y-3">
                {[
                  { text: 'Verify definition extraction in SEBI-2026-112', urgency: 'High' },
                  { text: 'Conflict detected: Deadline mismatch in RBI Master Direction', urgency: 'Critical' },
                  { text: 'Review 5 candidate obligations from NSE circular', urgency: 'Medium' },
                ].map((item, i) => (
                  <div key={i} className="group p-4 rounded-xl border border-[var(--border-subtle)] hover:border-[var(--primary)] hover:bg-[var(--surface-subtle)] transition-all cursor-pointer">
                    <div className="flex justify-between items-start mb-2">
                      <span className={`text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded ${
                        item.urgency === 'Critical' ? 'bg-[#FEF2F2] text-[#DC2626]' :
                        item.urgency === 'High' ? 'bg-[#FFF7ED] text-[#EA580C]' :
                        'bg-[#EFF6FF] text-[#2563EB]'
                      }`}>
                        {item.urgency}
                      </span>
                      <ArrowUpRight className="w-4 h-4 text-[var(--text-muted)] group-hover:text-[var(--primary)] transition-colors" />
                    </div>
                    <p className="text-sm text-[var(--text-primary)] font-medium">{item.text}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function StatCard({ title, value, trend, icon, trendColor = 'success' }: { title: string, value: string, trend: string, icon: React.ReactNode, trendColor?: 'success' | 'warning' | 'danger' }) {
  const trendBg = trendColor === 'success' ? 'bg-[#ECFDF5] text-[#059669]' : trendColor === 'warning' ? 'bg-[#FFFBEB] text-[#D97706]' : 'bg-[#FEF2F2] text-[#DC2626]';

  return (
    <Card className="relative group">
      <CardContent className="p-6 flex flex-col justify-between h-full">
        <div className="flex justify-between items-start mb-4">
          <p className="text-sm font-medium text-[var(--text-secondary)]">{title}</p>
          <div className="p-2 bg-[var(--surface-subtle)] rounded-lg">
            {icon}
          </div>
        </div>
        <div className="flex items-baseline space-x-2">
          <h2 className="text-[28px] font-semibold text-[var(--text-primary)]">{value}</h2>
          <span className={`text-xs font-medium px-2 py-0.5 rounded-md ${trendBg}`}>
            {trend}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
