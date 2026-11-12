import { useEffect, useState } from 'react';
import { Check, Crown } from 'lucide-react';
import { toast } from 'sonner';
import { isAxiosError } from 'axios';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card, CardBody } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

const LIMITE_CLIENTES_FREE = 5;

// Usado quando o backend não devolve o price_id do plano.
const PRICE_IDS_FALLBACK: Record<string, string> = {
  pro: 'price_1UaltqRruCfBuFHNt2bQ1kBM',
};

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
  price_id: string | null;
  features: { name: string; included: boolean }[];
  is_popular: boolean;
}

const PLANOS_PADRAO: Plan[] = [
  {
    name: 'free',
    display_name: 'Free',
    price_monthly: 0,
    price_id: null,
    is_popular: false,
    features: [
      { name: 'Até 5 clientes', included: true },
      { name: 'Edição e acompanhamento dos clientes', included: true },
    ],
  },
  {
    name: 'pro',
    display_name: 'Pro',
    price_monthly: 24.9,
    price_id: PRICE_IDS_FALLBACK.pro,
    is_popular: true,
    features: [
      { name: 'Clientes ilimitados', included: true },
      { name: 'Suporte prioritário', included: true },
    ],
  },
  {
    name: 'enterprise',
    display_name: 'Enterprise',
    price_monthly: 99,
    price_id: null,
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

export default function BillingPage() {
  const [sub, setSub] = useState<Subscription | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [totalClientes, setTotalClientes] = useState<number | null>(null);

  useEffect(() => {
    const carregarAssinatura = () =>
      api
        .get<Subscription | null>('/api/v1/subscriptions/current')
        .then((r) => setSub(r.data ?? null))
        .catch(() => {});

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

    // Ao voltar do checkout o webhook do Stripe pode levar alguns segundos.
    let timer: number | undefined;
    if (new URLSearchParams(window.location.search).get('success') === 'true') {
      toast.success('Pagamento recebido! Seu plano será atualizado em instantes.');
      timer = window.setTimeout(carregarAssinatura, 4000);
    }

    return () => window.clearTimeout(timer);
  }, []);

  const assinaturaAtiva = sub?.status === 'active' || sub?.status === 'trialing';
  const currentPlan = assinaturaAtiva && sub ? sub.plan_name : 'free';
  const planoAtual = plans.find((p) => p.name === currentPlan);
  const nomePlanoAtual = planoAtual?.display_name ?? currentPlan.charAt(0).toUpperCase() + currentPlan.slice(1);
  const statusLabel = sub ? (STATUS_LABEL[sub.status] ?? sub.status) : 'Ativa';
  // Quem já tem plano pago altera/cancela pelo portal, para não criar uma 2ª assinatura.
  const gerenciarPeloPortal = currentPlan !== 'free';

  const handleUpgrade = async (plan: Plan) => {
    const priceId = plan.price_id ?? PRICE_IDS_FALLBACK[plan.name];

    if (!priceId) {
      toast.error('Este plano ainda não está disponível para contratação.');
      return;
    }

    try {
      const r = await api.post('/api/v1/subscriptions/checkout', {
        price_id: priceId,
        success_url: `${window.location.origin}/settings/billing?success=true`,
        cancel_url: `${window.location.origin}/settings/billing`,
      });

      window.location.href = r.data.checkout_url;
    } catch {
      toast.error('Não foi possível iniciar o pagamento.');
    }
  };

  const handlePortal = async () => {
    try {
      const r = await api.get('/api/v1/subscriptions/portal');
      window.location.href = r.data.portal_url;
    } catch {
      toast.error('Não foi possível abrir o portal de assinatura.');
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
                {sub?.current_period_end && currentPlan !== 'free' && (
                  <p className="text-sm text-surface-500 mt-0.5">
                    Renova em {new Date(sub.current_period_end).toLocaleDateString('pt-BR')}
                  </p>
                )}
              </div>
            </div>
            {gerenciarPeloPortal && (
              <Button variant="secondary" onClick={handlePortal}>
                Gerenciar assinatura
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
                  ${plan.price_monthly}
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
              ) : (
                <Button
                  variant={plan.is_popular ? 'primary' : 'outline'}
                  className="w-full"
                  onClick={() => (gerenciarPeloPortal ? handlePortal() : handleUpgrade(plan))}
                >
                  {gerenciarPeloPortal ? 'Alterar no portal' : 'Assinar'}
                </Button>
              )}
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
}
