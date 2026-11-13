import { useCallback, useEffect, useRef, useState } from 'react';
import { Check, Crown } from 'lucide-react';
import { toast } from 'sonner';
import { isAxiosError } from 'axios';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card, CardBody } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

const LIMITE_CLIENTES_FREE = 5;

interface Subscription {
  id: string;
  plan_name: string;
  status: string;
  current_period_start: string | null;
  current_period_end: string | null;
}

interface Plan {
  name: string;
  display_name: string;
  price_monthly: number;
  purchasable: boolean;
  features: { name: string; included: boolean }[];
  is_popular: boolean;
}

// Usado só se o backend não responder. Os valores reais vêm de /subscriptions/plans.
const PLANOS_PADRAO: Plan[] = [
  {
    name: 'free',
    display_name: 'Free',
    price_monthly: 0,
    purchasable: false,
    is_popular: false,
    features: [
      { name: 'Até 5 clientes cadastrados', included: true },
      { name: 'Edição de clientes cadastrados', included: true },
      { name: 'Registro do relacionamento com os clientes', included: true },
      { name: 'Análise de estatísticas', included: true },
    ],
  },
  {
    name: 'pro',
    display_name: 'Pro',
    price_monthly: 24.9,
    purchasable: true,
    is_popular: true,
    features: [
      { name: 'Cadastro ilimitado de clientes', included: true },
      { name: 'Edição de clientes cadastrados', included: true },
      { name: 'Registro do relacionamento com os clientes', included: true },
      { name: 'Análise de estatísticas', included: true },
      { name: 'Suporte prioritário', included: true },
    ],
  },
  {
    name: 'enterprise',
    display_name: 'Enterprise',
    price_monthly: 99,
    purchasable: false,
    is_popular: false,
    features: [
      { name: 'Clientes ilimitados', included: true },
      { name: 'Tudo do plano Pro', included: true },
      { name: 'Painel administrativo', included: true },
      { name: 'SLA garantido', included: true },
    ],
  },
];

const STATUS_LABEL: Record<string, string> = {
  active: 'Ativa',
  trialing: 'Período de teste',
  canceled: 'Cancelada',
  past_due: 'Pagamento pendente',
  unpaid: 'Pagamento pendente',
  incomplete: 'Incompleta',
};

const formatarPreco = (valor: number) =>
  valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

const formatarData = (iso: string) => new Date(iso).toLocaleDateString('pt-BR');

// Mensagens do backend já vêm em português e são seguras para mostrar ao usuário.
const mensagemDeErro = (error: unknown, padrao: string) =>
  isAxiosError(error) && typeof error.response?.data?.detail === 'string' ? error.response.data.detail : padrao;

