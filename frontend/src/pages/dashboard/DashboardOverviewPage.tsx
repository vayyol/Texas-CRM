import { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, ArrowUpRight, CalendarDays, CheckCircle2, Clock3, Handshake, MessageCircle, RefreshCw, ShoppingCart, Star, Target, Users } from 'lucide-react';
import { api } from '@/lib/api';
import { Card, CardBody } from '@/components/ui/Card';

type State = { id: number; tipo: string; status: string; descricao: string | null; valor_total: number | null; created_at: string };
type Client = { id: number; nome: string; telefone: string | null; created_at: string; estados: State[] };
type Payment = { id_venda: number; client_id: number; nome: string; valor_total: number | string | null; situacao: string; data_vencimento: string | null };
type ManualFollowup = { key: string; client_id: number; nome: string; telefone: string | null; titulo: string; descricao: string; dias: number };
type Data = { estados_abertos: Array<{ id: number; client_id: number; nome: string; telefone: string | null; tipo: string; descricao: string | null; created_at: string; dias_aberto: number }>; pagamentos: Payment[] };
const money = (v: number) => v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const apiError = (error: unknown) => {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return typeof detail === 'string' ? detail : 'Não foi possível carregar os dados do dashboard.';
};
const date = (v: string) => new Date(v).toLocaleDateString('pt-BR');
const stageNames: Record<string, string> = { CONTATO: 'Contato', INTERESSADO: 'Interessado', PROPOSTA: 'Proposta', VENDA_REALIZADA: 'Venda realizada', VENDA_NAO_REALIZADA: 'Venda não realizada', DESINTERESSADO: 'Desinteressado' };
const stageColors: Record<string, string> = { CONTATO: 'bg-blue-500', INTERESSADO: 'bg-emerald-500', PROPOSTA: 'bg-amber-500', VENDA_REALIZADA: 'bg-green-700', VENDA_NAO_REALIZADA: 'bg-rose-500', DESINTERESSADO: 'bg-violet-500' };

