import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, BellRing, CheckCircle2, Loader2, MessageCircle, RefreshCw, Save, Send, Settings2, Smartphone, XCircle } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Toggle } from '@/components/ui/Toggle';

type Setting = { type: string; title: string; description: string; auto_enabled: boolean; message_template: string };
type RecordItem = { id: string; type: string; client_id: number; customer_name: string; phone: string | null; title: string; description: string; message: string; status: 'pending' | 'sent' | 'dismissed' | 'failed'; due_at: string; sent_at: string | null; error: string | null };
type PageData = { whatsapp: { connected: boolean; status: string; phone_number: string | null }; settings: Setting[]; records: RecordItem[] };
const dateTime = (v: string | null) => v ? new Date(v).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : '—';
const labels = { pending: 'Pendente', sent: 'Enviado', dismissed: 'Dispensado', failed: 'Falha no envio' };
const apiError = (error: unknown, fallback: string) => {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
};

export default function FollowupsPage() {
  const [data, setData] = useState<PageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [sending, setSending] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'pending' | 'sent'>('all');
  const [activeSection, setActiveSection] = useState<'messages' | 'records'>('messages');

  const load = useCallback(async () => {
    setLoading(true);
    try { const r = await api.get<PageData>('/api/v1/followups'); setData(r.data); }
    catch (e: unknown) { toast.error(apiError(e, 'Não foi possível carregar a página.')); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => { void load(); }, 60000);
    return () => window.clearInterval(timer);
  }, [load]);

  const changeSetting = (type: string, patch: Partial<Setting>) =>
    setData(d => d ? ({ ...d, settings: d.settings.map(s => s.type === type ? { ...s, ...patch } : s) }) : d);

  const saveSetting = async (s: Setting) => {
    setSaving(s.type);
    try {
      await api.put(`/api/v1/followups/settings/${s.type}`, { auto_enabled: s.auto_enabled, message_template: s.message_template });
      toast.success('Configuração salva.');
    } catch (e: unknown) { toast.error(apiError(e, 'Não foi possível salvar.')); }
    finally { setSaving(null); }
  };

  const send = async (item: RecordItem) => {
    setSending(item.id);
    try {
      const r = await api.post(`/api/v1/followups/records/${item.id}/send`, {});
      if (r.data.sent) toast.success('Mensagem enviada pelo WhatsApp.');
      else toast.error(r.data.error || 'Não foi possível enviar.');
      await load();
    } catch (e: unknown) { toast.error(apiError(e, 'Falha ao enviar.')); }
    finally { setSending(null); }
  };

  const dismiss = async (item: RecordItem) => {
    try {
      await api.post(`/api/v1/followups/records/${item.id}/dismiss`);
      toast.success('Follow-up dispensado.');
      await load();
    } catch (e: unknown) { toast.error(apiError(e, 'Não foi possível dispensar.')); }
  };

  const records = useMemo(() => (data?.records || []).filter(r =>
    filter === 'all' || (filter === 'sent' ? r.status === 'sent' : r.status === 'pending' || r.status === 'failed')
  ), [data, filter]);
  const pending = data?.records.filter(r => r.status === 'pending' || r.status === 'failed').length || 0;
  const sent = data?.records.filter(r => r.status === 'sent').length || 0;

  if (loading && !data) return <div className="flex min-h-64 items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-brand-500" /></div>;

  return <div className="space-y-7 pb-10">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10"><BellRing className="h-5 w-5" /></div>
        <div><h1 className="text-2xl font-bold text-surface-900 dark:text-white">Cobranças e follow-ups</h1><p className="text-sm text-surface-500 dark:text-white/50">Configure mensagens e acompanhe os contatos com seus clientes.</p></div>
      </div>
      <Button variant="outline" onClick={load} disabled={loading} leftIcon={<RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />}>Atualizar</Button>
    </div>

    <Card><CardBody className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
      <div className="flex items-center gap-3">
        <div className={`flex h-11 w-11 items-center justify-center rounded-full ${data?.whatsapp.connected ? 'bg-green-50 text-green-600' : 'bg-surface-100 text-surface-500'}`}>{data?.whatsapp.connected ? <MessageCircle /> : <Smartphone />}</div>
        <div><p className="font-semibold text-surface-900 dark:text-white">Conexão com WhatsApp</p><p className="text-sm text-surface-500">{data?.whatsapp.connected ? `Conectado ${data.whatsapp.phone_number ? '· +' + data.whatsapp.phone_number : ''}` : 'Desconectado. Conecte para enviar mensagens.'}</p></div>
      </div>
      <a href="/whatsapp" className="inline-flex items-center justify-center gap-2 rounded-xl border border-surface-200 px-4 py-2.5 text-sm font-medium dark:border-white/10"><MessageCircle className="h-4 w-4" />{data?.whatsapp.connected ? 'Ver conexão' : 'Conectar WhatsApp'}</a>
    </CardBody></Card>

    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <button onClick={() => setActiveSection('messages')} className={`rounded-xl border px-5 py-4 text-left transition ${activeSection === 'messages' ? 'border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300' : 'border-surface-200 bg-white text-surface-600 hover:border-brand-300 dark:border-white/10 dark:bg-white/[0.02] dark:text-white/70'}`}>
        <span className="flex items-center gap-2 font-semibold"><Settings2 className="h-5 w-5" /> Personalizar mensagens</span>
        <span className="mt-1 block text-sm opacity-75">Edite os textos e escolha quais automações ativar.</span>
      </button>
      <button onClick={() => setActiveSection('records')} className={`rounded-xl border px-5 py-4 text-left transition ${activeSection === 'records' ? 'border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300' : 'border-surface-200 bg-white text-surface-600 hover:border-brand-300 dark:border-white/10 dark:bg-white/[0.02] dark:text-white/70'}`}>
        <span className="flex items-center gap-2 font-semibold"><BellRing className="h-5 w-5" /> Registro de cobranças e follow-ups <span className="rounded-full bg-brand-600 px-2 py-0.5 text-xs text-white">{pending}</span></span>
        <span className="mt-1 block text-sm opacity-75">Consulte, envie ou dispense registros identificados.</span>
      </button>
    </div>

    {activeSection === 'messages' ? <section className="space-y-4">
      <div><h2 className="text-lg font-semibold text-surface-900 dark:text-white">Personalizar mensagens</h2><p className="text-sm text-surface-500">Ative cada tipo separadamente e personalize a mensagem que será enviada.</p></div>
      <div className="grid gap-4 xl:grid-cols-2">{data?.settings.map(s => <Card key={s.type}>
        <CardHeader><div className="flex items-start justify-between gap-3"><div><h3 className="font-semibold text-surface-900 dark:text-white">{s.title}</h3><p className="mt-1 text-sm text-surface-500">{s.description}</p></div><div className="flex items-center gap-2"><span className="text-xs text-surface-500">{s.auto_enabled ? 'Automático ativo' : 'Manual'}</span><Toggle checked={s.auto_enabled} onChange={v => { if (v && !data?.whatsapp.connected) { toast.error('Conecte o WhatsApp antes de ativar a automação.'); return; } changeSetting(s.type, { auto_enabled: v }); }} size="sm" /></div></div></CardHeader>
        <CardBody className="space-y-3"><label className="block text-sm font-medium text-surface-700 dark:text-white/80">Mensagem padrão editável</label><textarea rows={4} value={s.message_template} onChange={e => changeSetting(s.type, { message_template: e.target.value })} className="w-full resize-y rounded-xl border border-surface-200 bg-surface-50 p-3 text-sm leading-6 text-surface-800 outline-none focus:border-brand-500 dark:border-white/10 dark:bg-white/5 dark:text-white" /><p className="text-xs text-surface-500">Variáveis: {'{nome}, {descricao}, {valor_venda}, {valor_parcela}, {parcela}, {data_vencimento}'}</p><div className="flex justify-end"><Button size="sm" onClick={() => saveSetting(s)} isLoading={saving === s.type} disabled={saving !== null || !s.message_template.trim()} leftIcon={<Save className="h-4 w-4" />}>Salvar configuração</Button></div>
        {s.auto_enabled && !data.whatsapp.connected && <p className="flex items-center gap-2 rounded-lg bg-amber-50 p-2 text-xs text-amber-800 dark:bg-amber-500/10 dark:text-amber-300"><AlertCircle className="h-4 w-4" /> Automação ativa; o envio aguardará a conexão do WhatsApp.</p>}</CardBody>
      </Card>)}</div>
    </section> : <section className="space-y-4">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end"><div><h2 className="text-lg font-semibold text-surface-900 dark:text-white">Registro de cobranças e follow-ups</h2><p className="mt-1 text-sm text-surface-500">Toda situação identificada fica registrada, mesmo com o automático desligado.</p></div><div className="flex gap-2">{(['all','pending','sent'] as const).map(f => <button key={f} onClick={() => setFilter(f)} className={`rounded-lg px-3 py-2 text-sm font-medium ${filter === f ? 'bg-brand-600 text-white' : 'border border-surface-200 text-surface-600 dark:border-white/10 dark:text-white/60'}`}>{f === 'all' ? `Todos (${data?.records.length || 0})` : f === 'pending' ? `Pendentes (${pending})` : `Enviados (${sent})`}</button>)}</div></div>
      {records.length === 0 ? <Card><CardBody className="py-12 text-center"><CheckCircle2 className="mx-auto h-10 w-10 text-green-500" /><p className="mt-3 font-semibold text-surface-900 dark:text-white">Nenhum registro nesta categoria</p><p className="mt-1 text-sm text-surface-500">Quando uma situação for identificada, ela aparecerá aqui.</p></CardBody></Card> :
      <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">{records.map(item => <Card key={item.id}><CardBody className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-2"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold text-surface-900 dark:text-white">{item.customer_name}</h3><span className={`rounded-full px-2 py-1 text-xs font-semibold ${item.status === 'sent' ? 'bg-green-50 text-green-700' : item.status === 'dismissed' ? 'bg-surface-100 text-surface-500' : item.status === 'failed' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-700'}`}>{labels[item.status]}</span></div><p className="mt-1 text-xs text-surface-500">{item.phone || 'Telefone não informado'}</p></div><span className="shrink-0 rounded-lg bg-surface-50 px-2 py-1 text-xs text-surface-500 dark:bg-white/5">{item.title}</span></div>
        <div className="rounded-xl bg-surface-50 p-3 dark:bg-white/[0.04]"><p className="text-xs font-medium text-surface-800 dark:text-white/80">{item.description}</p><p className="mt-2 whitespace-pre-wrap text-sm leading-5 text-surface-600 dark:text-white/60">{item.message}</p></div>
        <div className="text-xs text-surface-500">Identificado: {dateTime(item.due_at)}{item.sent_at ? ` · Enviado: ${dateTime(item.sent_at)}` : ''}</div>
        {item.error && <p className="rounded-lg bg-red-50 p-2 text-xs text-red-700">{item.error}</p>}
        {(item.status === 'pending' || item.status === 'failed') && <div className="flex justify-end gap-2 border-t border-surface-100 pt-3 dark:border-white/10"><Button size="sm" variant="outline" onClick={() => dismiss(item)} leftIcon={<XCircle className="h-4 w-4" />}>Dispensar</Button><Button size="sm" onClick={() => send(item)} isLoading={sending === item.id} disabled={sending !== null} leftIcon={<Send className="h-4 w-4" />}>Fazer follow-up</Button></div>}
        {item.status === 'dismissed' && <p className="text-right text-xs text-surface-400">Este registro foi dispensado.</p>}
      </CardBody></Card>)}</div>}
    </section>}
    <p className="text-xs leading-5 text-surface-400">Novas situações são verificadas automaticamente. Registros anteriores à ativação não serão enviados automaticamente; continuam disponíveis para envio manual.</p>
  </div>;
}
