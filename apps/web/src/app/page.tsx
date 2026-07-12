import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { FileText, ShieldAlert, CheckSquare, Activity, ArrowUpRight, Cpu } from 'lucide-react';

export default function DashboardPage() {
  return (
    <div className="space-y-8 pb-12">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-4xl font-bold font-outfit tracking-tight">Dashboard</h1>
          <p className="text-slate-400 mt-2">Welcome to the Regulatory Intelligence Platform</p>
        </div>
        <div className="flex items-center space-x-2 text-sm text-slate-400 bg-slate-800/50 px-4 py-2 rounded-full border border-slate-700/50">
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></div>
          <span>System Healthy</span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          title="Total Documents" 
          value="1,248" 
          trend="+12%" 
          icon={<FileText className="text-blue-400" />} 
          gradient="from-blue-500/10 to-indigo-500/10"
        />
        <StatCard 
          title="Extracted Obligations" 
          value="4,823" 
          trend="+5%" 
          icon={<CheckSquare className="text-emerald-400" />} 
          gradient="from-emerald-500/10 to-teal-500/10"
        />
        <StatCard 
          title="Pending Reviews" 
          value="142" 
          trend="-3%" 
          icon={<ShieldAlert className="text-amber-400" />} 
          gradient="from-amber-500/10 to-orange-500/10"
        />
        <StatCard 
          title="Agent Runs (24h)" 
          value="856" 
          trend="+22%" 
          icon={<Cpu className="text-purple-400" />} 
          gradient="from-purple-500/10 to-pink-500/10"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Activity */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between border-b border-slate-800/50 pb-4">
              <div>
                <CardTitle>Recent Extractions</CardTitle>
                <CardDescription>Latest regulatory documents processed by the AI pipeline</CardDescription>
              </div>
              <Activity className="text-slate-400" />
            </CardHeader>
            <CardContent className="pt-6">
              <div className="space-y-4">
                {[
                  { title: 'SEBI Master Circular on Surveillance', type: 'SEBI', status: 'Completed', time: '10 mins ago', obl: 45 },
                  { title: 'RBI Cyber Security Framework', type: 'RBI', status: 'Extracting', time: '1 hour ago', obl: '-' },
                  { title: 'NSE Trading Halt Procedures', type: 'NSE', status: 'Review Pending', time: '3 hours ago', obl: 12 },
                  { title: 'BSE Listing Obligations', type: 'BSE', status: 'Completed', time: '5 hours ago', obl: 230 },
                ].map((item, i) => (
                  <div key={i} className="flex items-center justify-between p-4 rounded-lg bg-slate-900/40 border border-slate-800/50 hover:bg-slate-800/60 transition-colors">
                    <div className="flex items-start space-x-4">
                      <div className="w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center font-bold text-sm text-slate-300">
                        {item.type}
                      </div>
                      <div>
                        <p className="font-medium text-slate-200">{item.title}</p>
                        <p className="text-xs text-slate-400 mt-1">{item.time}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        item.status === 'Completed' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                        item.status === 'Extracting' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' :
                        'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                      }`}>
                        {item.status}
                      </span>
                      <p className="text-xs text-slate-400 mt-2">{item.obl} obligations</p>
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
            <CardHeader className="border-b border-slate-800/50 pb-4">
              <CardTitle>AI Action Items</CardTitle>
              <CardDescription>Items flagged for human review</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <div className="space-y-4">
                {[
                  { text: 'Verify definition extraction in SEBI-2026-112', urgency: 'High' },
                  { text: 'Conflict detected: Deadline mismatch in RBI Master Direction', urgency: 'Critical' },
                  { text: 'Review 5 candidate obligations from NSE circular', urgency: 'Medium' },
                ].map((item, i) => (
                  <div key={i} className="group p-4 rounded-lg bg-slate-900/40 border border-slate-800/50 hover:border-slate-600 transition-all cursor-pointer">
                    <div className="flex justify-between items-start mb-2">
                      <span className={`text-[10px] uppercase tracking-wider font-bold px-2 py-1 rounded ${
                        item.urgency === 'Critical' ? 'bg-red-500/20 text-red-400' :
                        item.urgency === 'High' ? 'bg-orange-500/20 text-orange-400' :
                        'bg-blue-500/20 text-blue-400'
                      }`}>
                        {item.urgency}
                      </span>
                      <ArrowUpRight className="w-4 h-4 text-slate-500 group-hover:text-slate-300 transition-colors" />
                    </div>
                    <p className="text-sm text-slate-300">{item.text}</p>
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

function StatCard({ title, value, trend, icon, gradient }: { title: string, value: string, trend: string, icon: React.ReactNode, gradient: string }) {
  return (
    <Card className="relative overflow-hidden group">
      <div className={`absolute inset-0 bg-gradient-to-br ${gradient} opacity-50 group-hover:opacity-100 transition-opacity duration-500`}></div>
      <CardContent className="p-6 relative z-10 flex flex-col justify-between h-full">
        <div className="flex justify-between items-start mb-4">
          <p className="text-sm font-medium text-slate-400">{title}</p>
          <div className="p-2 bg-slate-900/50 rounded-lg shadow-inner">
            {icon}
          </div>
        </div>
        <div className="flex items-baseline space-x-2">
          <h2 className="text-3xl font-bold font-outfit">{value}</h2>
          <span className="text-sm font-medium text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full">
            {trend}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
