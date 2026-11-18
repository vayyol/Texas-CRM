import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MessageCircle, Smartphone, AlertCircle, Loader2, CheckCircle2 } from 'lucide-react';
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

export default function WhatsAppPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<WhatsAppStatus | null>(null);
  const [terms, setTerms] = useState<Terms | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [qr, setQr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const connectionStartedAt = useRef<number | null>(null);

  const refreshStatus = useCallback(async () => {
    const data = await apiGet<WhatsAppStatus>('/api/v1/whatsapp/status');
    setStatus(data);
    return data;
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
      if (statusData.session?.status === 'WORKING') navigate('/followups', { replace: true });
    }).catch(() => {
      if (active) setError('Não foi possível carregar o estado da conexão do WhatsApp.');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [navigate]);

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
          navigate('/followups', { replace: true });
          return;
        }
        const elapsed = connectionStartedAt.current === null ? 0 : Date.now() - connectionStartedAt.current;
        if (current.session?.status === 'FAILED' || (current.session?.status === 'STOPPED' && elapsed >= 20000)) {
          setConnecting(false);
          setError(current.session.status === 'FAILED'
            ? 'O WAHA informou que a sessão falhou. Tente iniciar novamente.'
            : 'A sessão permaneceu parada por 20 segundos. Confira o WAHA e tente novamente.');
          return;
        }
        if (current.session?.status !== 'SCAN_QR_CODE') return;
        try {
          const data = await apiGet<{ mimetype: string; data: string }>('/api/v1/whatsapp/session/qr');
          if (active) setQr(`data:${data.mimetype};base64,${data.data}`);
        } catch {
          // O WAHA pode demorar alguns segundos para disponibilizar o QR Code.
        }
      } catch {
        if (active) {
          setConnecting(false);
          setError('Não foi possível consultar a conexão. Tente novamente.');
        }
      }
    };
    void poll();
    const timer = window.setInterval(poll, 2500);
    return () => { active = false; window.clearInterval(timer); };
  }, [connecting, refreshStatus, navigate]);

  const connect = async () => {
    if (connecting || status?.session?.status === 'WORKING') return;
    setConnecting(true);
    connectionStartedAt.current = Date.now();
    setError('');
    setQr(null);
    try {
      if (!status?.terms_accepted) {
        if (!accepted || !terms) throw new Error('Leia e aceite o termo para continuar.');
        await apiPost('/api/v1/whatsapp/consent', { accepted: true, terms_version: terms.version });
      }
      if (!status?.session) await apiPost('/api/v1/whatsapp/session');
      await apiPost('/api/v1/whatsapp/session/start');
      await refreshStatus();
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail
        || (err as { message?: string })?.message;
      setError(message || 'Não foi possível iniciar a conexão. Tente novamente.');
      connectionStartedAt.current = null;
      setConnecting(false);
    }
  };

  if (loading) return <div className="flex items-center justify-center py-24"><Loader2 className="h-7 w-7 animate-spin text-brand-500" /></div>;

  const connected = status?.session?.status === 'WORKING';

  return <div className="mx-auto max-w-3xl space-y-6">
    <div>
      <h1 className="text-2xl font-bold text-surface-900 dark:text-white">WhatsApp</h1>
      <p className="mt-1 text-sm text-surface-500 dark:text-white/50">Conecte seu número para enviar cobranças e follow-ups diretamente pelo TexasCRM.</p>
    </div>

    {error && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">{error}</div>}

    {connected ? <Card>
      <CardBody className="flex flex-col items-center gap-4 py-12 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-50 text-green-600 dark:bg-green-900/20"><CheckCircle2 className="h-9 w-9" /></div>
        <div><h2 className="text-xl font-semibold text-surface-900 dark:text-white">WhatsApp conectado!</h2><p className="mt-2 text-sm text-surface-500">Seu número está pronto para enviar mensagens e follow-ups.</p>{status?.session?.phone_number && <p className="mt-1 text-sm font-medium text-surface-700 dark:text-white/80">+{status.session.phone_number}</p>}</div>
        <Button onClick={() => navigate('/followups')}>Ir para personalizar follow-ups</Button>
      </CardBody>
    </Card> : <div className="grid gap-6 md:grid-cols-2">
      <Card>
        <CardHeader><div className="flex items-center gap-2 font-semibold text-surface-900 dark:text-white"><Smartphone className="h-5 w-5 text-brand-500" /> Conectar meu WhatsApp</div></CardHeader>
        <CardBody className="space-y-4">
          <p className="text-sm text-surface-600 dark:text-white/60">A conexão é feita com seu próprio número, usando uma sessão semelhante ao WhatsApp Web.</p>
          {terms && <div className="max-h-52 overflow-y-auto rounded-xl bg-surface-50 p-4 text-sm leading-6 text-surface-600 dark:bg-white/5 dark:text-white/60">{terms.text}</div>}
          <label className="flex items-start gap-3 text-sm text-surface-700 dark:text-white/70">
            <input type="checkbox" className="mt-1 accent-brand-600" checked={accepted} onChange={event => setAccepted(event.target.checked)} disabled={status?.terms_accepted || connecting} />
            <span>Li e aceito o termo de uso e estou ciente dos riscos de desconexão e possíveis restrições do WhatsApp.</span>
          </label>
          <Button onClick={connect} disabled={!status?.integration_configured || (!accepted && !status?.terms_accepted) || connecting} isLoading={connecting} leftIcon={<MessageCircle className="h-4 w-4" />}>
            {connecting ? 'Aguardando conexão...' : status?.session ? 'Gerar QR Code / reconectar' : 'Aceitar e conectar'}
          </Button>
          {!status?.integration_configured && <p className="text-xs text-red-600">A integração ainda não está configurada no servidor.</p>}
        </CardBody>
      </Card>
      <Card>
        <CardHeader><div className="font-semibold text-surface-900 dark:text-white">Leia o QR Code</div></CardHeader>
        <CardBody className="flex min-h-72 flex-col items-center justify-center gap-4 text-center">
          {qr ? <>
            <img src={qr} alt="QR Code para conectar o WhatsApp" className="h-64 w-64 rounded-xl border border-surface-200 bg-white p-2" />
            <p className="text-sm text-surface-500 dark:text-white/50">No celular, abra WhatsApp → Aparelhos conectados → Conectar aparelho.</p>
          </> : connecting ? <div className="space-y-3"><Loader2 className="mx-auto h-9 w-9 animate-spin text-brand-500" /><p className="text-sm text-surface-500 dark:text-white/50">Preparando a sessão e aguardando o QR Code...</p></div> : <div className="space-y-3"><Smartphone className="mx-auto h-10 w-10 text-surface-300" /><p className="text-sm text-surface-500 dark:text-white/50">Clique em conectar para gerar o QR Code.</p></div>}
        </CardBody>
      </Card>
    </div>}

    <div className="flex items-start gap-2 text-xs text-surface-400"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /><p>Esta conexão usa uma integração não oficial e pode sofrer interrupções. Não use para disparos em massa.</p></div>
  </div>;
}
