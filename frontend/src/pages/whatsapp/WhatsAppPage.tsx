import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { MessageCircle, Send, Smartphone, AlertCircle, Loader2 } from 'lucide-react';
import { apiGet, apiPost } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';

type WhatsAppStatus = {
  integration_configured: boolean;
  terms_version: string;
  terms_accepted: boolean;
  session: { name: string; status: string; phone_number: string | null } | null;
};
type Terms = { version: string; text: string };
type Conversation = {
  id: string; chat_id: string; contact_name: string | null; contact_phone: string | null;
  last_message_preview: string | null; last_message_at: string | null; unread_count: number;
};
type ChatMessage = { id: string; direction: 'in' | 'out'; body: string; status: string; sent_at: string | null };

export default function WhatsAppPage() {
  const [status, setStatus] = useState<WhatsAppStatus | null>(null);
  const [terms, setTerms] = useState<Terms | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [qr, setQr] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refreshStatus = useCallback(async () => {
    const data = await apiGet<WhatsAppStatus>('/api/v1/whatsapp/status');
    setStatus(data);
    return data;
  }, []);
  const refreshConversations = useCallback(async () => {
    const data = await apiGet<Conversation[]>('/api/v1/whatsapp/conversations');
    setConversations(data);
    setSelected((current) => current ? data.find((item) => item.id === current.id) ?? current : null);
  }, []);
  const refreshMessages = useCallback(async (id: string) => {
    const data = await apiGet<ChatMessage[]>(`/api/v1/whatsapp/conversations/${id}/messages`);
    setMessages(data);
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([
      apiGet<Terms>('/api/v1/whatsapp/terms'),
      apiGet<WhatsAppStatus>('/api/v1/whatsapp/status'),
    ]).then(([termData, statusData]) => {
      if (!active) return;
      setTerms(termData);
      setStatus(statusData);
      setAccepted(statusData.terms_accepted);
      if (statusData.session?.status === 'WORKING') void refreshConversations();
    }).catch(() => {
      if (active) setError('Não foi possível carregar a central do WhatsApp.');
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [refreshConversations]);

  useEffect(() => {
    if (!connecting) return;
    let active = true;
    const poll = async () => {
      try {
        const current = await refreshStatus();
        if (!active) return;
        if (current.session?.status === 'WORKING') {
          setConnecting(false);
          setQr(null);
          await refreshConversations();
          return;
        }
        if (current.session && ['FAILED', 'STOPPED'].includes(current.session.status)) {
          setConnecting(false);
          return;
        }
        // O WAHA só disponibiliza QR quando a sessão chega a SCAN_QR_CODE.
        // Consultar durante STARTING pode retornar 422 e não é uma falha definitiva.
        if (current.session?.status !== 'SCAN_QR_CODE') return;
        try {
          const data = await apiGet<{ mimetype: string; data: string }>('/api/v1/whatsapp/session/qr');
          if (active) setQr(`data:${data.mimetype};base64,${data.data}`);
        } catch {
          // WAHA can take a few seconds to prepare the QR.
        }
      } catch {
        if (active) setError('Não foi possível consultar o estado da conexão.');
      }
    };
    void poll();
    const timer = window.setInterval(poll, 2500);
    return () => { active = false; window.clearInterval(timer); };
  }, [connecting, refreshStatus, refreshConversations]);

  useEffect(() => {
    if (!status?.session || status.session.status !== 'WORKING') return;
    void refreshConversations();
    const timer = window.setInterval(() => { void refreshConversations(); }, 5000);
    return () => window.clearInterval(timer);
  }, [status?.session?.status, refreshConversations]);

  useEffect(() => {
    if (!selected) { setMessages([]); return; }
    void refreshMessages(selected.id);
    const timer = window.setInterval(() => { void refreshMessages(selected.id); }, 3000);
    return () => window.clearInterval(timer);
  }, [selected?.id, refreshMessages]);

  const connect = async () => {
    setError('');
    setQr(null);
    try {
      if (!status?.terms_accepted) {
        if (!accepted || !terms) { setError('Leia e aceite o termo para continuar.'); return; }
        await apiPost('/api/v1/whatsapp/consent', { accepted: true, terms_version: terms.version });
      }
      if (!status?.session) await apiPost('/api/v1/whatsapp/session');
      await apiPost('/api/v1/whatsapp/session/start');
      await refreshStatus();
      setConnecting(true);
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(message || 'Não foi possível iniciar a conexão. Tente novamente.');
    }
  };

  const sendMessage = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected || !draft.trim() || sending) return;
    setSending(true);
    setError('');
    try {
      await apiPost(`/api/v1/whatsapp/conversations/${selected.id}/messages`, { text: draft.trim() });
      setDraft('');
      await refreshMessages(selected.id);
      await refreshConversations();
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(message || 'Não foi possível enviar a mensagem.');
    } finally {
      setSending(false);
    }
  };

  if (loading) return <div className="flex items-center justify-center py-24"><Loader2 className="h-7 w-7 animate-spin text-brand-500" /></div>;
  const connected = status?.session?.status === 'WORKING';

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-white">WhatsApp</h1>
          <p className="mt-1 text-sm text-surface-500 dark:text-white/50">Conecte seu número e atenda suas conversas pelo TexasCRM.</p>
        </div>
        <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium ${connected ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300' : 'bg-surface-100 text-surface-600 dark:bg-white/10 dark:text-white/60'}`}>
          <span className={`h-2 w-2 rounded-full ${connected ? 'bg-green-500' : 'bg-surface-400'}`} />
          {connected ? 'Conectado' : connecting ? 'Aguardando conexão' : status?.session?.status ?? 'Desconectado'}
        </span>
      </div>

      {error && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">{error}</div>}

      {!connected ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader><div className="flex items-center gap-2 font-semibold text-surface-900 dark:text-white"><Smartphone className="h-5 w-5 text-brand-500" /> Conectar meu WhatsApp</div></CardHeader>
            <CardBody className="space-y-4">
              <p className="text-sm text-surface-600 dark:text-white/60">A conexão é feita com seu próprio número, usando uma sessão semelhante ao WhatsApp Web.</p>
              {terms && <div className="max-h-52 overflow-y-auto rounded-xl bg-surface-50 p-4 text-sm leading-6 text-surface-600 dark:bg-white/5 dark:text-white/60">{terms.text}</div>}
              <label className="flex items-start gap-3 text-sm text-surface-700 dark:text-white/70">
                <input type="checkbox" className="mt-1 accent-brand-600" checked={accepted} onChange={(event) => setAccepted(event.target.checked)} disabled={status?.terms_accepted} />
                <span>Li e aceito o termo de uso e estou ciente dos riscos de desconexão e possíveis restrições do WhatsApp.</span>
              </label>
              <Button onClick={connect} disabled={!status?.integration_configured || (!accepted && !status?.terms_accepted) || connecting} isLoading={connecting} leftIcon={<MessageCircle className="h-4 w-4" />}>
                {connecting ? 'Aguardando QR Code...' : status?.session ? 'Conectar / gerar QR Code' : 'Aceitar e conectar'}
              </Button>
              {!status?.integration_configured && <p className="text-xs text-red-600">A integração ainda não está configurada no servidor.</p>}
            </CardBody>
          </Card>
          <Card>
            <CardHeader><div className="font-semibold text-surface-900 dark:text-white">Leia o QR Code</div></CardHeader>
            <CardBody className="flex min-h-72 flex-col items-center justify-center gap-4 text-center">
              {qr ? (
                <>
                  <img src={qr} alt="QR Code para conectar o WhatsApp" className="h-64 w-64 rounded-xl border border-surface-200 bg-white p-2" />
                  <p className="text-sm text-surface-500 dark:text-white/50">No celular, abra WhatsApp → Aparelhos conectados → Conectar aparelho.</p>
                </>
              ) : connecting ? (
                <div className="space-y-3"><Loader2 className="mx-auto h-9 w-9 animate-spin text-brand-500" /><p className="text-sm text-surface-500 dark:text-white/50">Preparando a sessão e aguardando o QR Code...</p></div>
              ) : (
                <div className="space-y-3"><Smartphone className="mx-auto h-10 w-10 text-surface-300" /><p className="text-sm text-surface-500 dark:text-white/50">Clique em conectar para gerar o QR Code.</p></div>
              )}
            </CardBody>
          </Card>
        </div>
      ) : (
        <Card className="overflow-hidden">
          <div className="grid min-h-[620px] md:grid-cols-[320px_1fr]">
            <div className="border-r border-surface-200 dark:border-white/10">
              <div className="border-b border-surface-200 p-4 dark:border-white/10">
                <h2 className="font-semibold text-surface-900 dark:text-white">Conversas</h2>
                <p className="mt-1 text-xs text-surface-500 dark:text-white/50">{conversations.length} conversa(s)</p>
              </div>
              <div className="max-h-[560px] overflow-y-auto">
                {conversations.map((conversation) => (
                  <button key={conversation.id} onClick={() => setSelected(conversation)} className={`w-full border-b border-surface-100 px-4 py-3 text-left hover:bg-surface-50 dark:border-white/5 dark:hover:bg-white/5 ${selected?.id === conversation.id ? 'bg-brand-50 dark:bg-brand-900/20' : ''}`}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-semibold text-surface-900 dark:text-white">{conversation.contact_name || conversation.contact_phone || conversation.chat_id}</span>
                      {conversation.unread_count > 0 && <span className="rounded-full bg-brand-500 px-2 py-0.5 text-xs text-white">{conversation.unread_count}</span>}
                    </div>
                    <p className="mt-1 truncate text-xs text-surface-500 dark:text-white/50">{conversation.last_message_preview || 'Sem mensagens'}</p>
                  </button>
                ))}
                {conversations.length === 0 && <div className="p-6 text-center text-sm text-surface-500 dark:text-white/50">Nenhuma conversa recebida ainda.</div>}
              </div>
            </div>
            <div className="flex min-w-0 flex-col">
              {selected ? (
                <>
                  <div className="border-b border-surface-200 p-4 dark:border-white/10">
                    <div className="font-semibold text-surface-900 dark:text-white">{selected.contact_name || selected.contact_phone || selected.chat_id}</div>
                    <div className="text-xs text-surface-500 dark:text-white/50">{selected.contact_phone || selected.chat_id}</div>
                  </div>
                  <div className="flex-1 space-y-3 overflow-y-auto bg-surface-50/70 p-4 dark:bg-white/[0.02]">
                    {messages.map((message) => (
                      <div key={message.id} className={`flex ${message.direction === 'out' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm shadow-sm ${message.direction === 'out' ? 'bg-brand-600 text-white' : 'bg-white text-surface-800 dark:bg-white/10 dark:text-white'}`}>
                          <p className="whitespace-pre-wrap break-words">{message.body}</p>
                          <p className={`mt-1 text-right text-[10px] ${message.direction === 'out' ? 'text-white/60' : 'text-surface-400'}`}>{message.sent_at ? new Date(message.sent_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : ''}</p>
                        </div>
                      </div>
                    ))}
                    {messages.length === 0 && <p className="text-center text-sm text-surface-400">Ainda não há mensagens de texto nesta conversa.</p>}
                  </div>
                  <form onSubmit={sendMessage} className="flex gap-2 border-t border-surface-200 p-3 dark:border-white/10">
                    <input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Digite uma mensagem..." maxLength={4000} className="min-w-0 flex-1 rounded-xl border border-surface-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-brand-500 dark:border-white/10 dark:bg-white/5 dark:text-white" />
                    <Button type="submit" disabled={!draft.trim() || sending} isLoading={sending}><Send className="h-4 w-4" /> Enviar</Button>
                  </form>
                </>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center gap-3 text-surface-400"><MessageCircle className="h-10 w-10" /><p className="text-sm">Selecione uma conversa para visualizar as mensagens.</p></div>
              )}
            </div>
          </div>
        </Card>
      )}
      <div className="flex items-start gap-2 text-xs text-surface-400">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
        <p>Esta versão permite conversas de texto. A conexão usa uma integração não oficial e pode sofrer interrupções. Não use para disparos em massa.</p>
      </div>
    </div>
  );
}