export default function DashboardOverviewPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [manual, setManual] = useState<Data>({ estados_abertos: [], pagamentos: [] });
  const [followups, setFollowups] = useState<ManualFollowup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [clientRes, manualRes, followupRes] = await Promise.all([
        api.get<Client[]>('/api/v1/integracao/listar-clientes-estados'),
        api.get<Data>('/api/v1/integracao/dashboard-acompanhamento'),
        api.get<{ followups: ManualFollowup[] }>('/api/v1/integracao/followups'),
      ]);
      setClients(Array.isArray(clientRes.data) ? clientRes.data : []);
      setManual({ estados_abertos: manualRes.data.estados_abertos || [], pagamentos: manualRes.data.pagamentos || [] });
      setFollowups(followupRes.data.followups || []);
    } catch (e: unknown) {
      setError(apiError(e));
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const allStates = useMemo(() => clients.flatMap(c => (c.estados || []).map(s => ({ ...s, clientName: c.nome, clientPhone: c.telefone }))), [clients]);
  const sales = allStates.filter(s => s.tipo === 'VENDA_REALIZADA');
  const proposals = allStates.filter(s => s.tipo === 'PROPOSTA' && s.status === 'ABERTO');
  const salesValue = sales.reduce((sum, s) => sum + Number(s.valor_total || 0), 0);
  const average = sales.length ? salesValue / sales.length : 0;
  const now = new Date();
  const currentMonth = now.getMonth();
  const currentYear = now.getFullYear();
  const firstDay = new Date(currentYear, currentMonth, 1);
  const newClients = clients.filter(c => new Date(c.created_at) >= firstDay).length;
  const monthly = useMemo(() => Array.from({ length: 6 }, (_, i) => {
    const d = new Date(currentYear, currentMonth - 5 + i, 1);
    const key = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
    const amount = sales.filter(s => s.created_at?.slice(0, 7) === key).reduce((sum, s) => sum + Number(s.valor_total || 0), 0);
    return { label: d.toLocaleDateString('pt-BR', { month: 'short' }).replace('.', ''), amount };
  }), [sales, currentMonth, currentYear]);
  const maxSales = Math.max(1, ...monthly.map(m => m.amount));
  const stages = useMemo(() => Object.keys(stageNames).map(key => ({ key, name: stageNames[key], count: allStates.filter(s => s.tipo === key).length })), [allStates]);
  const attention = useMemo(() => {
    const overdue = manual.estados_abertos.filter(s => s.dias_aberto >= 2).map(s => ({ id: 'state-' + s.id, name: s.nome, phone: s.telefone, title: stageNames[s.tipo] + ' parado', detail: s.descricao || 'Etapa em aberto', days: s.dias_aberto }));
    const reminders = followups.map(f => ({ id: f.key, name: f.nome, phone: f.telefone, title: f.titulo, detail: f.descricao, days: f.dias }));
    return [...reminders, ...overdue].slice(0, 6);
  }, [manual.estados_abertos, followups]);
  const activities = useMemo(() => [...allStates].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).slice(0, 6), [allStates]);
  const recurrent = useMemo(() => {
    const counts = new Map<number, number>();
    sales.forEach(s => { const client = clients.find(c => c.estados.some(e => e.id === s.id)); if (client) counts.set(client.id, (counts.get(client.id) || 0) + 1); });
    return [...counts.values()].filter(n => n > 1).length;
  }, [sales, clients]);
  const statCards = [
    { label: 'Clientes cadastrados', value: clients.length, hint: `+${newClients} neste mês`, icon: Users, color: 'text-blue-600 bg-blue-50 dark:bg-blue-500/10' },
    { label: 'Novos clientes', value: newClients, hint: 'Neste mês', icon: UserPlusIcon, color: 'text-emerald-600 bg-emerald-50 dark:bg-emerald-500/10' },
    { label: 'Vendas realizadas', value: sales.length, hint: money(salesValue) + ' em vendas', icon: ShoppingCart, color: 'text-green-700 bg-green-50 dark:bg-green-500/10' },
    { label: 'Em negociação', value: proposals.length, hint: money(proposals.reduce((sum, s) => sum + Number(s.valor_total || 0), 0)) + ' em aberto', icon: Handshake, color: 'text-orange-600 bg-orange-50 dark:bg-orange-500/10' },
    { label: 'Ticket médio', value: money(average), hint: `${recurrent} clientes recorrentes`, icon: Star, color: 'text-violet-600 bg-violet-50 dark:bg-violet-500/10' },
  ];

  return <div className="space-y-6 pb-10">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-bold text-surface-900 dark:text-white">Visão geral</h1><p className="text-sm text-surface-500 dark:text-white/50">Acompanhe seus clientes e saiba o que precisa de atenção.</p></div><button onClick={load} disabled={loading} className="rounded-xl border border-surface-200 p-2.5 text-surface-600 hover:bg-surface-100 dark:border-white/10 dark:text-white/70"><RefreshCw className={`h-5 w-5 ${loading ? 'animate-spin' : ''}`} /></button></div>
    {error && <div className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</div>}
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">{statCards.map(s => <Card key={s.label}><CardBody className="flex items-center gap-3 p-4"><div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${s.color}`}><s.icon className="h-5 w-5" /></div><div className="min-w-0"><p className="text-xs text-surface-500">{s.label}</p><p className="truncate text-xl font-bold text-surface-900 dark:text-white">{loading ? '—' : s.value}</p><p className="truncate text-xs text-emerald-600">{s.hint}</p></div></CardBody></Card>)}</div>

    <div className="grid gap-4 xl:grid-cols-[1.25fr_1fr]">
      <Card><CardBody className="p-5"><div className="mb-5 flex items-center justify-between"><div><h2 className="font-semibold text-surface-900 dark:text-white">Evolução das vendas</h2><p className="text-xs text-surface-500">Valor das vendas realizadas nos últimos 6 meses</p></div><span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">Histórico real</span></div>
        <div className="flex h-56 items-end gap-3 border-b border-surface-200 px-2 dark:border-white/10">{monthly.map(m => <div key={m.label} className="flex h-full flex-1 flex-col items-center justify-end gap-2"><span className="text-[10px] text-surface-500">{m.amount ? money(m.amount).replace(',00','') : '—'}</span><div className="flex w-full flex-1 items-end"><div className="w-full rounded-t-md bg-brand-600 transition-all" style={{ height: `${Math.max(2, (m.amount / maxSales) * 100)}%` }} /></div><span className="pb-2 text-xs font-medium text-surface-500">{m.label}</span></div>)}</div>
      </CardBody></Card>
      <Card><CardBody className="p-5"><div className="mb-5"><h2 className="font-semibold text-surface-900 dark:text-white">Clientes por etapa</h2><p className="text-xs text-surface-500">Distribuição dos registros de relacionamento</p></div><div className="space-y-3">{stages.map(s => { const max = Math.max(1, ...stages.map(x => x.count)); return <div key={s.key}><div className="mb-1 flex justify-between gap-2 text-xs"><span className="text-surface-600 dark:text-white/70">{s.name}</span><b className="text-surface-900 dark:text-white">{s.count}</b></div><div className="h-2.5 overflow-hidden rounded-full bg-surface-100 dark:bg-white/10"><div className={`h-full rounded-full ${stageColors[s.key]}`} style={{ width: `${s.count / max * 100}%` }} /></div></div>; })}</div><p className="mt-4 text-xs text-surface-500">{clients.length} clientes cadastrados · um cliente pode ter várias etapas</p></CardBody></Card>
    </div>

    <div className="grid gap-4 xl:grid-cols-[1.25fr_1fr]">
      <Card><CardBody className="p-5"><div className="mb-4 flex items-center gap-2"><AlertTriangle className="h-5 w-5 text-rose-500" /><div><h2 className="font-semibold text-surface-900 dark:text-white">Clientes que precisam de atenção</h2><p className="text-xs text-surface-500">Situações que merecem um retorno</p></div></div>
        {attention.length ? <div className="divide-y divide-surface-100 dark:divide-white/10">{attention.map(a => <div key={a.id} className="flex flex-wrap items-center justify-between gap-3 py-3"><div className="min-w-0"><p className="font-medium text-surface-900 dark:text-white">{a.name}</p><p className="text-xs text-surface-500">{a.title} · {a.detail}</p></div><span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700">{a.days} dias</span></div>)}</div> : <div className="py-8 text-center"><CheckCircle2 className="mx-auto h-8 w-8 text-emerald-500" /><p className="mt-2 text-sm text-surface-500">Nenhum cliente sinalizado no momento.</p></div>}
      </CardBody></Card>
      <Card><CardBody className="p-5"><div className="mb-5 flex items-center gap-2"><Target className="h-5 w-5 text-rose-500" /><h2 className="font-semibold text-surface-900 dark:text-white">Oportunidades comerciais</h2></div><div className="grid grid-cols-2 gap-4"><div><p className="text-xs text-surface-500">Propostas abertas</p><p className="mt-1 text-2xl font-bold text-surface-900 dark:text-white">{proposals.length}</p></div><div><p className="text-xs text-surface-500">Valor em negociação</p><p className="mt-1 text-xl font-bold text-surface-900 dark:text-white">{money(proposals.reduce((sum, s) => sum + Number(s.valor_total || 0), 0))}</p></div><div><p className="text-xs text-surface-500">Vendas no mês</p><p className="mt-1 text-2xl font-bold text-surface-900 dark:text-white">{sales.filter(s => s.created_at?.slice(0,7) === now.toISOString().slice(0,7)).length}</p></div><div><p className="text-xs text-surface-500">Clientes recorrentes</p><p className="mt-1 text-2xl font-bold text-surface-900 dark:text-white">{recurrent}</p></div></div><div className="mt-5 rounded-xl bg-brand-50 p-3 text-xs text-brand-800 dark:bg-brand-500/10 dark:text-brand-200">As oportunidades consideram propostas abertas e vendas registradas. A taxa de conversão não é estimada sem vínculo confiável entre proposta e venda.</div></CardBody></Card>
    </div>

    <div className="grid gap-4 xl:grid-cols-2">
      <Card><CardBody className="p-5"><div className="mb-3 flex items-center gap-2"><Activity className="h-5 w-5 text-brand-600" /><h2 className="font-semibold text-surface-900 dark:text-white">Atividades recentes</h2></div>{activities.length ? <div className="space-y-3">{activities.map(a => <div key={a.id} className="flex items-start gap-3"><div className="mt-0.5 rounded-full bg-brand-50 p-2 text-brand-600 dark:bg-brand-500/10"><ArrowUpRight className="h-4 w-4" /></div><div className="min-w-0 flex-1"><p className="text-sm font-medium text-surface-900 dark:text-white">{stageNames[a.tipo]} — {a.clientName}</p><p className="text-xs text-surface-500">{a.descricao || 'Movimentação registrada'} · {date(a.created_at)}</p></div></div>)}</div> : <p className="py-8 text-center text-sm text-surface-500">Nenhuma movimentação registrada.</p>}</CardBody></Card>
      <Card><CardBody className="p-5"><div className="mb-3 flex items-center gap-2"><CalendarDays className="h-5 w-5 text-brand-600" /><h2 className="font-semibold text-surface-900 dark:text-white">Resumo do relacionamento</h2></div><div className="grid grid-cols-3 gap-2 text-center"><div className="rounded-xl bg-blue-50 p-3 dark:bg-blue-500/10"><Clock3 className="mx-auto h-5 w-5 text-blue-600" /><p className="mt-2 text-2xl font-bold text-surface-900 dark:text-white">{followups.length}</p><p className="text-xs text-surface-500">Follow-ups</p></div><div className="rounded-xl bg-amber-50 p-3 dark:bg-amber-500/10"><Handshake className="mx-auto h-5 w-5 text-amber-600" /><p className="mt-2 text-2xl font-bold text-surface-900 dark:text-white">{proposals.length}</p><p className="text-xs text-surface-500">Propostas abertas</p></div><div className="rounded-xl bg-emerald-50 p-3 dark:bg-emerald-500/10"><Users className="mx-auto h-5 w-5 text-emerald-600" /><p className="mt-2 text-2xl font-bold text-surface-900 dark:text-white">{recurrent}</p><p className="text-xs text-surface-500">Recorrentes</p></div></div><div className="mt-4 flex items-center justify-between text-sm"><span className="text-surface-500">Parcelas em atraso</span><b className="text-rose-600">{manual.pagamentos.filter(p => p.situacao === 'ATRASADO').length}</b></div><a href="/followups" className="mt-4 flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700"><MessageCircle className="h-4 w-4" />Abrir cobranças e follow-ups</a></CardBody></Card>
    </div>
  </div>;
}

function UserPlusIcon(props: React.ComponentProps<typeof Users>) {
  return <Users {...props} />;
}