export default function BillingPage() {
  const [sub, setSub] = useState<Subscription | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [totalClientes, setTotalClientes] = useState<number | null>(null);
  const [documento, setDocumento] = useState('');
  const [pedirDocumento, setPedirDocumento] = useState<string | null>(null);
  const [processando, setProcessando] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  const carregarAssinatura = useCallback(
    () =>
      api
        .get<Subscription | null>('/api/v1/subscriptions/current')
        .then((r) => {
          setSub(r.data ?? null);
          return r.data ?? null;
        })
        .catch(() => null),
    [],
  );

  useEffect(() => {
    carregarAssinatura();

    api
      .get<Plan[]>('/api/v1/subscriptions/plans')
      .then((r) => setPlans(r.data?.length ? r.data : PLANOS_PADRAO))
      .catch(() => setPlans(PLANOS_PADRAO));

    api
      .get<unknown[]>('/api/v1/integracao/listar-clientes')
      .then((r) => setTotalClientes(Array.isArray(r.data) ? r.data.length : 0))
      .catch((error: unknown) =>
        setTotalClientes(isAxiosError(error) && error.response?.status === 404 ? 0 : null),
      );

    // Voltar da página do Asaas NÃO confirma o pagamento: quem confirma é o webhook.
    // Por isso consultamos o backend até o plano mudar (ou desistimos depois de ~40s).
    const params = new URLSearchParams(window.location.search);
    if (params.get('success') === 'true') {
      toast.info('Estamos confirmando o seu pagamento. Seu plano será atualizado em instantes.');
      let tentativas = 0;
      const verificar = async () => {
        const atual = await carregarAssinatura();
        tentativas += 1;
        if (atual && atual.plan_name !== 'free' && atual.status === 'active') {
          toast.success('Pagamento confirmado! Seu plano foi atualizado.');
          return;
        }
        if (tentativas < 10) timer.current = window.setTimeout(verificar, 4000);
      };
      timer.current = window.setTimeout(verificar, 3000);
    } else if (params.get('canceled') === 'true') {
      toast.info('O pagamento não foi concluído. Você pode tentar novamente quando quiser.');
    } else if (params.get('expired') === 'true') {
      toast.info('O link de pagamento expirou. Clique em Assinar para gerar um novo.');
    }
    if (params.toString()) window.history.replaceState({}, '', window.location.pathname);

    return () => window.clearTimeout(timer.current);
  }, [carregarAssinatura]);

  // O acesso vale para assinatura ativa e também para cancelada que ainda está no período já pago.
  const assinaturaAtiva = sub?.status === 'active' || sub?.status === 'trialing';
  const periodoPagoAtivo =
    sub?.status === 'canceled' &&
    sub.plan_name !== 'free' &&
    !!sub.current_period_end &&
    new Date(sub.current_period_end) > new Date();
  const currentPlan = (assinaturaAtiva || periodoPagoAtivo) && sub ? sub.plan_name : 'free';
  const planoExibido = sub && sub.plan_name !== 'free' ? sub.plan_name : currentPlan;
  const nomePlanoAtual =
    plans.find((p) => p.name === planoExibido)?.display_name ??
    planoExibido.charAt(0).toUpperCase() + planoExibido.slice(1);
  const statusLabel = sub ? (STATUS_LABEL[sub.status] ?? sub.status) : 'Ativa';
  const podeCancelar = !!sub && sub.plan_name !== 'free' && sub.status !== 'canceled';
  const temAssinaturaPaga = currentPlan !== 'free' || podeCancelar;

  const handleUpgrade = async (plan: Plan) => {
    if (processando) return;
    setProcessando(true);
    try {
      // O frontend informa só o plano; o valor é definido pelo backend.
      const r = await api.post('/api/v1/subscriptions/checkout', {
        plan: plan.name,
        cpf_cnpj: documento.trim() || undefined,
      });
      window.location.href = r.data.checkout_url;
    } catch (error) {
      const detalhe = mensagemDeErro(error, 'Não foi possível iniciar o pagamento.');
      // Primeira assinatura: o Asaas exige CPF/CNPJ para cadastrar o cliente.
      if (detalhe.includes('CPF')) setPedirDocumento(plan.name);
      toast.error(detalhe);
      setProcessando(false);
    }
  };

  const handleCancelar = async () => {
    const confirmado = window.confirm(
      'Deseja cancelar a sua assinatura? Você mantém o acesso até o fim do período já pago.',
    );
    if (!confirmado || processando) return;
    setProcessando(true);
    try {
      await api.post('/api/v1/subscriptions/cancel');
      toast.success('Assinatura cancelada. Nenhuma nova cobrança será feita.');
      await carregarAssinatura();
    } catch (error) {
      toast.error(mensagemDeErro(error, 'Não foi possível cancelar a assinatura.'));
    } finally {
      setProcessando(false);
    }
  };

  return (
    <div className="max-w-4xl space-y-6">
      <h1 className="text-2xl font-bold text-surface-900 dark:text-white">Assinatura</h1>

      {/* Plano atual */}
      <Card variant="gradient-border">
        <CardBody className="space-y-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-brand-50 dark:bg-brand-900/30">
                <Crown className="w-6 h-6 text-brand-600 dark:text-brand-400" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-surface-900 dark:text-white">Plano {nomePlanoAtual}</h3>
                  <Badge variant={assinaturaAtiva || !sub ? 'success' : 'warning'} dot>
                    {statusLabel}
                  </Badge>
                </div>
                {sub?.current_period_end && planoExibido !== 'free' && (
                  <p className="text-sm text-surface-500 mt-0.5">
                    {sub.status === 'canceled'
                      ? `Acesso até ${formatarData(sub.current_period_end)}`
                      : `Renova em ${formatarData(sub.current_period_end)}`}
                  </p>
                )}
                {sub?.status === 'past_due' && (
                  <p className="text-sm text-amber-600 dark:text-amber-400 mt-0.5">
                    Há um pagamento pendente. Regularize-o para voltar a usar o plano.
                  </p>
                )}
              </div>
            </div>
            {podeCancelar && (
              <Button variant="secondary" onClick={handleCancelar} disabled={processando}>
                Cancelar assinatura
              </Button>
            )}
          </div>

          {currentPlan === 'free' && totalClientes !== null && (
            <div>
              <div className="flex items-center justify-between text-sm text-surface-600 dark:text-white/60 mb-1.5">
                <span>Clientes cadastrados</span>
                <span>
                  {totalClientes} de {LIMITE_CLIENTES_FREE}
                </span>
              </div>
              <div className="h-2 rounded-full bg-surface-100 dark:bg-white/10 overflow-hidden">
                <div
                  className="h-full rounded-full bg-brand-500 transition-all"
                  style={{ width: `${Math.min(100, (totalClientes / LIMITE_CLIENTES_FREE) * 100)}%` }}
                />
              </div>
              {totalClientes >= LIMITE_CLIENTES_FREE && (
                <p className="text-sm text-amber-600 dark:text-amber-400 mt-2">
                  Você atingiu o limite do plano Free. Assine um plano para cadastrar mais clientes.
                </p>
              )}
            </div>
          )}
        </CardBody>
      </Card>

      {/* Planos */}
      <div className="grid md:grid-cols-3 gap-6">
        {plans.map((plan) => (
          <Card key={plan.name} className={plan.is_popular ? 'ring-2 ring-brand-500' : ''}>
            <CardBody className="space-y-4">
              {plan.is_popular && <Badge variant="info">Mais popular</Badge>}
              <h3 className="text-lg font-bold text-surface-900 dark:text-white">{plan.display_name}</h3>
              <div className="flex items-baseline gap-1">
                <span className="text-3xl font-extrabold text-surface-900 dark:text-white">
                  {formatarPreco(plan.price_monthly)}
                </span>
                <span className="text-surface-500">/mês</span>
              </div>
              <ul className="space-y-2">
                {plan.features.map((f) => (
                  <li key={f.name} className="flex items-center gap-2 text-sm text-surface-600 dark:text-white/60">
                    <Check className="w-4 h-4 text-accent-500 shrink-0" />
                    {f.name}
                  </li>
                ))}
              </ul>

              {currentPlan === plan.name ? (
                <Button variant="secondary" className="w-full" disabled>
                  Plano atual
                </Button>
              ) : plan.purchasable && !temAssinaturaPaga ? (
                <div className="space-y-2">
                  {pedirDocumento === plan.name && (
                    <input
                      type="text"
                      inputMode="numeric"
                      autoComplete="off"
                      maxLength={18}
                      value={documento}
                      onChange={(e) => setDocumento(e.target.value)}
                      placeholder="CPF ou CNPJ"
                      aria-label="CPF ou CNPJ"
                      className="w-full rounded-lg border border-surface-200 dark:border-white/10 bg-white dark:bg-white/5 px-3 py-2 text-sm text-surface-900 dark:text-white"
                    />
                  )}
                  <Button
                    variant={plan.is_popular ? 'primary' : 'outline'}
                    className="w-full"
                    onClick={() => handleUpgrade(plan)}
                    disabled={processando}
                  >
                    {processando ? 'Aguarde...' : pedirDocumento === plan.name ? 'Continuar para o pagamento' : 'Assinar'}
                  </Button>
                </div>
              ) : !plan.purchasable && plan.name !== 'free' ? (
                <Button variant="outline" className="w-full" disabled>
                  Em breve
                </Button>
              ) : null}
            </CardBody>
          </Card>
        ))}
      </div>

      <p className="text-sm text-surface-500">
        O pagamento é feito em uma página segura do Asaas, com cobrança mensal no cartão de crédito. Você pode
        cancelar quando quiser e mantém o acesso até o fim do período já pago.
      </p>
    </div>
  );
}
